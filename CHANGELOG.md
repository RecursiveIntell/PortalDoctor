# Changelog

All notable changes to Portal Doctor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-01-29

### Added
- **New diagnostic rules:**
  - DBus session bus availability check
  - XDG_RUNTIME_DIR existence and permissions check
  - GTK_USE_PORTAL environment variable detection
  - Flatpak portal issues detection (sandbox detection, override blocking)
  - Multiple conflicting backends running simultaneously detection
  - PipeWire socket activation pending state detection
  - COSMIC desktop environment support
  - LXQt and Cinnamon desktop support

- **CLI improvements:**
  - `--version` / `-V` flag to display version
  - `--verbose` / `-v` flag for detailed output with evidence and commands
  - `--json` flag for JSON output (scripting support)
  - Improved help text with examples
  - Smart text truncation at sentence boundaries

- **GUI improvements:**
  - Full menu bar with File, View, Tools, and Help menus
  - Keyboard shortcuts (Ctrl+R refresh, Ctrl+1-4 tab switching, F5 test, etc.)
  - About dialog with version information
  - Keyboard shortcuts help dialog
  - Quick restart buttons for Portal and PipeWire services in Tools menu
  - Tab tooltips with keyboard shortcuts
  - Improved status bar with version display
  - Better dark theme styling with refined colors
  - Application icon

- **Additional desktop environment support:**
  - COSMIC Desktop (System76) detection and guidance
  - LXQt portal backend support
  - Cinnamon desktop detection

### Changed
- Improved findings display with smarter text truncation
- Enhanced test coverage with tests for all new rules
- Better error handling throughout the codebase
- Cleaner code organization and removed dead code

### Fixed
- Fixed `_generate_diff()` in fixes tab incorrectly treating PortalsConfig as dict
- Fixed unused imports and variables throughout codebase
- Fixed bare except clauses replaced with specific exception types
- Fixed truncation calculation bug in log collection
- Fixed placeholder URL in report footer
- Fixed Finding dataclass missing `__eq__` method (had `__hash__` without `__eq__`)
- Removed duplicate `main()` function in cli.py


## [0.1.0] - 2024-12-13

### Added
- Initial release
- GUI with 4 tabs: Overview, Fixes, Test Screencast, Report
- Environment detection (session type, desktop, compositor)
- Portal backend discovery and configuration
- PipeWire/WirePlumber status checks
- Rules engine for common issues:
  - X11 session detection
  - Portal backend mismatch
  - Broken/stopped services
  - Missing components
  - Multiple backend conflicts
- XDG ScreenCast portal test via DBus
- Diagnostic report generation with sanitization
- portals.conf management with backup/undo
- CLI mode: `--check`, `--report`, `--test-screencast`
