"""Rules engine for diagnosing portal issues.

Implements detection rules for common portal/screen-sharing problems.
"""

from typing import Callable

from ..models import (
    Finding, Severity, Action, ActionType,
    EnvironmentInfo, PortalBackend, ServiceStatus, PortalsConfig
)
from .services import check_service_status, restart_service, PORTAL_SERVICES
from .portals import (
    generate_recommended_config, write_portals_config, 
    read_portals_config, USER_PORTALS_CONF, get_config_diff
)
from .pipewire import is_pipewire_running, is_session_manager_running


class DiagnosticContext:
    """Context containing all diagnostic data for rules evaluation."""
    
    def __init__(
        self,
        environment: EnvironmentInfo,
        backends: list[PortalBackend],
        portal_statuses: dict[str, ServiceStatus],
        pipewire_statuses: dict[str, ServiceStatus],
        portals_config: PortalsConfig | None,
    ):
        self.environment = environment
        self.backends = backends
        self.portal_statuses = portal_statuses
        self.pipewire_statuses = pipewire_statuses
        self.portals_config = portals_config
        
        # Derived properties
        self.backend_names = {b.name.lower() for b in backends}
        self.active_portal_services = [
            name for name, status in portal_statuses.items() if status.is_active
        ]


# Type alias for rule functions
RuleFunc = Callable[[DiagnosticContext], Finding | None]


def rule_x11_session(ctx: DiagnosticContext) -> Finding | None:
    """Detect X11 session and warn about different screen-sharing approach."""
    if not ctx.environment.is_x11:
        return None
    
    return Finding(
        id="x11_session",
        severity=Severity.INFO,
        title="Running on X11 Session",
        component="Session",
        details=(
            "You are running an X11 session, not Wayland. Screen sharing on X11 works differently "
            "and typically doesn't require XDG portals. Most applications can capture the screen "
            "directly on X11.\n\n"
            "If you're experiencing screen-sharing issues on X11, the problem is likely not "
            "related to portals. Consider checking the application's own screen capture settings."
        ),
        evidence=f"XDG_SESSION_TYPE={ctx.environment.session_type}",
        recommended_actions=[
            Action(
                id="x11_guidance",
                type=ActionType.GUIDANCE,
                label="X11 Screen Sharing Guidance",
                description="Screen sharing on X11 is handled directly by applications, not through portals.",
                requires_confirmation=False,
            )
        ],
    )


def rule_portal_service_not_running(ctx: DiagnosticContext) -> Finding | None:
    """Detect if xdg-desktop-portal is not running."""
    portal_status = ctx.portal_statuses.get("xdg-desktop-portal.service")
    
    if not portal_status:
        return None
    
    if portal_status.is_active:
        return None
    
    severity = Severity.ERROR if portal_status.is_failed else Severity.WARNING
    
    def restart_portal() -> tuple[bool, str]:
        return restart_service("xdg-desktop-portal.service")
    
    return Finding(
        id="portal_not_running",
        severity=severity,
        title="XDG Desktop Portal Not Running",
        component="Portal Service",
        details=(
            "The xdg-desktop-portal service is not running. This service is essential for "
            "screen sharing on Wayland as it handles the communication between applications "
            "and the compositor.\n\n"
            "Without this service running, screen sharing will not work in Discord, browsers, "
            "OBS, and other applications."
        ),
        evidence=f"Service status: {'failed' if portal_status.is_failed else 'inactive'}",
        recommended_actions=[
            Action(
                id="restart_portal",
                type=ActionType.RESTART_SERVICE,
                label="Restart xdg-desktop-portal",
                description="Restart the xdg-desktop-portal.service to enable screen sharing",
                command="systemctl --user restart xdg-desktop-portal.service",
                execute_callback=restart_portal,
            ),
            Action(
                id="view_portal_logs",
                type=ActionType.OPEN_LOGS,
                label="View Portal Logs",
                description="View the portal service logs to diagnose the issue",
                command="journalctl --user -xeu xdg-desktop-portal.service",
            ),
        ],
    )


