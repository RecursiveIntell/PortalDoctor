"""Main entry point for Portal Doctor."""

import sys
import argparse


def main():
    """Main entry point supporting both GUI and CLI modes."""
    parser = argparse.ArgumentParser(
        prog="portal-doctor",
        description="Diagnose and fix Wayland screen-sharing issues",
    )
    
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run health check and print findings (CLI mode)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate and save diagnostic report (CLI mode)",
    )
    parser.add_argument(
        "--test-screencast",
        action="store_true",
        help="Run screencast test (CLI mode)",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Disable GUI, use CLI only",
    )
    
    args = parser.parse_args()
    
    # CLI mode if any CLI flag is provided
    if args.check or args.report or args.test_screencast or args.no_gui:
        from .cli import run_cli
        return run_cli(args)
    
    # GUI mode
    try:
        from .ui.main_window import run_gui
        return run_gui()
    except ImportError as e:
        print(f"Failed to import GUI components: {e}")
        print("Try running with --check for CLI mode")
        return 1


if __name__ == "__main__":
    sys.exit(main())
