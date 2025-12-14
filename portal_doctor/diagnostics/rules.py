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


# All diagnostic rules
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
