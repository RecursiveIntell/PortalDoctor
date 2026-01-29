"""CLI interface for Portal Doctor."""

import asyncio
import json
import sys
from argparse import Namespace
from typing import Any

from . import __version__
from .models import Severity, Finding, EnvironmentInfo, ServiceStatus, PortalBackend
from .diagnostics.env_detect import detect_environment, get_environment_summary
from .diagnostics.services import check_service_status, PORTAL_SERVICES, PIPEWIRE_SERVICES
from .diagnostics.portals import discover_backends, read_portals_config
from .diagnostics.logs import collect_journal_logs, get_relevant_log_services
from .diagnostics.rules import DiagnosticContext, run_diagnostics, get_overall_status
from .screencast_test.xdg_screencast import run_screencast_test
from .report.generator import generate_report, save_report


# ANSI color codes
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


# Global verbose flag
_verbose = False
_json_output = False


def print_colored(text: str, color: str = ""):
    """Print text with optional color."""
    if _json_output:
        return  # Suppress text output in JSON mode
    if sys.stdout.isatty():
        print(f"{color}{text}{Colors.RESET}")
    else:
        print(text)


def print_verbose(text: str, color: str = ""):
    """Print text only in verbose mode."""
    if _verbose:
        print_colored(f"  {text}", color or Colors.DIM)


def run_cli(args: Namespace) -> int:
    """Run CLI operations based on arguments."""
    global _verbose, _json_output
    _verbose = getattr(args, 'verbose', False)
    _json_output = getattr(args, 'json', False)

    if not _json_output:
        print_colored(f"Portal Doctor v{__version__} - Wayland Screen Sharing Diagnostics", Colors.BOLD)
        print("=" * 60)
        print()

    if args.check:
        return cli_check()

    if args.report:
        return cli_report()

    if args.test_screencast:
        return cli_screencast()

    # Default: run check
    return cli_check()


def _finding_to_dict(finding: Finding) -> dict[str, Any]:
    """Convert a Finding to a dictionary for JSON output."""
    return {
        "id": finding.id,
        "severity": finding.severity.value,
        "title": finding.title,
        "component": finding.component,
        "details": finding.details,
        "evidence": finding.evidence,
        "actions": [
            {
                "id": action.id,
                "label": action.label,
                "description": action.description,
                "command": action.command,
            }
            for action in finding.recommended_actions
        ],
    }


def _env_to_dict(env: EnvironmentInfo) -> dict[str, Any]:
    """Convert EnvironmentInfo to a dictionary for JSON output."""
    return {
        "session_type": env.session_type,
        "current_desktop": env.current_desktop,
        "desktop_session": env.desktop_session,
        "compositor": env.compositor,
        "compositor_version": env.compositor_version,
        "is_wayland": env.is_wayland,
        "is_x11": env.is_x11,
        "is_kde": env.is_kde,
        "is_gnome": env.is_gnome,
        "is_wlroots": env.is_wlroots,
        "is_hyprland": env.is_hyprland,
    }


def _service_to_dict(status: ServiceStatus) -> dict[str, Any]:
    """Convert ServiceStatus to a dictionary for JSON output."""
    return {
        "name": status.name,
        "is_active": status.is_active,
        "is_failed": status.is_failed,
        "unit_file_state": status.unit_file_state,
    }


def _backend_to_dict(backend: PortalBackend) -> dict[str, Any]:
    """Convert PortalBackend to a dictionary for JSON output."""
    return {
        "name": backend.name,
        "display_name": backend.display_name,
        "portal_file": backend.portal_file,
        "use_in": backend.use_in,
    }


