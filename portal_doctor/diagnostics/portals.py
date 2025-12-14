"""Portal backend discovery and configuration management.

Handles discovery of installed portal backends and management of portals.conf.
"""

import os
import re
import shutil
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import PortalBackend, PortalsConfig, EnvironmentInfo


# Standard locations for portal files
PORTAL_DIRS = [
    "/usr/share/xdg-desktop-portal/portals",
    "/usr/local/share/xdg-desktop-portal/portals",
]

# User config paths
USER_CONFIG_DIR = Path.home() / ".config" / "xdg-desktop-portal"
USER_PORTALS_CONF = USER_CONFIG_DIR / "portals.conf"

# Backup directory
BACKUP_DIR = USER_CONFIG_DIR / "backups"


def discover_backends() -> list[PortalBackend]:
    """Discover all installed XDG desktop portal backends.
    
    Returns:
        List of discovered PortalBackend objects
    """
    backends = []
    seen_names = set()
    
    # Scan portal directories for .portal files
    for portal_dir in PORTAL_DIRS:
        if not os.path.isdir(portal_dir):
            continue
            
        try:
            for filename in os.listdir(portal_dir):
                if not filename.endswith(".portal"):
                    continue
                    
                portal_path = os.path.join(portal_dir, filename)
                backend = _parse_portal_file(portal_path)
                
                if backend and backend.name not in seen_names:
                    backends.append(backend)
                    seen_names.add(backend.name)
        except (PermissionError, OSError):
            continue
    
    return backends


def _parse_portal_file(portal_path: str) -> Optional[PortalBackend]:
    """Parse a .portal file and extract backend information.
    
    Args:
        portal_path: Path to the .portal file
        
    Returns:
        PortalBackend object or None if parsing failed
    """
    try:
        config = ConfigParser()
        config.read(portal_path)
        
        if "portal" not in config:
            return None
        
        portal_section = config["portal"]
        
        name = portal_section.get("DBusName", "")
        # Extract short name from DBus name (e.g., org.freedesktop.impl.portal.desktop.kde -> kde)
        if name:
            # Try to get the last part after 'desktop.'
            match = re.search(r"desktop\.(\w+)$", name)
            if match:
                name = match.group(1)
            else:
                # Fallback: use filename
                name = os.path.splitext(os.path.basename(portal_path))[0]
        else:
            name = os.path.splitext(os.path.basename(portal_path))[0]
        
        use_in = []
        if "UseIn" in portal_section:
            use_in = [x.strip() for x in portal_section["UseIn"].split(";") if x.strip()]
        
        return PortalBackend(
            name=name,
            portal_file=portal_path,
            use_in=use_in,
        )
        
    except Exception:
        return None


def read_portals_config(config_path: Optional[Path] = None) -> Optional[PortalsConfig]:
    """Read the portals.conf configuration file.
    
    Args:
        config_path: Path to the config file, defaults to user config
        
    Returns:
        PortalsConfig object or None if file doesn't exist
    """
    path = config_path or USER_PORTALS_CONF
    
    if not path.exists():
        return None
    
    try:
        content = path.read_text()
        config = ConfigParser()
        config.read_string(content)
        
        default_backend = None
        interface_backends = {}
        
        if "preferred" in config:
            default_backend = config["preferred"].get("default")
            
            # Get interface-specific backends
            for key, value in config["preferred"].items():
                if key != "default":
                    interface_backends[key] = value
        
        return PortalsConfig(
            default_backend=default_backend,
            interface_backends=interface_backends,
            raw_content=content,
            file_path=str(path),
        )
        
    except Exception:
        return None


def generate_recommended_config(env: EnvironmentInfo, 
                                 backends: list[PortalBackend]) -> str:
    """Generate a recommended portals.conf based on environment and available backends.
    
    Args:
        env: Current environment information
        backends: List of available backends
        
    Returns:
        Configuration file content as string
    """
    backend_names = {b.name.lower() for b in backends}
    preferred = None
    
    # Determine preferred backend based on environment
    if env.is_hyprland:
        if "hyprland" in backend_names:
            preferred = "hyprland"
        elif "wlr" in backend_names:
            preferred = "wlr"
    elif env.is_wlroots:
        if "wlr" in backend_names:
            preferred = "wlr"
        elif "hyprland" in backend_names:
            preferred = "hyprland"
    elif env.is_kde:
        if "kde" in backend_names:
            preferred = "kde"
    elif env.is_gnome:
        if "gnome" in backend_names:
            preferred = "gnome"
        elif "gtk" in backend_names:
            preferred = "gtk"
    
    # Fallback: if no specific match, use gtk as a common fallback
    if not preferred:
        if "gtk" in backend_names:
            preferred = "gtk"
        elif backends:
            preferred = backends[0].name.lower()
    
    if not preferred:
        return "# No suitable portal backend found\n"
    
    lines = [
        "# Portal Doctor - Generated Configuration",
        f"# Generated: {datetime.now().isoformat()}",
        f"# Detected Environment: {env.current_desktop} ({env.session_type})",
        "",
        "[preferred]",
        f"default={preferred}",
    ]
    
    return "\n".join(lines) + "\n"


