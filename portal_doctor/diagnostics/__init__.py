"""Diagnostics module for Portal Doctor."""

from .env_detect import detect_environment
from .services import (
    check_service_status,
    restart_service,
    get_service_logs,
    PORTAL_SERVICES,
    PIPEWIRE_SERVICES,
)
from .portals import (
    discover_backends,
    read_portals_config,
    write_portals_config,
    backup_portals_config,
    restore_portals_config,
    generate_recommended_config,
)
from .pipewire import check_pipewire_status
from .logs import collect_journal_logs, sanitize_log_output
from .rules import run_diagnostics, RULES

__all__ = [
    "detect_environment",
    "check_service_status",
    "restart_service",
    "get_service_logs",
    "PORTAL_SERVICES",
    "PIPEWIRE_SERVICES",
    "discover_backends",
    "read_portals_config",
    "write_portals_config",
    "backup_portals_config",
    "restore_portals_config",
    "generate_recommended_config",
    "check_pipewire_status",
    "collect_journal_logs",
    "sanitize_log_output",
    "run_diagnostics",
    "RULES",
]
