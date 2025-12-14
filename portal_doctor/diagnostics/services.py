"""Systemd user service management for Portal Doctor.

Provides functions to check status, restart, and get logs for user services.
"""

import subprocess
from typing import Optional
from functools import lru_cache

from ..models import ServiceStatus


# Cache whether systemd is available
@lru_cache(maxsize=1)
def is_systemd_available() -> bool:
    """Check if systemd --user is available on this system."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return False


def get_systemd_warning() -> Optional[str]:
    """Get a warning message if systemd is not available."""
    if not is_systemd_available():
        return (
            "systemd --user is not available on this system. "
            "Service checks and restarts will not work. "
            "You may need to manage services manually or use a different init system."
        )
    return None


# Portal-related services
PORTAL_SERVICES = [
    "xdg-desktop-portal.service",
    "xdg-desktop-portal-kde.service",
    "xdg-desktop-portal-gnome.service",
    "xdg-desktop-portal-gtk.service",
    "xdg-desktop-portal-wlr.service",
    "xdg-desktop-portal-hyprland.service",
    "xdg-desktop-portal-lxqt.service",
]

# PipeWire-related services (includes sockets)
PIPEWIRE_SERVICES = [
    "pipewire.service",
    "pipewire.socket",
    "wireplumber.service",
    "pipewire-media-session.service",
    "pipewire-pulse.service",
    "pipewire-pulse.socket",
]

# All relevant services
ALL_SERVICES = PORTAL_SERVICES + PIPEWIRE_SERVICES


def check_service_status(service_name: str, timeout: int = 10) -> ServiceStatus:
    """Check the status of a systemd user service.
    
    Args:
        service_name: Name of the systemd service (e.g., 'xdg-desktop-portal.service')
        timeout: Timeout in seconds for subprocess calls
        
    Returns:
        ServiceStatus object with status information
    """
    is_active = _is_service_active(service_name, timeout)
    is_failed = _is_service_failed(service_name, timeout)
    status_output = _get_service_status(service_name, timeout)
    unit_file_state = _get_unit_file_state(service_name, timeout)
    
    return ServiceStatus(
        name=service_name,
        is_active=is_active,
        is_failed=is_failed,
        status_output=status_output,
        unit_file_state=unit_file_state,
    )


def _is_service_active(service_name: str, timeout: int) -> bool:
    """Check if a service is active."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip() == "active"
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False


def _is_service_failed(service_name: str, timeout: int) -> bool:
    """Check if a service has failed."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-failed", service_name],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip() == "failed"
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False


def _get_service_status(service_name: str, timeout: int) -> str:
    """Get the full status output of a service."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "status", service_name, "--no-pager"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        # Return both stdout and stderr, trimmed
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        # Limit output size
        return _trim_output(output, max_lines=30)
    except subprocess.TimeoutExpired:
        return f"Timeout getting status for {service_name}"
    except FileNotFoundError:
        return "systemctl not found"
    except subprocess.SubprocessError as e:
        return f"Error: {e}"


def _get_unit_file_state(service_name: str, timeout: int) -> Optional[str]:
    """Get the unit file state (enabled, disabled, static, etc.)."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-enabled", service_name],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        state = result.stdout.strip()
        if state in ("enabled", "disabled", "static", "masked", "linked"):
            return state
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return None


def restart_service(service_name: str, timeout: int = 30) -> tuple[bool, str]:
    """Restart a systemd user service.
    
    Args:
        service_name: Name of the service to restart
        timeout: Timeout in seconds
        
    Returns:
        Tuple of (success, message)
    """
    try:
        result = subprocess.run(
            ["systemctl", "--user", "restart", service_name],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        if result.returncode == 0:
            return True, f"Successfully restarted {service_name}"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            return False, f"Failed to restart {service_name}: {error_msg}"
            
    except subprocess.TimeoutExpired:
        return False, f"Timeout restarting {service_name}"
    except FileNotFoundError:
        return False, "systemctl not found"
    except subprocess.SubprocessError as e:
        return False, f"Error: {e}"


def restart_multiple_services(service_names: list[str], timeout: int = 30) -> list[tuple[str, bool, str]]:
    """Restart multiple services in order.
    
    Args:
        service_names: List of service names to restart
        timeout: Timeout per service
        
    Returns:
        List of (service_name, success, message) tuples
    """
    results = []
    for service in service_names:
        success, message = restart_service(service, timeout)
        results.append((service, success, message))
    return results


def get_service_logs(service_name: str, since: str = "30 min ago", 
                     max_lines: int = 100, timeout: int = 10) -> str:
    """Get journal logs for a service.
    
    Args:
        service_name: Name of the service
        since: Time specification for --since
        max_lines: Maximum number of lines to return
        timeout: Timeout in seconds
        
    Returns:
        Log output string
    """
    try:
        result = subprocess.run(
            [
                "journalctl", "--user",
                "-u", service_name,
                "--since", since,
                "--no-pager",
                "-n", str(max_lines),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        output = result.stdout
        if not output.strip():
            output = "(No logs found)"
        return output
        
    except subprocess.TimeoutExpired:
        return f"Timeout getting logs for {service_name}"
    except FileNotFoundError:
        return "journalctl not found"
    except subprocess.SubprocessError as e:
        return f"Error: {e}"


def get_active_portal_services() -> list[str]:
    """Get list of currently active portal services."""
    active = []
    for service in PORTAL_SERVICES:
        if _is_service_active(service, timeout=5):
            active.append(service)
    return active


def get_active_pipewire_services() -> list[str]:
    """Get list of currently active PipeWire services."""
    active = []
    for service in PIPEWIRE_SERVICES:
        if _is_service_active(service, timeout=5):
            active.append(service)
    return active


def _trim_output(output: str, max_lines: int = 30) -> str:
    """Trim output to a maximum number of lines."""
    lines = output.split("\n")
    if len(lines) <= max_lines:
        return output
    
    # Keep first and last parts with indication of truncation
    half = max_lines // 2
    return "\n".join(lines[:half]) + f"\n... ({len(lines) - max_lines} lines omitted) ...\n" + "\n".join(lines[-half:])
