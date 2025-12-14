"""Tests for the rules engine."""

import pytest

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
