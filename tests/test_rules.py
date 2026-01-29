"""Tests for the rules engine."""

import os
import pytest
from unittest import mock

from portal_doctor.diagnostics.rules import (
    DiagnosticContext,
    run_diagnostics,
    get_overall_status,
    rule_x11_session,
    rule_portal_service_not_running,
    rule_no_backend_running,
    rule_backend_mismatch,
    rule_multiple_backends_no_config,
    rule_pipewire_not_running,
    rule_no_session_manager,
    rule_flatpak_portal_issues,
    rule_xdg_runtime_dir,
    rule_gtk_use_portal,
    rule_conflicting_backends,
    rule_pipewire_socket_activation,
    rule_cosmic_desktop,
    rule_dbus_session,
)
from portal_doctor.models import (
    EnvironmentInfo, ServiceStatus, PortalBackend, PortalsConfig, Severity
)


def create_mock_context(
    session_type: str = "wayland",
    current_desktop: str = "KDE",
    compositor: str = "KWin",
    portal_active: bool = True,
    backend_active: str = None,
    pipewire_active: bool = True,
    wireplumber_active: bool = True,
    backends: list = None,
    portals_config: PortalsConfig = None,
) -> DiagnosticContext:
    """Create a mock diagnostic context for testing."""
    
    environment = EnvironmentInfo(
        session_type=session_type,
        current_desktop=current_desktop,
        desktop_session=current_desktop.lower(),
        compositor=compositor,
    )
    
    portal_statuses = {
        "xdg-desktop-portal.service": ServiceStatus(
            name="xdg-desktop-portal.service",
            is_active=portal_active,
            is_failed=not portal_active,
            status_output="mock status",
        ),
    }
    
    # Add backend service status
    backend_services = [
        "xdg-desktop-portal-kde.service",
        "xdg-desktop-portal-gnome.service",
        "xdg-desktop-portal-gtk.service",
        "xdg-desktop-portal-wlr.service",
        "xdg-desktop-portal-hyprland.service",
    ]
    
    for service in backend_services:
        is_active = backend_active and service == f"xdg-desktop-portal-{backend_active}.service"
        portal_statuses[service] = ServiceStatus(
            name=service,
            is_active=is_active,
            is_failed=False,
            status_output="mock status",
        )
    
    pipewire_statuses = {
        "pipewire.service": ServiceStatus(
            name="pipewire.service",
            is_active=pipewire_active,
            is_failed=not pipewire_active,
            status_output="mock status",
        ),
        "wireplumber.service": ServiceStatus(
            name="wireplumber.service",
            is_active=wireplumber_active,
            is_failed=False,
            status_output="mock status",
        ),
        "pipewire-media-session.service": ServiceStatus(
            name="pipewire-media-session.service",
            is_active=False,
            is_failed=False,
            status_output="mock status",
        ),
    }
    
    if backends is None:
        backends = [PortalBackend(name="kde"), PortalBackend(name="gtk")]
    
    return DiagnosticContext(
        environment=environment,
        backends=backends,
        portal_statuses=portal_statuses,
        pipewire_statuses=pipewire_statuses,
        portals_config=portals_config,
    )


class TestRuleX11Session:
    """Test Scenario 1: X11 session detection."""
    
    def test_detects_x11_session(self):
        """Test that X11 session is detected and warned about."""
        ctx = create_mock_context(session_type="x11")
        
        finding = rule_x11_session(ctx)
        
        assert finding is not None
        assert finding.id == "x11_session"
        assert finding.severity == Severity.INFO
        assert "X11" in finding.title
    
    def test_no_warning_on_wayland(self):
        """Test that no warning on Wayland session."""
        ctx = create_mock_context(session_type="wayland")
        
        finding = rule_x11_session(ctx)
        
        assert finding is None


class TestRuleBackendMismatch:
    """Test Scenario 2: Portal backend mismatch."""
    
    def test_kde_with_gtk_backend(self):
        """Test detection of KDE with GTK backend configured."""
        ctx = create_mock_context(
            current_desktop="KDE",
            portals_config=PortalsConfig(
                default_backend="gtk",
                raw_content="[preferred]\ndefault=gtk\n",
            ),
        )
        
        finding = rule_backend_mismatch(ctx)
        
        assert finding is not None
        assert finding.id == "backend_mismatch"
        assert finding.severity == Severity.WARNING
    
    def test_kde_with_kde_backend(self):
        """Test no warning when KDE uses KDE backend."""
        ctx = create_mock_context(
            current_desktop="KDE",
            portals_config=PortalsConfig(
                default_backend="kde",
                raw_content="[preferred]\ndefault=kde\n",
            ),
        )
        
        finding = rule_backend_mismatch(ctx)
        
        assert finding is None
    
    def test_gnome_with_kde_backend(self):
        """Test detection of GNOME with KDE backend configured."""
        ctx = create_mock_context(
            current_desktop="GNOME",
            compositor="GNOME Shell",
            portals_config=PortalsConfig(
                default_backend="kde",
                raw_content="[preferred]\ndefault=kde\n",
            ),
        )
        
        finding = rule_backend_mismatch(ctx)
        
        assert finding is not None
        assert finding.id == "backend_mismatch"


