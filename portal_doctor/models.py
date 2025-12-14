"""Data models for Portal Doctor."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Any


class Severity(Enum):
    """Severity level for findings."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ActionType(Enum):
    """Type of recommended action."""
    RESTART_SERVICE = "restart_service"
    GENERATE_CONFIG = "generate_config"
    SHOW_COMMAND = "show_command"
    OPEN_LOGS = "open_logs"
    RESET_PERMISSIONS = "reset_permissions"
    GUIDANCE = "guidance"


@dataclass
class Action:
    """A recommended action to fix a finding."""
    
    id: str
    type: ActionType
    label: str
    description: str
    command: Optional[str] = None
    preview_callback: Optional[Callable[[], str]] = None
    execute_callback: Optional[Callable[[], tuple[bool, str]]] = None
    requires_confirmation: bool = True
    
    def get_preview(self) -> str:
        """Get a preview of what this action will do."""
        if self.preview_callback:
            return self.preview_callback()
        if self.command:
            return f"Will run: {self.command}"
        return self.description


@dataclass
class Finding:
    """A diagnostic finding from the rules engine."""
    
    id: str
    severity: Severity
    title: str
    details: str
    evidence: str
    component: str
    recommended_actions: list[Action] = field(default_factory=list)
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class EnvironmentInfo:
    """Information about the user's desktop environment."""
    
    session_type: str  # wayland, x11, tty
    current_desktop: str  # KDE, GNOME, sway, Hyprland, etc.
    desktop_session: str
    compositor: Optional[str] = None  # KWin, GNOME Shell, Sway, Hyprland
    compositor_version: Optional[str] = None
    
    @property
    def is_wayland(self) -> bool:
        return self.session_type.lower() == "wayland"
    
    @property
    def is_x11(self) -> bool:
        return self.session_type.lower() == "x11"
    
    @property
    def is_kde(self) -> bool:
        return "kde" in self.current_desktop.lower() or "plasma" in self.current_desktop.lower()
    
    @property
    def is_gnome(self) -> bool:
        return "gnome" in self.current_desktop.lower()
    
    @property
    def is_wlroots(self) -> bool:
        compositor_lower = (self.compositor or "").lower()
        desktop_lower = self.current_desktop.lower()
        return any(wm in compositor_lower or wm in desktop_lower 
                   for wm in ["sway", "hyprland", "river", "wayfire", "dwl"])
    
    @property
    def is_hyprland(self) -> bool:
        return "hyprland" in (self.compositor or "").lower() or \
               "hyprland" in self.current_desktop.lower()


@dataclass
class ServiceStatus:
    """Status of a systemd user service."""
    
    name: str
    is_active: bool
    is_failed: bool
    status_output: str
    unit_file_state: Optional[str] = None  # enabled, disabled, static, etc.


@dataclass
class PortalBackend:
    """An installed XDG desktop portal backend."""
    
    name: str  # kde, gnome, gtk, wlr, hyprland
    portal_file: Optional[str] = None  # Path to .portal file
    service_name: Optional[str] = None  # systemd service name
    binary_path: Optional[str] = None
    use_in: list[str] = field(default_factory=list)  # Desktop environments
    
    @property
    def display_name(self) -> str:
        """Human-readable name for the backend."""
        names = {
            "kde": "KDE",
            "gnome": "GNOME",
            "gtk": "GTK",
            "wlr": "wlroots",
            "hyprland": "Hyprland",
            "lxqt": "LXQt",
        }
        return names.get(self.name, self.name.upper())


@dataclass
class PortalsConfig:
    """Contents of portals.conf."""
    
    default_backend: Optional[str] = None
    interface_backends: dict[str, str] = field(default_factory=dict)  # interface -> backend
    raw_content: str = ""
    file_path: Optional[str] = None


@dataclass 
class ScreenCastTestResult:
    """Result of a screencast test."""
    
    success: bool
    step_reached: str  # CreateSession, SelectSources, Start
    error_name: Optional[str] = None
    error_message: Optional[str] = None
    pipewire_node_id: Optional[int] = None
    stream_properties: Optional[dict] = None
    log_excerpt: str = ""


@dataclass
class DiagnosticReport:
    """A complete diagnostic report."""
    
    timestamp: str
    environment: EnvironmentInfo
    services: list[ServiceStatus]
    backends: list[PortalBackend]
    portals_config: Optional[PortalsConfig]
    findings: list[Finding]
    journal_excerpts: dict[str, str]  # service -> log excerpt
    screencast_test_result: Optional[ScreenCastTestResult] = None