def write_portals_config(content: str, config_path: Optional[Path] = None,
                          create_backup: bool = True) -> tuple[bool, str]:
    """Write a new portals.conf file.
    
    Args:
        content: Configuration content to write
        config_path: Path to write to, defaults to user config
        create_backup: Whether to backup existing file first
        
    Returns:
        Tuple of (success, message)
    """
    path = config_path or USER_PORTALS_CONF
    
    try:
        # Create config directory if needed
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Backup existing file if present
        if path.exists() and create_backup:
            backup_result = backup_portals_config(path)
            if not backup_result[0]:
                return False, f"Failed to create backup: {backup_result[1]}"
        
        # Write new content
        path.write_text(content)
        return True, f"Successfully wrote {path}"
        
    except PermissionError:
        return False, f"Permission denied writing to {path}"
    except OSError as e:
        return False, f"Error writing config: {e}"


def backup_portals_config(config_path: Optional[Path] = None) -> tuple[bool, str]:
    """Create a timestamped backup of the portals.conf file.
    
    Args:
        config_path: Path to the config file, defaults to user config
        
    Returns:
        Tuple of (success, backup_path or error message)
    """
    path = config_path or USER_PORTALS_CONF
    
    if not path.exists():
        return False, f"File does not exist: {path}"
    
    try:
        # Create backup directory
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamped backup filename
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_name = f"portals.conf.bak-{timestamp}"
        backup_path = BACKUP_DIR / backup_name
        
        # Copy file
        shutil.copy2(path, backup_path)
        
        return True, str(backup_path)
        
    except PermissionError:
        return False, "Permission denied creating backup"
    except OSError as e:
        return False, f"Error creating backup: {e}"


def restore_portals_config(backup_path: Optional[str] = None) -> tuple[bool, str]:
    """Restore portals.conf from a backup file.
    
    Args:
        backup_path: Path to the backup file, or None to use most recent
        
    Returns:
        Tuple of (success, message)
    """
    try:
        if backup_path:
            source = Path(backup_path)
        else:
            # Find most recent backup
            source = get_latest_backup()
            if not source:
                return False, "No backup files found"
        
        if not source.exists():
            return False, f"Backup file not found: {source}"
        
        # Ensure config directory exists
        USER_PORTALS_CONF.parent.mkdir(parents=True, exist_ok=True)
        
        # Restore from backup
        shutil.copy2(source, USER_PORTALS_CONF)
        
        return True, f"Restored from {source}"
        
    except PermissionError:
        return False, "Permission denied restoring backup"
    except OSError as e:
        return False, f"Error restoring backup: {e}"


def get_latest_backup() -> Optional[Path]:
    """Get the most recent backup file.
    
    Returns:
        Path to the most recent backup or None if no backups exist
    """
    if not BACKUP_DIR.exists():
        return None
    
    backups = sorted(BACKUP_DIR.glob("portals.conf.bak-*"), reverse=True)
    return backups[0] if backups else None


def list_backups() -> list[Path]:
    """List all available backup files.
    
    Returns:
        List of backup file paths, sorted newest first
    """
    if not BACKUP_DIR.exists():
        return []
    
    return sorted(BACKUP_DIR.glob("portals.conf.bak-*"), reverse=True)


def get_config_diff(current: str, new: str) -> str:
    """Generate a unified diff between current and new configuration.
    
    Args:
        current: Current configuration content
        new: New configuration content
        
    Returns:
        Diff string
    """
    import difflib
    
    current_lines = current.splitlines(keepends=True) if current else []
    new_lines = new.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        current_lines,
        new_lines,
        fromfile="current portals.conf",
        tofile="new portals.conf",
        lineterm=""
    )
    
    diff_text = "".join(diff)
    
    if not diff_text.strip():
        return "(No changes)"
    
    return diff_text