def rule_no_backend_running(ctx: DiagnosticContext) -> Finding | None:
    """Detect if no portal backend is running."""
    if ctx.environment.is_x11:
        return None
    
    # Check if any backend service is running
    backend_services = [
        "xdg-desktop-portal-kde.service",
        "xdg-desktop-portal-gnome.service",
        "xdg-desktop-portal-gtk.service",
        "xdg-desktop-portal-wlr.service",
        "xdg-desktop-portal-hyprland.service",
    ]
    
    running_backends = []
    for service in backend_services:
        status = ctx.portal_statuses.get(service)
        if status and status.is_active:
            running_backends.append(service)
    
    if running_backends:
        return None
    
    # Check if any backends are installed
    if not ctx.backends:
        return Finding(
            id="no_backend_installed",
            severity=Severity.ERROR,
            title="No Portal Backend Installed",
            component="Portal Backend",
            details=(
                "No XDG desktop portal backend is installed. You need a backend that matches "
                "your desktop environment for screen sharing to work.\n\n"
                "Common backends:\n"
                "• KDE Plasma: xdg-desktop-portal-kde\n"
                "• GNOME: xdg-desktop-portal-gnome\n"
                "• Sway/wlroots: xdg-desktop-portal-wlr\n"
                "• Hyprland: xdg-desktop-portal-hyprland\n"
                "• GTK (fallback): xdg-desktop-portal-gtk"
            ),
            evidence="No .portal files found in system directories",
            recommended_actions=[
                Action(
                    id="install_backend_guidance",
                    type=ActionType.GUIDANCE,
                    label="Install Portal Backend",
                    description=(
                        "Install the appropriate portal backend for your desktop. "
                        "Package names vary by distribution."
                    ),
                    requires_confirmation=False,
                ),
            ],
        )
    
    return Finding(
        id="no_backend_running",
        severity=Severity.ERROR,
        title="Portal Backend Not Running",
        component="Portal Backend",
        details=(
            "A portal backend is installed but not running. The screen sharing functionality "
            "requires an active backend to communicate with your compositor.\n\n"
            f"Installed backends: {', '.join(b.name for b in ctx.backends)}"
        ),
        evidence="No backend services active",
        recommended_actions=[
            Action(
                id="restart_portals",
                type=ActionType.RESTART_SERVICE,
                label="Restart All Portal Services",
                description="Restart xdg-desktop-portal to trigger backend activation",
                command="systemctl --user restart xdg-desktop-portal.service",
            ),
        ],
    )


def rule_backend_mismatch(ctx: DiagnosticContext) -> Finding | None:
    """Detect mismatch between desktop environment and active portal backend."""
    if ctx.environment.is_x11:
        return None
    
    # Determine what backend SHOULD be used
    expected_backends = []
    if ctx.environment.is_kde:
        expected_backends = ["kde"]
    elif ctx.environment.is_gnome:
        expected_backends = ["gnome", "gtk"]
    elif ctx.environment.is_hyprland:
        expected_backends = ["hyprland", "wlr"]
    elif ctx.environment.is_wlroots:
        expected_backends = ["wlr", "hyprland"]
    
    if not expected_backends:
        return None
    
    # Check what's actually configured
    if ctx.portals_config and ctx.portals_config.default_backend:
        configured = ctx.portals_config.default_backend.lower()
        
        if configured not in expected_backends:
            # Map configured to readable name
            expected_str = " or ".join(expected_backends)
            
            def preview_fix():
                return generate_recommended_config(ctx.environment, ctx.backends)
            
            def apply_fix():
                new_config = generate_recommended_config(ctx.environment, ctx.backends)
                return write_portals_config(new_config)
            
            return Finding(
                id="backend_mismatch",
                severity=Severity.WARNING,
                title="Portal Backend Mismatch",
                component="Portal Configuration",
                details=(
                    f"Your desktop environment is {ctx.environment.current_desktop}, but the "
                    f"configured portal backend is '{configured}'.\n\n"
                    f"For {ctx.environment.current_desktop}, you should use the {expected_str} backend. "
                    "Using a mismatched backend can cause screen sharing to fail or show "
                    "incorrect UI elements."
                ),
                evidence=f"Expected: {expected_str}, Configured: {configured}",
                recommended_actions=[
                    Action(
                        id="fix_backend_config",
                        type=ActionType.GENERATE_CONFIG,
                        label="Generate Correct Configuration",
                        description=f"Update portals.conf to use the {expected_str} backend",
                        preview_callback=preview_fix,
                        execute_callback=apply_fix,
                    ),
                ],
            )
    
    return None


