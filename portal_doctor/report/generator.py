"""Diagnostic report generator for Portal Doctor."""

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import (
    DiagnosticReport, EnvironmentInfo, Finding, ServiceStatus,
    PortalBackend, PortalsConfig, ScreenCastTestResult, Severity
)
from ..diagnostics.logs import sanitize_log_output


# Default report output directory
REPORT_DIR = Path.home() / "Documents" / "portal-doctor"


def generate_report(
    environment: EnvironmentInfo,
    services: list[ServiceStatus],
    backends: list[PortalBackend],
    portals_config: Optional[PortalsConfig],
    findings: list[Finding],
    journal_excerpts: dict[str, str],
    screencast_result: Optional[ScreenCastTestResult] = None,
) -> str:
    """Generate a markdown diagnostic report.
    
    Args:
        environment: Detected environment info
        services: List of service statuses
        backends: Discovered portal backends
        portals_config: Current portals.conf content
        findings: Diagnostic findings
        journal_excerpts: Journal logs by service
        screencast_result: Optional screencast test result
        
    Returns:
        Markdown report string
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    sections = [
        _header_section(timestamp),
        _quick_summary_section(findings, services, backends),
        _system_info_section(),
        _environment_section(environment),
        _services_section(services),
        _backends_section(backends, portals_config),
        _findings_section(findings),
    ]
    
    if screencast_result:
        sections.append(_screencast_section(screencast_result))
    
    sections.append(_package_versions_section())
    sections.append(_troubleshooting_section(environment, findings))
    sections.append(_logs_section(journal_excerpts))
    sections.append(_footer_section())
    
    return "\n\n".join(sections)


def _header_section(timestamp: str) -> str:
    """Generate report header."""
    return f"""# 🔬 Portal Doctor Diagnostic Report

**Generated:** {timestamp}  
**Purpose:** Diagnose Wayland screen-sharing issues (Discord, OBS, Teams, browsers, etc.)

