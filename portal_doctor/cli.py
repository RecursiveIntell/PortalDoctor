"""CLI interface for Portal Doctor."""

import asyncio
import sys
from argparse import Namespace

from .models import Severity
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
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_colored(text: str, color: str = ""):
    """Print text with optional color."""
    if sys.stdout.isatty():
        print(f"{color}{text}{Colors.RESET}")
    else:
        print(text)


def run_cli(args: Namespace) -> int:
    """Run CLI operations based on arguments."""
    print_colored("Portal Doctor - Wayland Screen Sharing Diagnostics", Colors.BOLD)
    print("=" * 50)
    print()
    
    if args.check:
        return cli_check()
    
    if args.report:
        return cli_report()
    
    if args.test_screencast:
        return cli_screencast()
    
    # Default: run check
    return cli_check()


def cli_check() -> int:
    """Run health check from CLI."""
    print_colored("Running diagnostics...", Colors.BLUE)
    print()
    
    # Detect environment
    env = detect_environment()
    print_colored("System Environment:", Colors.BOLD)
    print(get_environment_summary(env))
    print()
    
    # Check services
    print_colored("Checking services...", Colors.BLUE)
    portal_statuses = {}
    for service in PORTAL_SERVICES:
        portal_statuses[service] = check_service_status(service)
    
    pipewire_statuses = {}
    for service in PIPEWIRE_SERVICES:
        pipewire_statuses[service] = check_service_status(service)
    
    # Print active services
    active_portals = [s for s, st in portal_statuses.items() if st.is_active]
    active_pw = [s for s, st in pipewire_statuses.items() if st.is_active]
    
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
    backends = discover_backends()
    print_colored(f"\nInstalled backends: ", Colors.BOLD, )
    if backends:
        print(", ".join(b.name for b in backends))
    else:
        print_colored("None found", Colors.RED)
    
    # Read config
    portals_config = read_portals_config()
    if portals_config:
        print_colored(f"\nportals.conf: ", Colors.BOLD)
        print(f"default={portals_config.default_backend}")
    
    # Run rules
    ctx = DiagnosticContext(
        environment=env,
        backends=backends,
        portal_statuses=portal_statuses,
        pipewire_statuses=pipewire_statuses,
        portals_config=portals_config,
    )
    
    findings = run_diagnostics(ctx)
    
    print()
    print("=" * 50)
    status_icon, status_text = get_overall_status(findings)
    
    if status_icon == "❌":
        print_colored(f"{status_icon} {status_text}", Colors.RED)
    elif status_icon == "⚠️":
        print_colored(f"{status_icon} {status_text}", Colors.YELLOW)
    else:
        print_colored(f"{status_icon} {status_text}", Colors.GREEN)
    print("=" * 50)
    
    if findings:
        print_colored("\nFindings:", Colors.BOLD)
        print()
        
        severity_colors = {
            Severity.ERROR: Colors.RED,
            Severity.WARNING: Colors.YELLOW,
            Severity.INFO: Colors.BLUE,
        }
        severity_icons = {
            Severity.ERROR: "❌",
            Severity.WARNING: "⚠️",
            Severity.INFO: "ℹ️",
        }
        
        for finding in findings:
            icon = severity_icons.get(finding.severity, "•")
            color = severity_colors.get(finding.severity, "")
            print_colored(f"{icon} [{finding.component}] {finding.title}", color)
            print(f"   {finding.details[:100]}...")
            if finding.recommended_actions:
                action = finding.recommended_actions[0]
                print(f"   → {action.label}")
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
    print()
    print("This will attempt to start a screen capture session.")
    print("You may see a picker dialog appear.")
    print()
    
    try:
        result = asyncio.run(run_screencast_test())
    except Exception as e:
        print_colored(f"❌ Test failed with exception: {e}", Colors.RED)
        return 1
    
    print("=" * 50)
    
    if result.success:
        print_colored("✅ SCREENCAST TEST PASSED", Colors.GREEN)
        print("=" * 50)
        print(f"Step reached: {result.step_reached}")
        if result.pipewire_node_id:
            print(f"PipeWire Node ID: {result.pipewire_node_id}")
        print()
        print("Screen sharing appears to be working correctly!")
        return 0
    else:
        print_colored("❌ SCREENCAST TEST FAILED", Colors.RED)
        print("=" * 50)
        print(f"Step reached: {result.step_reached}")
        if result.error_name:
            print(f"Error: {result.error_name}")
        if result.error_message:
            print(f"Message: {result.error_message}")
        print()
        print("Run 'portal-doctor --check' for diagnostic suggestions.")
        return 1


def main():
    """CLI entry point."""
    from argparse import ArgumentParser
    
    parser = ArgumentParser(
        prog="portal-doctor",
        description="Diagnose and fix Wayland screen-sharing issues",
    )
    
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run health check and print findings",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate and save diagnostic report",
    )
    parser.add_argument(
        "--test-screencast",
        action="store_true",
        help="Run screencast test",
    )
    
    args = parser.parse_args()
    
    # Default to check if no args
    if not (args.check or args.report or args.test_screencast):
        args.check = True
    
    sys.exit(run_cli(args))


if __name__ == "__main__":
    main()