def rule_multiple_backends_no_config(ctx: DiagnosticContext) -> Finding | None:
    """Detect multiple backends installed without explicit configuration."""
    if ctx.environment.is_x11:
        return None
    
    if len(ctx.backends) <= 1:
        return None
    
    if ctx.portals_config and ctx.portals_config.default_backend:
        return None
    
    def preview_fix():
        return generate_recommended_config(ctx.environment, ctx.backends)
    
    def apply_fix():
        new_config = generate_recommended_config(ctx.environment, ctx.backends)
        return write_portals_config(new_config)
    
    backend_names = ", ".join(b.name for b in ctx.backends)
    
    return Finding(
        id="multiple_backends_no_config",
        severity=Severity.WARNING,
        title="Multiple Backends Without Configuration",
        component="Portal Configuration",
        details=(
            f"Multiple portal backends are installed ({backend_names}), but no portals.conf "
            "file exists to specify which one to use.\n\n"
            "This can cause unpredictable behavior as the system may select the wrong backend, "
            "leading to screen sharing failures or incorrect UI."
        ),
        evidence=f"Installed backends: {backend_names}, No portals.conf found",
        recommended_actions=[
            Action(
                id="create_portals_conf",
                type=ActionType.GENERATE_CONFIG,
                label="Create portals.conf",
                description=f"Create a configuration file to prefer the correct backend for {ctx.environment.current_desktop}",
                preview_callback=preview_fix,
                execute_callback=apply_fix,
            ),
        ],
    )


def rule_pipewire_not_running(ctx: DiagnosticContext) -> Finding | None:
    """Detect if PipeWire is not running."""
    if ctx.environment.is_x11:
        return None
    
    pw_status = ctx.pipewire_statuses.get("pipewire.service")
    
    if pw_status and pw_status.is_active:
        return None
    
    severity = Severity.ERROR
    if pw_status and pw_status.is_failed:
        evidence = "pipewire.service: failed"
    else:
        evidence = "pipewire.service: not active"
    
    def restart_pipewire():
        return restart_service("pipewire.service")
    
    return Finding(
        id="pipewire_not_running",
        severity=severity,
        title="PipeWire Not Running",
        component="PipeWire",
        details=(
            "PipeWire is not running. Screen sharing on Wayland requires PipeWire to handle "
            "the video streams from the compositor.\n\n"
            "Without PipeWire, applications cannot receive the screen capture data even if "
            "the portal picker works correctly."
        ),
        evidence=evidence,
        recommended_actions=[
            Action(
                id="restart_pipewire",
                type=ActionType.RESTART_SERVICE,
                label="Restart PipeWire",
                description="Restart the PipeWire service",
                command="systemctl --user restart pipewire.service",
                execute_callback=restart_pipewire,
            ),
            Action(
                id="view_pipewire_logs",
                type=ActionType.OPEN_LOGS,
                label="View PipeWire Logs",
                description="View PipeWire logs to diagnose the issue",
                command="journalctl --user -xeu pipewire.service",
            ),
        ],
    )