---"""


def _quick_summary_section(findings: list[Finding], services: list[ServiceStatus], 
                           backends: list[PortalBackend]) -> str:
    """Generate a quick summary box."""
    has_error = any(f.severity == Severity.ERROR for f in findings)
    has_warning = any(f.severity == Severity.WARNING for f in findings)
    
    # Count issues
    errors = sum(1 for f in findings if f.severity == Severity.ERROR)
    warnings = sum(1 for f in findings if f.severity == Severity.WARNING)
    infos = sum(1 for f in findings if f.severity == Severity.INFO)
    
    # Service counts
    active_services = sum(1 for s in services if s.is_active)
    failed_services = sum(1 for s in services if s.is_failed)
    total_services = len(services)
    
    if has_error:
        status_icon = "❌"
        status_text = "Problems Found"
        status_detail = "Screen sharing may not work correctly"
    elif has_warning:
        status_icon = "⚠️"
        status_text = "Warnings Detected"
        status_detail = "Some issues may affect screen sharing"
    elif findings:
        status_icon = "✅"
        status_text = "Looks Good"
        status_detail = "Minor observations, no critical issues"
    else:
        status_icon = "✅"
        status_text = "All Clear"
        status_detail = "No issues detected"
    
    lines = [
        "## 📊 Quick Summary",
        "",
        f"> {status_icon} **{status_text}** — {status_detail}",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Errors | {errors} |",
        f"| Warnings | {warnings} |",
        f"| Info | {infos} |",
        f"| Services Running | {active_services}/{total_services} |",
        f"| Failed Services | {failed_services} |",
        f"| Installed Backends | {len(backends)} |",
    ]
    
    return "\n".join(lines)


def _system_info_section() -> str:
    """Generate detailed system information."""
    lines = [
        "## 🖥️ System Information",
        "",
        "| Property | Value |",
        "|----------|-------|",
    ]
    
    # OS info
    try:
        with open("/etc/os-release") as f:
            os_info = {}
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    os_info[key] = value.strip('"')
            distro = os_info.get("PRETTY_NAME", "Unknown")
    except:
        distro = platform.platform()
    
    lines.append(f"| Distribution | {distro} |")
    lines.append(f"| Kernel | {platform.release()} |")
    lines.append(f"| Architecture | {platform.machine()} |")
    
    # Display server
    wayland_display = os.environ.get("WAYLAND_DISPLAY", "")
    x_display = os.environ.get("DISPLAY", "")
    if wayland_display:
        lines.append(f"| Wayland Display | {wayland_display} |")
    if x_display:
        lines.append(f"| X11 Display | {x_display} |")
    
    # XDG runtime
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    if xdg_runtime:
        lines.append(f"| XDG Runtime Dir | `{xdg_runtime}` |")
    
    return "\n".join(lines)


def _environment_section(env: EnvironmentInfo) -> str:
    """Generate environment info section."""
    lines = [
        "## 🖼️ Desktop Environment",
        "",
        "| Property | Value |",
        "|----------|-------|",
        f"| Session Type | **{env.session_type.upper()}** |",
        f"| Desktop | {env.current_desktop} |",
    ]
    
    if env.desktop_session and env.desktop_session != env.current_desktop:
        lines.append(f"| Desktop Session | {env.desktop_session} |")
    
    if env.compositor:
        compositor = env.compositor
        if env.compositor_version:
            compositor += f" ({env.compositor_version})"
        lines.append(f"| Compositor | {compositor} |")
    
    # Add relevant environment variables
    lines.append("")
    lines.append("**Relevant Environment Variables:**")
    lines.append("```")
    
    env_vars = [
        "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP", "DESKTOP_SESSION",
        "WAYLAND_DISPLAY", "DISPLAY", "QT_QPA_PLATFORM", "GDK_BACKEND"
    ]
    for var in env_vars:
        value = os.environ.get(var, "(not set)")
        lines.append(f"{var}={value}")
    
    lines.append("```")
    
    return "\n".join(lines)


def _services_section(services: list[ServiceStatus]) -> str:
    """Generate services status section."""
    lines = [
        "## ⚙️ Services Status",
        "",
    ]
    
    # Group by category
    portal_services = [s for s in services if "portal" in s.name.lower()]
    pipewire_services = [s for s in services if "pipewire" in s.name.lower() or "wireplumber" in s.name.lower()]
    other_services = [s for s in services if s not in portal_services and s not in pipewire_services]
    
    def add_service_table(title: str, svcs: list[ServiceStatus]):
        if not svcs:
            return
        lines.append(f"### {title}")
        lines.append("")
        lines.append("| Service | Status | Details |")
        lines.append("|---------|--------|---------|")
        
        for svc in svcs:
            if svc.is_active:
                status = "✅ Active"
            elif svc.is_failed:
                status = "❌ Failed"
            else:
                status = "⚪ Inactive"
            
            name = svc.name.replace(".service", "")
            # Add PID if available
            details = ""
            if hasattr(svc, 'pid') and svc.pid:
                details = f"PID: {svc.pid}"
            
            lines.append(f"| `{name}` | {status} | {details} |")
        
        lines.append("")
    
    add_service_table("Portal Services", portal_services)
    add_service_table("PipeWire/Audio Services", pipewire_services)
    if other_services:
        add_service_table("Other Services", other_services)
    
    return "\n".join(lines)


def _backends_section(backends: list[PortalBackend], config: Optional[PortalsConfig]) -> str:
    """Generate portal backends section."""
    lines = [
        "## 🔌 Portal Backends",
        "",
    ]
    
    if backends:
        lines.append("### Installed Backends")
        lines.append("")
        lines.append("| Backend | Name | UseIn | Portal File |")
        lines.append("|---------|------|-------|-------------|")
        
        for backend in backends:
            use_in = ", ".join(backend.use_in) if backend.use_in else "all"
            portal_file = Path(backend.portal_file).name if backend.portal_file else "unknown"
            lines.append(f"| **{backend.display_name}** | `{backend.name}` | {use_in} | `{portal_file}` |")
    else:
        lines.append("> ⚠️ **No portal backends found!** This is a critical issue.")
        lines.append(">")
        lines.append("> Install a portal backend for your desktop:")
        lines.append("> - KDE: `xdg-desktop-portal-kde`")
        lines.append("> - GNOME: `xdg-desktop-portal-gnome`")
        lines.append("> - wlroots/Sway: `xdg-desktop-portal-wlr`")
        lines.append("> - Hyprland: `xdg-desktop-portal-hyprland`")
    
    lines.append("")
    lines.append("### Configuration (portals.conf)")
    lines.append("")
    
    if config and config.raw_content:
        lines.append(f"📄 File: `{config.file_path}`")
        lines.append("")
        lines.append("```ini")
        lines.append(config.raw_content.strip())
        lines.append("```")
    else:
        lines.append("> ℹ️ No `portals.conf` file found — using system defaults")
        lines.append(">")
        lines.append("> This can cause issues if multiple backends are installed.")
        lines.append("> Create `~/.config/xdg-desktop-portal/portals.conf` to specify your preferred backend.")
    
    return "\n".join(lines)


def _findings_section(findings: list[Finding]) -> str:
    """Generate findings section."""
    lines = [
        "## 🔍 Diagnostic Findings",
        "",
    ]
    
    if not findings:
        lines.append("> ✅ **No issues detected!** Your portal configuration appears healthy.")
        return "\n".join(lines)
    
    severity_icons = {
        Severity.ERROR: "❌",
        Severity.WARNING: "⚠️",
        Severity.INFO: "ℹ️",
    }
    
    severity_labels = {
        Severity.ERROR: "ERROR",
        Severity.WARNING: "WARNING",
        Severity.INFO: "INFO",
    }
    
    for i, finding in enumerate(findings, 1):
        icon = severity_icons.get(finding.severity, "•")
        label = severity_labels.get(finding.severity, "")
        
        lines.append(f"### {icon} Finding #{i}: {finding.title}")
        lines.append("")
        lines.append(f"**Severity:** {label}  ")
        lines.append(f"**Component:** {finding.component}")
        lines.append("")
        lines.append(finding.details)
        lines.append("")
        
        if finding.evidence:
            lines.append("**Evidence:**")
            lines.append(f"```")
            lines.append(finding.evidence)
            lines.append("```")
            lines.append("")
        
        if finding.recommended_actions:
            lines.append("**🔧 Recommended Actions:**")
            lines.append("")
            for j, action in enumerate(finding.recommended_actions, 1):
                lines.append(f"{j}. **{action.label}**")
                lines.append(f"   {action.description}")
                if action.command:
                    lines.append(f"   ```bash")
                    lines.append(f"   {action.command}")
                    lines.append(f"   ```")
            lines.append("")
        
        lines.append("---")
        lines.append("")
    
    return "\n".join(lines)


def _screencast_section(result: ScreenCastTestResult) -> str:
    """Generate screencast test result section."""
    lines = [
        "## 🎬 ScreenCast Test Result",
        "",
    ]
    
    if result.success:
        lines.append("> ✅ **Test Passed** — Screen sharing is working!")
        lines.append("")
        lines.append("| Property | Value |")
        lines.append("|----------|-------|")
        lines.append(f"| Step Reached | {result.step_reached} |")
        if result.pipewire_node_id:
            lines.append(f"| PipeWire Node ID | {result.pipewire_node_id} |")
    else:
        lines.append("> ❌ **Test Failed** — Screen sharing is not working")
        lines.append("")
        lines.append("| Property | Value |")
        lines.append("|----------|-------|")
        lines.append(f"| Step Reached | {result.step_reached} |")
        if result.error_name:
            lines.append(f"| Error | `{result.error_name}` |")
        if result.error_message:
            lines.append(f"| Message | {result.error_message} |")
    
    if result.log_excerpt:
        lines.append("")
        lines.append("**Detailed Log Output:**")
        lines.append("```")
        lines.append(result.log_excerpt)
        lines.append("```")
    
    return "\n".join(lines)


def _package_versions_section() -> str:
    """Generate package versions section."""
    lines = [
        "## 📦 Package Versions",
        "",
        "<details>",
        "<summary>Click to expand version information</summary>",
        "",
    ]
    
    packages_to_check = [
        ("pipewire", ["pipewire", "--version"]),
        ("wireplumber", ["wireplumber", "--version"]),
        ("xdg-desktop-portal", ["xdg-desktop-portal", "--version"]),
    ]
    
    lines.append("| Package | Version |")
    lines.append("|---------|---------|")
    
    for pkg_name, cmd in packages_to_check:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                # Clean up version string
                if version:
                    version = version.replace(pkg_name, "").strip()
                    if not version:
                        version = "(installed)"
                lines.append(f"| `{pkg_name}` | {version} |")
            else:
                lines.append(f"| `{pkg_name}` | ❌ Not found |")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            lines.append(f"| `{pkg_name}` | ❌ Not found |")
    
    lines.append("")
    lines.append("</details>")
    
    return "\n".join(lines)


def _troubleshooting_section(env: EnvironmentInfo, findings: list[Finding]) -> str:
    """Generate troubleshooting tips section."""
    lines = [
        "## 💡 Troubleshooting Tips",
        "",
    ]
    
    tips = []
    
    # Add tips based on environment
    if env.session_type == "x11":
        tips.append("🔹 **X11 Session:** XDG portals are designed for Wayland. Consider switching to a Wayland session for best screen sharing support.")
    
    if env.is_kde:
        tips.append("🔹 **KDE Plasma:** Ensure `xdg-desktop-portal-kde` is installed and running. Restart the portal services after making changes.")
    
    if env.is_gnome:
        tips.append("🔹 **GNOME:** Ensure `xdg-desktop-portal-gnome` is installed. GNOME typically handles portals automatically.")
    
    if env.is_hyprland or env.is_wlroots:
        tips.append("🔹 **wlroots-based compositor:** You may need `xdg-desktop-portal-wlr` or `xdg-desktop-portal-hyprland`. Add `exec-once = dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP` to your config.")
    
    # General tips
    tips.extend([
        "",
        "**General Steps:**",
        "1. Restart portal services: `systemctl --user restart xdg-desktop-portal`",
        "2. Restart PipeWire: `systemctl --user restart pipewire wireplumber`",
        "3. Log out and back in to refresh the session",
        "4. Check if `~/.config/xdg-desktop-portal/portals.conf` exists and is correct",
    ])
    
    if tips:
        lines.extend(tips)
    else:
        lines.append("No specific tips for your configuration.")
    
    return "\n".join(lines)


def _logs_section(journal_excerpts: dict[str, str]) -> str:
    """Generate journal logs section."""
    lines = [
        "## 📜 Journal Logs",
        "",
        "<details>",
        "<summary>Click to expand system logs</summary>",
        "",
    ]
    
    has_logs = False
    for service, logs in journal_excerpts.items():
        if not logs or logs.startswith("(No"):
            continue
        
        has_logs = True
        service_name = service.replace(".service", "")
        lines.append(f"### `{service_name}`")
        lines.append("")
        lines.append("```")
        # Limit log output
        log_lines = logs.split("\n")
        if len(log_lines) > 50:
            lines.extend(log_lines[:25])
            lines.append(f"... ({len(log_lines) - 50} lines omitted) ...")
            lines.extend(log_lines[-25:])
        else:
            lines.append(logs)
        lines.append("```")
        lines.append("")
    
    if not has_logs:
        lines.append("*No relevant log entries found.*")
        lines.append("")
    
    lines.append("</details>")
    
    return "\n".join(lines)


def _footer_section() -> str:
    """Generate report footer."""
    return """---

