"""PipeWire status checks for Portal Doctor."""

from ..models import ServiceStatus
from .services import check_service_status, PIPEWIRE_SERVICES


def check_pipewire_status() -> dict[str, ServiceStatus]:
    """Check the status of all PipeWire-related services.
    
    Returns:
        Dictionary mapping service name to ServiceStatus
    """
    statuses = {}
    for service in PIPEWIRE_SERVICES:
        statuses[service] = check_service_status(service)
    return statuses


def is_pipewire_running() -> bool:
    """Check if PipeWire is running.
    
    Returns:
        True if pipewire.service is active
    """
    status = check_service_status("pipewire.service")
    return status.is_active


def is_session_manager_running() -> tuple[bool, str]:
    """Check if a PipeWire session manager is running.
    
    Returns:
        Tuple of (is_running, manager_name)
    """
    # Check WirePlumber first (modern default)
    wp_status = check_service_status("wireplumber.service")
    if wp_status.is_active:
        return True, "wireplumber"
    
    # Check pipewire-media-session (legacy)
    pms_status = check_service_status("pipewire-media-session.service")
    if pms_status.is_active:
        return True, "pipewire-media-session"
    
    return False, ""


def get_pipewire_summary() -> str:
    """Get a summary of PipeWire status.
    
    Returns:
        Human-readable status summary
    """
    lines = []
    
    # Main PipeWire service
    pw_status = check_service_status("pipewire.service")
    if pw_status.is_active:
        lines.append("✅ PipeWire: running")
    elif pw_status.is_failed:
        lines.append("❌ PipeWire: failed")
    else:
        lines.append("⚠️ PipeWire: not running")
    
    # Session manager
    sm_running, sm_name = is_session_manager_running()
    if sm_running:
        lines.append(f"✅ Session Manager: {sm_name}")
    else:
        lines.append("⚠️ Session Manager: not running (need wireplumber or pipewire-media-session)")
    
    # PulseAudio compatibility
    pulse_status = check_service_status("pipewire-pulse.service")
    if pulse_status.is_active:
        lines.append("✅ PulseAudio compatibility: enabled")
    else:
        lines.append("ℹ️ PulseAudio compatibility: not running")
    
    return "\n".join(lines)