def cli_check() -> int:
    """Run health check from CLI."""
    print_colored("Running diagnostics...", Colors.BLUE)
    print()

    # Detect environment
    print_verbose("Detecting environment...")
    env = detect_environment()
    print_colored("System Environment:", Colors.BOLD)
    if not _json_output:
        print(get_environment_summary(env))
        print()

    # Check services
    print_colored("Checking services...", Colors.BLUE)
    portal_statuses = {}
    for service in PORTAL_SERVICES:
        print_verbose(f"Checking {service}...")
        portal_statuses[service] = check_service_status(service)

    pipewire_statuses = {}
    for service in PIPEWIRE_SERVICES:
        print_verbose(f"Checking {service}...")
        pipewire_statuses[service] = check_service_status(service)

    # Print active services
    active_portals = [s for s, st in portal_statuses.items() if st.is_active]
    active_pw = [s for s, st in pipewire_statuses.items() if st.is_active]

    if not _json_output:
        print_colored("\nActive Portal Services:", Colors.BOLD)
        if active_portals:
            for s in active_portals:
                print(f"  ✅ {s}")
        else:
            print_colored("  ❌ No portal services running", Colors.RED)

        print_colored("\nActive PipeWire Services:", Colors.BOLD)
        if active_pw:
            for s in active_pw:
                print(f"  ✅ {s}")
        else:
            print_colored("  ❌ No PipeWire services running", Colors.RED)

    # Discover backends
    print_verbose("Discovering backends...")
    backends = discover_backends()
    if not _json_output:
        print_colored(f"\nInstalled backends: ", Colors.BOLD)
        if backends:
            print(", ".join(b.name for b in backends))
        else:
            print_colored("None found", Colors.RED)

    # Read config
    portals_config = read_portals_config()
    if portals_config and not _json_output:
        print_colored(f"\nportals.conf: ", Colors.BOLD)
        print(f"default={portals_config.default_backend}")

    # Run rules
    print_verbose("Running diagnostic rules...")
    ctx = DiagnosticContext(
        environment=env,
        backends=backends,
        portal_statuses=portal_statuses,
        pipewire_statuses=pipewire_statuses,
        portals_config=portals_config,
    )

    findings = run_diagnostics(ctx)

    status_icon, status_text = get_overall_status(findings)

    # JSON output mode
    if _json_output:
        output = {
            "version": __version__,
            "status": {
                "icon": status_icon,
                "text": status_text,
                "has_errors": status_icon == "❌",
                "has_warnings": status_icon == "⚠️",
            },
            "environment": _env_to_dict(env),
            "services": {
                "portal": {name: _service_to_dict(st) for name, st in portal_statuses.items()},
                "pipewire": {name: _service_to_dict(st) for name, st in pipewire_statuses.items()},
            },
            "backends": [_backend_to_dict(b) for b in backends],
            "config": {
                "default_backend": portals_config.default_backend if portals_config else None,
                "file_path": portals_config.file_path if portals_config else None,
            },
            "findings": [_finding_to_dict(f) for f in findings],
            "summary": {
                "total_findings": len(findings),
                "errors": sum(1 for f in findings if f.severity == Severity.ERROR),
                "warnings": sum(1 for f in findings if f.severity == Severity.WARNING),
                "info": sum(1 for f in findings if f.severity == Severity.INFO),
            },
        }
        print(json.dumps(output, indent=2))
        return 0 if status_icon != "❌" else 1

    # Normal text output
    print()
    print("=" * 60)
    if status_icon == "❌":
        print_colored(f"{status_icon} {status_text}", Colors.RED)
    elif status_icon == "⚠️":
        print_colored(f"{status_icon} {status_text}", Colors.YELLOW)
    else:
        print_colored(f"{status_icon} {status_text}", Colors.GREEN)
    print("=" * 60)

    if findings:
        print_colored("\nFindings:", Colors.BOLD)
        print()

        severity_colors = {
            Severity.ERROR: Colors.RED,
            Severity.WARNING: Colors.YELLOW,
            Severity.INFO: Colors.CYAN,
        }
        severity_icons = {
            Severity.ERROR: "❌",
            Severity.WARNING: "⚠️",
            Severity.INFO: "ℹ️",
        }

        for i, finding in enumerate(findings, 1):
            icon = severity_icons.get(finding.severity, "•")
            color = severity_colors.get(finding.severity, "")
            print_colored(f"{icon} [{finding.component}] {finding.title}", color)

            # Smart truncation - find a good break point (unless verbose)
            details = finding.details
            if not _verbose and len(details) > 120:
                # Try to break at a sentence or newline
                truncate_at = details.find('\n', 0, 120)
                if truncate_at == -1:
                    truncate_at = details.rfind('. ', 0, 120)
                if truncate_at == -1:
                    truncate_at = details.rfind(' ', 0, 120)
                if truncate_at == -1:
                    truncate_at = 120
                details = details[:truncate_at + 1].strip() + "..."
            print(f"   {details}")

            if _verbose and finding.evidence:
                print_colored(f"   Evidence: {finding.evidence}", Colors.DIM)

            if finding.recommended_actions:
                action = finding.recommended_actions[0]
                print_colored(f"   → {action.label}", Colors.CYAN)
                if _verbose and action.command:
                    print_colored(f"     $ {action.command}", Colors.DIM)
            print()
    else:
        print_colored("\n✅ No issues detected!", Colors.GREEN)

    return 0 if status_icon != "❌" else 1


