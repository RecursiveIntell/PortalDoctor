"""Environment detection for Portal Doctor.

Detects the user's desktop environment, session type, and compositor.
"""

import os
import subprocess
from typing import Optional

from ..models import EnvironmentInfo


def detect_environment() -> EnvironmentInfo:
    """Detect the current desktop environment and session type."""
    session_type = _detect_session_type()
    current_desktop = _detect_current_desktop()
    desktop_session = os.environ.get("DESKTOP_SESSION", "")
    compositor = _detect_compositor()
    compositor_version = _detect_compositor_version(compositor)
    
    return EnvironmentInfo(
        session_type=session_type,
        current_desktop=current_desktop,
        desktop_session=desktop_session,
        compositor=compositor,
        compositor_version=compositor_version,
    )


def _detect_session_type() -> str:
    """Detect session type from XDG_SESSION_TYPE."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    
    if session_type in ("wayland", "x11", "tty"):
        return session_type
    
    # Fallback: check for Wayland display
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    
    # Fallback: check for X11 display
    if os.environ.get("DISPLAY"):
        return "x11"
    
    return "unknown"


def _detect_current_desktop() -> str:
    """Detect current desktop from environment variables."""
    # XDG_CURRENT_DESKTOP can have multiple values separated by ':'
    current_desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    
    if current_desktop:
        return current_desktop
    
    # Fallback checks
    desktop_session = os.environ.get("DESKTOP_SESSION", "")
    if desktop_session:
        return desktop_session
    
    # Check for specific environment variables
    if os.environ.get("KDE_FULL_SESSION"):
        return "KDE"
    
    if os.environ.get("GNOME_DESKTOP_SESSION_ID"):
        return "GNOME"
    
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "Hyprland"
    
    if os.environ.get("SWAYSOCK"):
        return "sway"
    
    return "unknown"


def _detect_compositor() -> Optional[str]:
    """Detect the running compositor from process list or environment."""
    # Check environment hints first
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "Hyprland"
    
    if os.environ.get("SWAYSOCK"):
        return "Sway"
    
    # Check for KWin
    current_desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "kde" in current_desktop or "plasma" in current_desktop:
        return "KWin"
    
    if "gnome" in current_desktop:
        return "GNOME Shell"
    
    # Try to detect from running processes using pidof
    # (pgrep with regex requires shell=True which we avoid for security)
    compositors_to_check = [
        ("kwin_wayland", "KWin"),
        ("sway", "Sway"),
        ("Hyprland", "Hyprland"),
        ("hyprland", "Hyprland"),
        ("gnome-shell", "GNOME Shell"),
        ("river", "River"),
        ("wayfire", "Wayfire"),
    ]
    
    for process, name in compositors_to_check:
        try:
            result = subprocess.run(
                ["pidof", process],
                capture_output=True,
                timeout=2,
            )
            if result.returncode == 0:
                return name
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            continue
    
    return None


def _detect_compositor_version(compositor: Optional[str]) -> Optional[str]:
    """Try to detect the version of the running compositor."""
    if not compositor:
        return None
    
    version_commands = {
        "Sway": ["sway", "--version"],
        "Hyprland": ["hyprctl", "version"],
        "KWin": ["kwin_wayland", "--version"],
        "GNOME Shell": ["gnome-shell", "--version"],
    }
    
    cmd = version_commands.get(compositor)
    if not cmd:
        return None
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            # Extract version number from output
            if compositor == "Hyprland":
                # hyprctl version outputs multiple lines
                for line in output.split("\n"):
                    if "version" in line.lower():
                        return line.split()[-1] if line.split() else None
            else:
                # Usually the version is the last word
                return output.split()[-1] if output else None
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        pass
    
    return None


def get_environment_summary(env: EnvironmentInfo) -> str:
    """Generate a human-readable summary of the environment."""
    lines = [
        f"Session Type: {env.session_type}",
        f"Desktop: {env.current_desktop}",
    ]
    
    if env.desktop_session and env.desktop_session != env.current_desktop:
        lines.append(f"Desktop Session: {env.desktop_session}")
    
    if env.compositor:
        compositor_str = env.compositor
        if env.compositor_version:
            compositor_str += f" ({env.compositor_version})"
        lines.append(f"Compositor: {compositor_str}")
    
    return "\n".join(lines)