def rule_no_session_manager(ctx: DiagnosticContext) -> Finding | None:
    """Detect if no PipeWire session manager is running."""
    if ctx.environment.is_x11:
        return None

    # Check for wireplumber or pipewire-media-session
    wp_status = ctx.pipewire_statuses.get("wireplumber.service")
    pms_status = ctx.pipewire_statuses.get("pipewire-media-session.service")

    wp_active = wp_status and wp_status.is_active
    pms_active = pms_status and pms_status.is_active

    if wp_active or pms_active:
        return None

    def restart_wireplumber():
        return restart_service("wireplumber.service")

    return Finding(
        id="no_session_manager",
        severity=Severity.WARNING,
        title="No PipeWire Session Manager Running",
        component="PipeWire",
        details=(
            "No PipeWire session manager (wireplumber or pipewire-media-session) is running. "
            "The session manager handles policy decisions for PipeWire streams.\n\n"
            "This may cause issues with screen sharing if the streams aren't being managed properly."
        ),
        evidence="Neither wireplumber nor pipewire-media-session is active",
        recommended_actions=[
            Action(
                id="restart_wireplumber",
                type=ActionType.RESTART_SERVICE,
                label="Restart WirePlumber",
                description="Restart the WirePlumber session manager",
                command="systemctl --user restart wireplumber.service",
                execute_callback=restart_wireplumber,
            ),
        ],
    )


def rule_flatpak_portal_issues(ctx: DiagnosticContext) -> Finding | None:
    """Detect Flatpak portal configuration issues."""
    import os
    from pathlib import Path

    if ctx.environment.is_x11:
        return None

    # Check if running inside Flatpak
    flatpak_id = os.environ.get("FLATPAK_ID")
    if flatpak_id:
        return Finding(
            id="running_inside_flatpak",
            severity=Severity.INFO,
            title="Running Inside Flatpak Sandbox",
            component="Flatpak",
            details=(
                f"Portal Doctor is running inside a Flatpak sandbox ({flatpak_id}). "
                "Some diagnostics may be limited due to sandboxing.\n\n"
                "For best results, run Portal Doctor directly on the host system."
            ),
            evidence=f"FLATPAK_ID={flatpak_id}",
            recommended_actions=[
                Action(
                    id="run_on_host",
                    type=ActionType.GUIDANCE,
                    label="Run on Host System",
                    description="Run Portal Doctor outside of Flatpak for complete diagnostics",
                ),
            ],
        )

    # Check for Flatpak portal override issues
    flatpak_overrides = Path.home() / ".local/share/flatpak/overrides"
    if flatpak_overrides.exists():
        global_override = flatpak_overrides / "global"
        if global_override.exists():
            try:
                content = global_override.read_text()
                if "talk-name=org.freedesktop.portal" in content and "!" in content:
                    return Finding(
                        id="flatpak_portal_blocked",
                        severity=Severity.WARNING,
                        title="Flatpak Portal Access May Be Blocked",
                        component="Flatpak",
                        details=(
                            "Found a global Flatpak override that may be blocking portal access. "
                            "This can prevent Flatpak applications from using screen sharing.\n\n"
                            "Check your Flatpak overrides if apps inside Flatpak can't share screens."
                        ),
                        evidence=f"Override file: {global_override}",
                        recommended_actions=[
                            Action(
                                id="check_flatpak_overrides",
                                type=ActionType.SHOW_COMMAND,
                                label="View Flatpak Overrides",
                                description="Check the Flatpak permission overrides",
                                command="flatpak override --user --show",
                            ),
                        ],
                    )
            except (OSError, IOError):
                pass

    return None


