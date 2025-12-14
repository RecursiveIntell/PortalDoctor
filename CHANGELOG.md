# Changelog

All notable changes to Portal Doctor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