## 📋 How to Use This Report

1. **Share with support:** Copy this report when asking for help on forums, Discord, or bug trackers
2. **Review findings:** Check the Diagnostic Findings section for specific issues and fixes
3. **Run suggested commands:** Apply the recommended actions in order
4. **Re-test:** After making changes, run Portal Doctor again to verify

---

*Report generated by Portal Doctor v0.1.0*

*For help or to report issues: https://github.com/YOUR-USERNAME/portal-doctor*"""


def save_report(report: str, filename: Optional[str] = None) -> tuple[bool, str]:
    """Save report to a file.
    
    Args:
        report: Report content
        filename: Optional filename, auto-generated if not provided
        
    Returns:
        Tuple of (success, filepath or error message)
    """
    try:
        # Create report directory
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"report-{timestamp}.md"
        
        filepath = REPORT_DIR / filename
        filepath.write_text(report)
        
        return True, str(filepath)
        
    except PermissionError:
        return False, f"Permission denied writing to {REPORT_DIR}"
    except OSError as e:
        return False, f"Error saving report: {e}"


def report_to_clipboard(report: str) -> tuple[bool, str]:
    """Copy report to system clipboard.
    
    Args:
        report: Report content
        
    Returns:
        Tuple of (success, message)
    """
    # Try different clipboard tools
    clipboard_tools = [
        ["wl-copy"],  # Wayland
        ["xclip", "-selection", "clipboard"],  # X11
        ["xsel", "--clipboard", "--input"],  # X11 alternative
    ]
    
    for tool in clipboard_tools:
        try:
            result = subprocess.run(
                tool,
                input=report.encode(),
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True, f"Copied to clipboard using {tool[0]}"
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError):
            continue
    
    return False, "No clipboard tool available (install wl-copy, xclip, or xsel)"