def rule_xdg_runtime_dir(ctx: DiagnosticContext) -> Finding | None:
    """Check XDG_RUNTIME_DIR exists and has correct permissions."""
    import os
    import stat
    from pathlib import Path

    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")

    if not runtime_dir:
        return Finding(
            id="xdg_runtime_dir_missing",
            severity=Severity.ERROR,
            title="XDG_RUNTIME_DIR Not Set",
            component="Environment",
            details=(
                "The XDG_RUNTIME_DIR environment variable is not set. This directory is "
                "essential for PipeWire sockets and portal communication.\n\n"
                "This usually indicates a problem with your login session or display manager."
            ),
            evidence="XDG_RUNTIME_DIR is not set",
            recommended_actions=[
                Action(
                    id="check_session",
                    type=ActionType.GUIDANCE,
                    label="Check Login Session",
                    description="Make sure you're using a proper display manager (SDDM, GDM, etc.) and not just startx",
                ),
            ],
        )

    runtime_path = Path(runtime_dir)

    if not runtime_path.exists():
        return Finding(
            id="xdg_runtime_dir_not_exists",
            severity=Severity.ERROR,
            title="XDG_RUNTIME_DIR Does Not Exist",
            component="Environment",
            details=(
                f"The runtime directory ({runtime_dir}) does not exist. "
                "This is required for PipeWire and portal communication."
            ),
            evidence=f"Directory missing: {runtime_dir}",
            recommended_actions=[
                Action(
                    id="relogin",
                    type=ActionType.GUIDANCE,
                    label="Re-login to Session",
                    description="Log out and log back in to recreate the runtime directory",
                ),
            ],
        )

    # Check permissions
    try:
        dir_stat = runtime_path.stat()
        mode = dir_stat.st_mode

        # Should be owned by current user and mode 0700
        if dir_stat.st_uid != os.getuid():
            return Finding(
                id="xdg_runtime_dir_wrong_owner",
                severity=Severity.ERROR,
                title="XDG_RUNTIME_DIR Wrong Owner",
                component="Environment",
                details=(
                    f"The runtime directory ({runtime_dir}) is not owned by you. "
                    "This can cause permission issues with PipeWire and portals."
                ),
                evidence=f"Owner UID: {dir_stat.st_uid}, Your UID: {os.getuid()}",
                recommended_actions=[
                    Action(
                        id="relogin",
                        type=ActionType.GUIDANCE,
                        label="Re-login to Session",
                        description="Log out and log back in to fix the runtime directory",
                    ),
                ],
            )

        # Check if it's too permissive (security issue)
        if mode & stat.S_IRWXO:  # Others have any access
            return Finding(
                id="xdg_runtime_dir_insecure",
                severity=Severity.WARNING,
                title="XDG_RUNTIME_DIR Has Insecure Permissions",
                component="Environment",
                details=(
                    f"The runtime directory ({runtime_dir}) has overly permissive access. "
                    "It should only be accessible by you (mode 0700)."
                ),
                evidence=f"Current mode: {oct(mode)}",
                recommended_actions=[
                    Action(
                        id="fix_permissions",
                        type=ActionType.RESTART_SERVICE,
                        label="Fix Permissions",
                        description="Set correct permissions on runtime directory",
                        command=f"chmod 700 {runtime_dir}",
                    ),
                ],
            )
    except OSError:
        pass

    return None


def rule_gtk_use_portal(ctx: DiagnosticContext) -> Finding | None:
    """Check GTK_USE_PORTAL environment variable."""
    import os

    if ctx.environment.is_x11:
        return None

    gtk_use_portal = os.environ.get("GTK_USE_PORTAL")

    # On Wayland, GTK_USE_PORTAL should NOT be set to 0/false
    if gtk_use_portal in ("0", "false", "no"):
        return Finding(
            id="gtk_use_portal_disabled",
            severity=Severity.WARNING,
            title="GTK Portal Usage Disabled",
            component="Environment",
            details=(
                "The GTK_USE_PORTAL environment variable is set to disable portal usage. "
                "This can prevent GTK applications from using native file dialogs and "
                "screen sharing on Wayland.\n\n"
                "Consider removing this environment variable or setting it to 1."
            ),
            evidence=f"GTK_USE_PORTAL={gtk_use_portal}",
            recommended_actions=[
                Action(
                    id="unset_gtk_use_portal",
                    type=ActionType.GUIDANCE,
                    label="Remove GTK_USE_PORTAL",
                    description=(
                        "Remove GTK_USE_PORTAL=0 from your shell profile (~/.bashrc, ~/.profile) "
                        "or environment.d files"
                    ),
                ),
            ],
        )

    return None