def cli_report() -> int:
    """Generate report from CLI."""
    print_colored("Generating diagnostic report...", Colors.BLUE)
    
    # Gather all data
    env = detect_environment()
    
    portal_statuses = {}
    for service in PORTAL_SERVICES:
        portal_statuses[service] = check_service_status(service)
    
    pipewire_statuses = {}
    for service in PIPEWIRE_SERVICES:
        pipewire_statuses[service] = check_service_status(service)
    
    backends = discover_backends()
    portals_config = read_portals_config()
    
    ctx = DiagnosticContext(
        environment=env,
        backends=backends,
        portal_statuses=portal_statuses,
        pipewire_statuses=pipewire_statuses,
        portals_config=portals_config,
    )
    
    findings = run_diagnostics(ctx)
    
    # Collect logs
    services = get_relevant_log_services()
    journal_excerpts = collect_journal_logs(services)
    
    # Generate report
    services_list = list(portal_statuses.values()) + list(pipewire_statuses.values())
    
    report = generate_report(
        environment=env,
        services=services_list,
        backends=backends,
        portals_config=portals_config,
        findings=findings,
        journal_excerpts=journal_excerpts,
    )
    
    # Save report
    success, result = save_report(report)
    
    if success:
        print_colored(f"✅ Report saved to: {result}", Colors.GREEN)
    else:
        print_colored(f"❌ Failed to save: {result}", Colors.RED)
        # Print to stdout as fallback
        print()
        print(report)
    
    return 0


def cli_screencast() -> int:
    """Run screencast test from CLI."""
    print_colored("Running XDG ScreenCast test...", Colors.BLUE)
    if not _json_output:
        print()
        print("This will attempt to start a screen capture session.")
        print("You may see a picker dialog appear.")
        print()

    try:
        result = asyncio.run(run_screencast_test())
    except Exception as e:
        if _json_output:
            output = {
                "success": False,
                "step_reached": "Initialize",
                "error_name": type(e).__name__,
                "error_message": str(e),
            }
            print(json.dumps(output, indent=2))
        else:
            print_colored(f"❌ Test failed with exception: {e}", Colors.RED)
        return 1

    # JSON output
    if _json_output:
        output = {
            "success": result.success,
            "step_reached": result.step_reached,
            "error_name": result.error_name,
            "error_message": result.error_message,
            "pipewire_node_id": result.pipewire_node_id,
            "stream_properties": result.stream_properties,
        }
        print(json.dumps(output, indent=2))
        return 0 if result.success else 1

    # Normal text output
    print("=" * 60)

    if result.success:
        print_colored("✅ SCREENCAST TEST PASSED", Colors.GREEN)
        print("=" * 60)
        print(f"Step reached: {result.step_reached}")
        if result.pipewire_node_id:
            print(f"PipeWire Node ID: {result.pipewire_node_id}")
        if _verbose and result.stream_properties:
            print(f"Stream properties: {result.stream_properties}")
        print()
        print("Screen sharing appears to be working correctly!")
        return 0
    else:
        print_colored("❌ SCREENCAST TEST FAILED", Colors.RED)
        print("=" * 60)
        print(f"Step reached: {result.step_reached}")
        if result.error_name:
            print(f"Error: {result.error_name}")
        if result.error_message:
            print(f"Message: {result.error_message}")
        if _verbose and result.log_excerpt:
            print()
            print_colored("Log excerpt:", Colors.DIM)
            print(result.log_excerpt)
        print()
        print("Run 'portal-doctor --check' for diagnostic suggestions.")
        return 1