class TestRuleBrokenService:
    """Test Scenario 3: Broken xdg-desktop-portal service."""
    
    def test_portal_not_running(self):
        """Test detection of portal service not running."""
        ctx = create_mock_context(portal_active=False)
        
        finding = rule_portal_service_not_running(ctx)
        
        assert finding is not None
        assert finding.id == "portal_not_running"
        assert finding.severity == Severity.ERROR
    
    def test_portal_running(self):
        """Test no finding when portal is running."""
        ctx = create_mock_context(portal_active=True)
        
        finding = rule_portal_service_not_running(ctx)
        
        assert finding is None


class TestRulePipewireNotRunning:
    """Test Scenario 4: Missing PipeWire service."""
    
    def test_pipewire_not_running(self):
        """Test detection of PipeWire not running."""
        ctx = create_mock_context(pipewire_active=False)
        
        finding = rule_pipewire_not_running(ctx)
        
        assert finding is not None
        assert finding.id == "pipewire_not_running"
        assert finding.severity == Severity.ERROR
    
    def test_pipewire_running(self):
        """Test no finding when PipeWire is running."""
        ctx = create_mock_context(pipewire_active=True)
        
        finding = rule_pipewire_not_running(ctx)
        
        assert finding is None
    
    def test_pipewire_not_checked_on_x11(self):
        """Test PipeWire rule is skipped on X11."""
        ctx = create_mock_context(session_type="x11", pipewire_active=False)
        
        finding = rule_pipewire_not_running(ctx)
        
        assert finding is None


class TestRuleWlrootsBackendMismatch:
    """Test Scenario 5: wlroots compositor with KDE backend."""
    
    def test_sway_with_kde_backend(self):
        """Test detection of Sway with KDE backend configured."""
        ctx = create_mock_context(
            current_desktop="sway",
            compositor="Sway",
            backends=[PortalBackend(name="wlr"), PortalBackend(name="kde")],
            portals_config=PortalsConfig(
                default_backend="kde",
                raw_content="[preferred]\ndefault=kde\n",
            ),
        )
        
        finding = rule_backend_mismatch(ctx)
        
        assert finding is not None
        assert finding.id == "backend_mismatch"
    
    def test_hyprland_with_wlr_backend(self):
        """Test no warning when Hyprland uses wlr backend."""
        ctx = create_mock_context(
            current_desktop="Hyprland",
            compositor="Hyprland",
            backends=[PortalBackend(name="hyprland"), PortalBackend(name="wlr")],
            portals_config=PortalsConfig(
                default_backend="wlr",
                raw_content="[preferred]\ndefault=wlr\n",
            ),
        )
        
        finding = rule_backend_mismatch(ctx)
        
        # wlr is acceptable for Hyprland
        assert finding is None


class TestRuleMultipleBackends:
    """Test Scenario 6: Multiple backends without configuration."""
    
    def test_multiple_backends_no_config(self):
        """Test detection of multiple backends without portals.conf."""
        ctx = create_mock_context(
            backends=[
                PortalBackend(name="kde"),
                PortalBackend(name="gtk"),
                PortalBackend(name="gnome"),
            ],
            portals_config=None,
        )
        
        finding = rule_multiple_backends_no_config(ctx)
        
        assert finding is not None
        assert finding.id == "multiple_backends_no_config"
        assert finding.severity == Severity.WARNING
    
    def test_multiple_backends_with_config(self):
        """Test no warning when config exists."""
        ctx = create_mock_context(
            backends=[
                PortalBackend(name="kde"),
                PortalBackend(name="gtk"),
            ],
            portals_config=PortalsConfig(
                default_backend="kde",
                raw_content="[preferred]\ndefault=kde\n",
            ),
        )
        
        finding = rule_multiple_backends_no_config(ctx)
        
        assert finding is None
    
    def test_single_backend_no_config(self):
        """Test no warning with single backend and no config."""
        ctx = create_mock_context(
            backends=[PortalBackend(name="kde")],
            portals_config=None,
        )
        
        finding = rule_multiple_backends_no_config(ctx)
        
        assert finding is None