def rule_conflicting_backends(ctx: DiagnosticContext) -> Finding | None:
    """Detect multiple portal backends running simultaneously."""
    if ctx.environment.is_x11:
        return None

    # List of backend services that can conflict
    backend_services = {
        "xdg-desktop-portal-kde.service": "KDE",
        "xdg-desktop-portal-gnome.service": "GNOME",
        "xdg-desktop-portal-gtk.service": "GTK",
        "xdg-desktop-portal-wlr.service": "wlroots",
        "xdg-desktop-portal-hyprland.service": "Hyprland",
        "xdg-desktop-portal-lxqt.service": "LXQt",
    }

    running_backends = []
    for service, name in backend_services.items():
        status = ctx.portal_statuses.get(service)
        if status and status.is_active:
            running_backends.append((service, name))

    # Having multiple backends running can cause conflicts
    if len(running_backends) > 1:
        backend_names = ", ".join(name for _, name in running_backends)
        service_names = ", ".join(svc for svc, _ in running_backends)

        return Finding(
            id="conflicting_backends",
            severity=Severity.WARNING,
            title="Multiple Portal Backends Running",
            component="Portal Backend",
            details=(
                f"Multiple portal backends are running simultaneously: {backend_names}.\n\n"
                "This can cause conflicts and unpredictable behavior. Usually only one "
                "backend should be active - the one that matches your desktop environment.\n\n"
                "Consider stopping the extra backends or creating a portals.conf to "
                "explicitly select which one to use."
            ),
            evidence=f"Active services: {service_names}",
            recommended_actions=[
                Action(
                    id="restart_portal",
                    type=ActionType.RESTART_SERVICE,
                    label="Restart Portal Service",
                    description="Restart xdg-desktop-portal to let it select the correct backend",
                    command="systemctl --user restart xdg-desktop-portal.service",
                ),
                Action(
                    id="check_config",
                    type=ActionType.GUIDANCE,
                    label="Create portals.conf",
                    description="Create ~/.config/xdg-desktop-portal/portals.conf to specify the preferred backend",
                ),
            ],
        )

    return None


def rule_pipewire_socket_activation(ctx: DiagnosticContext) -> Finding | None:
    """Detect PipeWire socket active but service not running (socket activation pending)."""
    if ctx.environment.is_x11:
        return None

    pw_service = ctx.pipewire_statuses.get("pipewire.service")
    pw_socket = ctx.pipewire_statuses.get("pipewire.socket")

    # Socket is active but service isn't - might be waiting for activation
    if pw_socket and pw_socket.is_active and pw_service and not pw_service.is_active:
        return Finding(
            id="pipewire_socket_activation_pending",
            severity=Severity.INFO,
            title="PipeWire Using Socket Activation",
            component="PipeWire",
            details=(
                "PipeWire socket is active but the service hasn't started yet. "
                "This is normal with socket activation - the service will start when "
                "an application first tries to use it.\n\n"
                "If you're experiencing issues, you can manually start PipeWire."
            ),
            evidence="pipewire.socket: active, pipewire.service: inactive",
            recommended_actions=[
                Action(
                    id="start_pipewire",
                    type=ActionType.RESTART_SERVICE,
                    label="Start PipeWire Now",
                    description="Manually start the PipeWire service",
                    command="systemctl --user start pipewire.service",
                ),
            ],
        )

    return None


def rule_cosmic_desktop(ctx: DiagnosticContext) -> Finding | None:
    """Detect COSMIC desktop and provide specific guidance."""
    desktop = ctx.environment.current_desktop.lower()
    compositor = (ctx.environment.compositor or "").lower()

    is_cosmic = "cosmic" in desktop or "cosmic" in compositor

    if not is_cosmic:
        return None

    # COSMIC is still in development, provide guidance
    return Finding(
        id="cosmic_desktop_detected",
        severity=Severity.INFO,
        title="COSMIC Desktop Detected",
        component="Desktop Environment",
        details=(
            "You're running the COSMIC desktop environment by System76. "
            "COSMIC is still in active development and may have limited portal support.\n\n"
            "For screen sharing, COSMIC should work with xdg-desktop-portal-cosmic or "
            "xdg-desktop-portal-wlr as a fallback."
        ),
        evidence=f"Desktop: {ctx.environment.current_desktop}, Compositor: {ctx.environment.compositor}",
        recommended_actions=[
            Action(
                id="cosmic_portal_info",
                type=ActionType.GUIDANCE,
                label="COSMIC Portal Info",
                description=(
                    "Check if xdg-desktop-portal-cosmic is available for your distribution. "
                    "If not, xdg-desktop-portal-wlr may work as a fallback."
                ),
            ),
        ],
    )


def rule_dbus_session(ctx: DiagnosticContext) -> Finding | None:
    """Check DBUS_SESSION_BUS_ADDRESS is set."""
    import os

    dbus_addr = os.environ.get("DBUS_SESSION_BUS_ADDRESS")

    if not dbus_addr:
        return Finding(
            id="dbus_session_missing",
            severity=Severity.ERROR,
            title="DBus Session Bus Not Available",
            component="DBus",
            details=(
                "The DBUS_SESSION_BUS_ADDRESS environment variable is not set. "
                "DBus is required for portal communication.\n\n"
                "This usually indicates a problem with your session initialization."
            ),
            evidence="DBUS_SESSION_BUS_ADDRESS is not set",
            recommended_actions=[
                Action(
                    id="check_dbus",
                    type=ActionType.SHOW_COMMAND,
                    label="Check DBus Status",
                    description="Check if DBus user session is running",
                    command="systemctl --user status dbus.service dbus.socket",
                ),
            ],
        )

    return None


# All diagnostic rules
RULES: list[RuleFunc] = [
    rule_x11_session,
    rule_dbus_session,
    rule_xdg_runtime_dir,
    rule_portal_service_not_running,
    rule_no_backend_running,
    rule_backend_mismatch,
    rule_multiple_backends_no_config,
    rule_conflicting_backends,
    rule_pipewire_not_running,
    rule_pipewire_socket_activation,
    rule_no_session_manager,
    rule_gtk_use_portal,
    rule_flatpak_portal_issues,
    rule_cosmic_desktop,
]
RULES: list[RuleFunc] = [
    rule_x11_session,
    rule_portal_service_not_running,
    rule_no_backend_running,
    rule_backend_mismatch,
    rule_multiple_backends_no_config,
    rule_pipewire_not_running,
    rule_no_session_manager,
]


def run_diagnostics(ctx: DiagnosticContext) -> list[Finding]:
    """Run all diagnostic rules and return findings.
    
    Args:
        ctx: Diagnostic context containing all system information
        
    Returns:
        List of findings from all rules
    """
    findings = []
    
    for rule in RULES:
        try:
            finding = rule(ctx)
            if finding:
                findings.append(finding)
        except Exception as e:
            # Don't let one rule failure stop the diagnostics
            findings.append(Finding(
                id=f"rule_error_{rule.__name__}",
                severity=Severity.INFO,
                title=f"Diagnostic Rule Error: {rule.__name__}",
                component="Diagnostics",
                details=f"An error occurred while running diagnostic rule: {e}",
                evidence=str(e),
                recommended_actions=[],
            ))
    
    # Sort by severity (errors first)
    severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    findings.sort(key=lambda f: severity_order.get(f.severity, 99))
    
    return findings


def get_overall_status(findings: list[Finding]) -> tuple[str, str]:
    """Get overall system status based on findings.
    
    Args:
        findings: List of diagnostic findings
        
    Returns:
        Tuple of (status_emoji, status_text)
    """
    has_error = any(f.severity == Severity.ERROR for f in findings)
    has_warning = any(f.severity == Severity.WARNING for f in findings)
    
    if has_error:
        return "❌", "Problems Found"
    elif has_warning:
        return "⚠️", "Warnings"
    else:
        return "✅", "Looks Good"