class TestRunDiagnostics:
    """Tests for the full diagnostics run."""
    
    def test_run_all_rules(self):
        """Test that all rules are executed."""
        ctx = create_mock_context()
        
        findings = run_diagnostics(ctx)
        
        # Should return a list (even if empty)
        assert isinstance(findings, list)
    
    def test_findings_sorted_by_severity(self):
        """Test that findings are sorted by severity."""
        ctx = create_mock_context(
            portal_active=False,  # ERROR
            pipewire_active=False,  # ERROR
            backends=[
                PortalBackend(name="kde"),
                PortalBackend(name="gtk"),
            ],
            portals_config=None,  # WARNING
        )
        
        findings = run_diagnostics(ctx)
        
        if len(findings) > 1:
            # Errors should come before warnings
            severity_order = [f.severity for f in findings]
            error_indices = [i for i, s in enumerate(severity_order) if s == Severity.ERROR]
            warning_indices = [i for i, s in enumerate(severity_order) if s == Severity.WARNING]
            
            if error_indices and warning_indices:
                assert max(error_indices) < min(warning_indices)


class TestGetOverallStatus:
    """Tests for overall status determination."""
    
    def test_error_status(self):
        """Test status with errors."""
        from portal_doctor.models import Finding, Action
        findings = [
            Finding(
                id="test",
                severity=Severity.ERROR,
                title="Test Error",
                details="",
                evidence="",
                component="Test",
            )
        ]
        
        icon, text = get_overall_status(findings)
        
        assert icon == "❌"
        assert "Problem" in text
    
    def test_warning_status(self):
        """Test status with only warnings."""
        from portal_doctor.models import Finding
        findings = [
            Finding(
                id="test",
                severity=Severity.WARNING,
                title="Test Warning",
                details="",
                evidence="",
                component="Test",
            )
        ]
        
        icon, text = get_overall_status(findings)
        
        assert icon == "⚠️"
    
    def test_good_status(self):
        """Test status with no issues."""
        findings = []

        icon, text = get_overall_status(findings)

        assert icon == "✅"
        assert "Good" in text


class TestRuleDbusSession:
    """Test DBus session detection rule."""

    def test_dbus_missing(self):
        """Test detection when DBUS_SESSION_BUS_ADDRESS is missing."""
        ctx = create_mock_context()

        with mock.patch.dict(os.environ, {}, clear=True):
            # Ensure DBUS_SESSION_BUS_ADDRESS is not set
            if "DBUS_SESSION_BUS_ADDRESS" in os.environ:
                del os.environ["DBUS_SESSION_BUS_ADDRESS"]
            finding = rule_dbus_session(ctx)

        assert finding is not None
        assert finding.id == "dbus_session_missing"
        assert finding.severity == Severity.ERROR

    def test_dbus_present(self):
        """Test no finding when DBUS_SESSION_BUS_ADDRESS is set."""
        ctx = create_mock_context()

        with mock.patch.dict(os.environ, {"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus"}):
            finding = rule_dbus_session(ctx)

        assert finding is None


class TestRuleXdgRuntimeDir:
    """Test XDG_RUNTIME_DIR rule."""

    def test_runtime_dir_missing(self):
        """Test detection when XDG_RUNTIME_DIR is missing."""
        ctx = create_mock_context()

        with mock.patch.dict(os.environ, {}, clear=True):
            finding = rule_xdg_runtime_dir(ctx)

        assert finding is not None
        assert finding.id == "xdg_runtime_dir_missing"
        assert finding.severity == Severity.ERROR


class TestRuleGtkUsePortal:
    """Test GTK_USE_PORTAL environment variable rule."""

    def test_gtk_portal_disabled(self):
        """Test detection when GTK_USE_PORTAL is set to 0."""
        ctx = create_mock_context(session_type="wayland")

        with mock.patch.dict(os.environ, {"GTK_USE_PORTAL": "0"}):
            finding = rule_gtk_use_portal(ctx)

        assert finding is not None
        assert finding.id == "gtk_use_portal_disabled"
        assert finding.severity == Severity.WARNING

    def test_gtk_portal_not_set(self):
        """Test no finding when GTK_USE_PORTAL is not set."""
        ctx = create_mock_context(session_type="wayland")

        with mock.patch.dict(os.environ, {}, clear=True):
            # Remove GTK_USE_PORTAL if present
            env = dict(os.environ)
            env.pop("GTK_USE_PORTAL", None)
            with mock.patch.dict(os.environ, env, clear=True):
                finding = rule_gtk_use_portal(ctx)

        assert finding is None

    def test_gtk_portal_x11_ignored(self):
        """Test rule is skipped on X11."""
        ctx = create_mock_context(session_type="x11")

        with mock.patch.dict(os.environ, {"GTK_USE_PORTAL": "0"}):
            finding = rule_gtk_use_portal(ctx)

        assert finding is None


class TestRuleConflictingBackends:
    """Test conflicting backends rule."""

    def test_multiple_backends_running(self):
        """Test detection when multiple backends are running."""
        ctx = create_mock_context(session_type="wayland")

        # Set multiple backends as active
        ctx.portal_statuses["xdg-desktop-portal-kde.service"] = ServiceStatus(
            name="xdg-desktop-portal-kde.service",
            is_active=True,
            is_failed=False,
            status_output="active",
        )
        ctx.portal_statuses["xdg-desktop-portal-gnome.service"] = ServiceStatus(
            name="xdg-desktop-portal-gnome.service",
            is_active=True,
            is_failed=False,
            status_output="active",
        )

        finding = rule_conflicting_backends(ctx)

        assert finding is not None
        assert finding.id == "conflicting_backends"
        assert finding.severity == Severity.WARNING

    def test_single_backend_running(self):
        """Test no finding with single backend."""
        ctx = create_mock_context(session_type="wayland", backend_active="kde")

        finding = rule_conflicting_backends(ctx)

        assert finding is None


class TestRulePipewireSocketActivation:
    """Test PipeWire socket activation rule."""

    def test_socket_active_service_inactive(self):
        """Test detection of socket activation pending state."""
        ctx = create_mock_context(session_type="wayland", pipewire_active=False)

        # Socket is active but service is not
        ctx.pipewire_statuses["pipewire.socket"] = ServiceStatus(
            name="pipewire.socket",
            is_active=True,
            is_failed=False,
            status_output="active",
        )

        finding = rule_pipewire_socket_activation(ctx)

        assert finding is not None
        assert finding.id == "pipewire_socket_activation_pending"
        assert finding.severity == Severity.INFO

    def test_both_active(self):
        """Test no finding when both socket and service are active."""
        ctx = create_mock_context(session_type="wayland", pipewire_active=True)

        ctx.pipewire_statuses["pipewire.socket"] = ServiceStatus(
            name="pipewire.socket",
            is_active=True,
            is_failed=False,
            status_output="active",
        )

        finding = rule_pipewire_socket_activation(ctx)

        assert finding is None


class TestRuleCosmicDesktop:
    """Test COSMIC desktop detection rule."""

    def test_cosmic_detected_desktop(self):
        """Test detection of COSMIC desktop."""
        ctx = create_mock_context(
            session_type="wayland",
            current_desktop="COSMIC",
            compositor="cosmic-comp",
        )

        finding = rule_cosmic_desktop(ctx)

        assert finding is not None
        assert finding.id == "cosmic_desktop_detected"
        assert finding.severity == Severity.INFO

    def test_non_cosmic_desktop(self):
        """Test no finding for non-COSMIC desktop."""
        ctx = create_mock_context(
            session_type="wayland",
            current_desktop="KDE",
            compositor="KWin",
        )

        finding = rule_cosmic_desktop(ctx)

        assert finding is None


class TestRuleFlatpakPortalIssues:
    """Test Flatpak portal issues rule."""

    def test_running_inside_flatpak(self):
        """Test detection when running inside Flatpak."""
        ctx = create_mock_context(session_type="wayland")

        with mock.patch.dict(os.environ, {"FLATPAK_ID": "com.example.app"}):
            finding = rule_flatpak_portal_issues(ctx)

        assert finding is not None
        assert finding.id == "running_inside_flatpak"
        assert finding.severity == Severity.INFO

    def test_not_flatpak(self):
        """Test no finding when not running in Flatpak."""
        ctx = create_mock_context(session_type="wayland")

        with mock.patch.dict(os.environ, {}, clear=True):
            # Ensure FLATPAK_ID is not set
            env = dict(os.environ)
            env.pop("FLATPAK_ID", None)
            with mock.patch.dict(os.environ, env, clear=True):
                finding = rule_flatpak_portal_issues(ctx)

        # Should return None (or possibly a finding about overrides, but not about running in flatpak)
        assert finding is None or finding.id != "running_inside_flatpak"


class TestEnvironmentInfoProperties:
    """Test EnvironmentInfo model properties."""

    def test_is_cosmic(self):
        """Test is_cosmic property."""
        env = EnvironmentInfo(
            session_type="wayland",
            current_desktop="COSMIC",
            desktop_session="cosmic",
            compositor="cosmic-comp",
        )
        assert env.is_cosmic is True

        env2 = EnvironmentInfo(
            session_type="wayland",
            current_desktop="KDE",
            desktop_session="kde",
            compositor="KWin",
        )
        assert env2.is_cosmic is False

    def test_is_lxqt(self):
        """Test is_lxqt property."""
        env = EnvironmentInfo(
            session_type="wayland",
            current_desktop="LXQt",
            desktop_session="lxqt",
            compositor=None,
        )
        assert env.is_lxqt is True

    def test_is_cinnamon(self):
        """Test is_cinnamon property."""
        env = EnvironmentInfo(
            session_type="x11",
            current_desktop="X-Cinnamon",
            desktop_session="cinnamon",
            compositor=None,
        )
        assert env.is_cinnamon is True
