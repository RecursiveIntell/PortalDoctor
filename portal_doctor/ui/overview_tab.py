"""Overview/Health Check tab for Portal Doctor."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QGroupBox, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtGui import QFont

from ..models import Finding, Severity, EnvironmentInfo, ServiceStatus, PortalBackend
from ..diagnostics.env_detect import detect_environment
from ..diagnostics.services import check_service_status, PORTAL_SERVICES, PIPEWIRE_SERVICES, is_systemd_available, get_systemd_warning
from ..diagnostics.portals import discover_backends, read_portals_config
from ..diagnostics.pipewire import check_pipewire_status
from ..diagnostics.logs import collect_journal_logs, get_relevant_log_services
from ..diagnostics.rules import DiagnosticContext, run_diagnostics, get_overall_status


class DiagnosticsWorker(QObject):
    """Worker to run diagnostics in a background thread."""
    
    finished = Signal(object)  # Emits diagnostic data dict
    error = Signal(str)
    progress = Signal(str)  # Progress updates
    
    def run(self):
        """Run diagnostics including screencast test."""
        try:
            self.progress.emit("Detecting environment...")
            # Detect environment
            environment = detect_environment()
            
            # Skip screencast test on X11
            run_screencast_test = not environment.is_x11
            
            # Check for systemd availability
            systemd_available = is_systemd_available()
            systemd_warning = get_systemd_warning()
            
            self.progress.emit("Checking services...")
            # Check services (will return empty/inactive if systemd not available)
            portal_statuses = {}
            for service in PORTAL_SERVICES:
                portal_statuses[service] = check_service_status(service)
            
            pipewire_statuses = {}
            for service in PIPEWIRE_SERVICES:
                pipewire_statuses[service] = check_service_status(service)
            
            self.progress.emit("Discovering backends...")
            # Discover backends
            backends = discover_backends()
            
            # Read portals.conf
            portals_config = read_portals_config()
            
            # Create diagnostic context and run rules
            ctx = DiagnosticContext(
                environment=environment,
                backends=backends,
                portal_statuses=portal_statuses,
                pipewire_statuses=pipewire_statuses,
                portals_config=portals_config,
            )
            
            findings = run_diagnostics(ctx)
            
            # Run screencast test to verify actual functionality
            screencast_result = None
            screencast_findings = []
            if run_screencast_test:
                self.progress.emit("Testing screen sharing...")
                screencast_result, screencast_findings = self._run_screencast_test()
                findings = screencast_findings + findings
            
            self.progress.emit("Collecting logs...")
            # Collect journal logs
            services = get_relevant_log_services()
            journal_excerpts = collect_journal_logs(services)
            
            # Package all data
            data = {
                "environment": environment,
                "portal_statuses": portal_statuses,
                "pipewire_statuses": pipewire_statuses,
                "backends": backends,
                "portals_config": portals_config,
                "findings": findings,
                "journal_excerpts": journal_excerpts,
                "context": ctx,
                "screencast_result": screencast_result,
                "systemd_warning": systemd_warning,
            }
            
            self.finished.emit(data)
            
        except Exception as e:
            self.error.emit(str(e))
    
    def _run_screencast_test(self):
        """Run a quick screencast test and generate findings."""
        import asyncio
        from ..screencast_test.xdg_screencast import run_screencast_test
        from ..models import Finding, Severity, Action, ActionType
        
        findings = []
        
        try:
            # Run the test with a short timeout for initial check
            result = asyncio.run(run_screencast_test())
            
            if result.success:
                # Add success finding
                findings.append(Finding(
                    id="screencast_verified",
                    severity=Severity.INFO,
                    title="Screen Sharing Verified",
                    component="ScreenCast",
                    details="The screencast test completed successfully. Screen sharing should work.",
                    evidence=f"PipeWire node: {result.pipewire_node_id}" if result.pipewire_node_id else "Test passed",
                    recommended_actions=[],
                ))
            else:
                # Generate failure finding based on step
                findings.extend(self._generate_screencast_findings(result))
            
            return result, findings
            
        except Exception as e:
            # Test failed to run
            findings.append(Finding(
                id="screencast_test_error",
                severity=Severity.WARNING,
                title="Screencast Test Could Not Run",
                component="ScreenCast",
                details=f"The automatic screencast test encountered an error: {e}",
                evidence=str(e),
                recommended_actions=[
                    Action(
                        id="manual_test",
                        type=ActionType.GUIDANCE,
                        label="Run Manual Test",
                        description="Go to the Test Screencast tab to run a manual test",
                    ),
                ],
            ))
            return None, findings
    
    def _generate_screencast_findings(self, result):
        """Generate findings from screencast test failure."""
        from ..models import Finding, Severity, Action, ActionType
        
        findings = []
        error_msg = result.error_message or ""
        error_name = result.error_name or ""
        step = result.step_reached
        
        if step == "GetPortal":
            if "power-saver" in error_msg.lower():
                findings.append(Finding(
                    id="screencast_dbus_bug",
                    severity=Severity.WARNING,
                    title="DBus Library Compatibility Issue",
                    component="Portal DBus",
                    details="A dbus-next library bug was detected. Screen sharing may still work in applications.",
                    evidence=f"{error_name}: {error_msg}",
                    recommended_actions=[
                        Action(
                            id="test_apps",
                            type=ActionType.GUIDANCE,
                            label="Test Real Apps",
                            description="Try screen sharing in Discord, OBS, or a browser",
                        ),
                    ],
                ))
            else:
                findings.append(Finding(
                    id="screencast_portal_issue",
                    severity=Severity.ERROR,
                    title="Portal Connection Failed",
                    component="Portal Service",
                    details="Could not connect to the screen sharing portal.",
                    evidence=f"{error_name}: {error_msg}",
                    recommended_actions=[
                        Action(
                            id="restart_portal",
                            type=ActionType.RESTART_SERVICE,
                            label="Restart Portal",
                            description="Restart portal services",
                            command="systemctl --user restart xdg-desktop-portal.service",
                        ),
                    ],
                ))
        
        elif step in ["CreateSession", "SelectSources"]:
            if "interface" in error_msg.lower() or "interfacenotfound" in error_name.lower():
                findings.append(Finding(
                    id="screencast_no_interface",
                    severity=Severity.ERROR,
                    title="ScreenCast Not Supported",
                    component="Portal Backend",
                    details=(
                        "Your portal backend doesn't support ScreenCast. "
                        "Install the correct backend for your desktop environment."
                    ),
                    evidence=f"{error_name}: {error_msg}",
                    recommended_actions=[
                        Action(
                            id="check_backends",
                            type=ActionType.SHOW_COMMAND,
                            label="Check Installed Portals",
                            description="See what portal backends are installed",
                            command="systemctl --user list-units 'xdg-desktop-portal*' --all",
                        ),
                    ],
                ))
            else:
                findings.append(Finding(
                    id="screencast_session_issue",
                    severity=Severity.ERROR,
                    title="Screen Capture Session Failed",
                    component="Portal Backend",
                    details="Failed to create a screen capture session.",
                    evidence=f"Step: {step}, Error: {error_name}: {error_msg}",
                    recommended_actions=[
                        Action(
                            id="restart_all",
                            type=ActionType.RESTART_SERVICE,
                            label="Restart Services",
                            description="Restart all portal services",
                            command="systemctl --user restart xdg-desktop-portal.service pipewire.service",
                        ),
                    ],
                ))
        
        elif step == "Start":
            findings.append(Finding(
                id="screencast_stream_issue",
                severity=Severity.ERROR,
                title="Stream Start Failed",
                component="PipeWire",
                details="Screen was selected but stream couldn't start. PipeWire may have issues.",
                evidence=f"{error_name}: {error_msg}",
                recommended_actions=[
                    Action(
                        id="restart_pw",
                        type=ActionType.RESTART_SERVICE,
                        label="Restart PipeWire",
                        description="Restart PipeWire stack",
                        command="systemctl --user restart pipewire.service wireplumber.service",
                    ),
                ],
            ))
        
        else:
            findings.append(Finding(
                id="screencast_issue",
                severity=Severity.WARNING,
                title="Screencast Test Issue",
                component="Screen Sharing",
                details=f"The screencast test encountered an issue at step: {step}",
                evidence=f"{error_name}: {error_msg}",
                recommended_actions=[
                    Action(
                        id="manual_test",
                        type=ActionType.GUIDANCE,
                        label="Run Manual Test",
                        description="Go to Test Screencast tab for detailed testing",
                    ),
                ],
            ))
        
        return findings


class OverviewTab(QWidget):
    """Overview tab showing health check results."""
    
    findings_updated = Signal(list)  # Emits list of findings
    data_ready = Signal(object)  # Emits all diagnostic data
    
    def __init__(self):
        super().__init__()
        
        self.diagnostic_data = None
        self.worker_thread = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the tab UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Status banner
        self.status_frame = QFrame()
        self.status_frame.setFrameStyle(QFrame.StyledPanel)
        self.status_frame.setStyleSheet("""
            QFrame {
                background-color: #333;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        status_layout = QHBoxLayout(self.status_frame)
        
        self.status_icon = QLabel("⏳")
        self.status_icon.setFont(QFont("", 48))
        self.status_icon.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.status_icon)
        
        self.status_text = QLabel("Running diagnostics...")
        self.status_text.setFont(QFont("", 18, QFont.Bold))
        self.status_text.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.status_text, 1)
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.run_diagnostics)
        status_layout.addWidget(self.refresh_btn)
        
        layout.addWidget(self.status_frame)
        
        # Environment info group
        env_group = QGroupBox("System Environment")
        env_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
            }
        """)
        env_layout = QGridLayout(env_group)
        
        self.env_labels = {}
        env_fields = [
            ("session_type", "Session Type:"),
            ("desktop", "Desktop:"),
            ("compositor", "Compositor:"),
            ("pipewire", "PipeWire:"),
            ("portal", "Portal Service:"),
            ("backend", "Active Backend:"),
        ]
        
        for i, (key, label) in enumerate(env_fields):
            label_widget = QLabel(label)
            label_widget.setStyleSheet("font-weight: bold;")
            value_widget = QLabel("-")
            value_widget.setStyleSheet("color: #aaa;")
            self.env_labels[key] = value_widget
            
            row = i // 3
            col = (i % 3) * 2
            env_layout.addWidget(label_widget, row, col)
            env_layout.addWidget(value_widget, row, col + 1)
        
        layout.addWidget(env_group)
        
        # Findings table
        findings_label = QLabel("Diagnostic Findings")
        findings_label.setFont(QFont("", 12, QFont.Bold))
        layout.addWidget(findings_label)
        
        self.findings_table = QTableWidget()
        self.findings_table.setColumnCount(4)
        self.findings_table.setHorizontalHeaderLabels([
            "Severity", "Component", "Finding", "Suggested Action"
        ])
        self.findings_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.findings_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.findings_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.findings_table.setAlternatingRowColors(True)
        self.findings_table.verticalHeader().setVisible(False)
        
        layout.addWidget(self.findings_table, 1)
    
    def run_diagnostics(self):
        """Run diagnostics in a background thread."""
        self.status_icon.setText("⏳")
        self.status_text.setText("Running diagnostics...")
        self.refresh_btn.setEnabled(False)
        
        # Create worker and thread
        self.worker = DiagnosticsWorker()
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        
        # Connect signals
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_diagnostics_complete)
        self.worker.error.connect(self._on_diagnostics_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        
        # Start thread
        self.worker_thread.start()
    
    def _on_progress(self, message):
        """Update status text with progress."""
        self.status_text.setText(message)
    
    def _on_diagnostics_complete(self, data):
        """Handle diagnostics completion."""
        self.diagnostic_data = data
        self.refresh_btn.setEnabled(True)
        
        # Update status
        findings = data["findings"]
        status_icon, status_text = get_overall_status(findings)
        self.status_icon.setText(status_icon)
        self.status_text.setText(status_text)
        
        # Update status frame color
        if status_icon == "❌":
            self.status_frame.setStyleSheet("""
                QFrame { background-color: #3d1f1f; border-radius: 8px; }
            """)
        elif status_icon == "⚠️":
            self.status_frame.setStyleSheet("""
                QFrame { background-color: #3d3a1f; border-radius: 8px; }
            """)
        else:
            self.status_frame.setStyleSheet("""
                QFrame { background-color: #1f3d1f; border-radius: 8px; }
            """)
        
        # Update environment info
        env = data["environment"]
        self.env_labels["session_type"].setText(env.session_type)
        self.env_labels["desktop"].setText(env.current_desktop)
        self.env_labels["compositor"].setText(env.compositor or "Unknown")
        
        # PipeWire status (check both service and socket - may be socket-activated)
        pw_service = data["pipewire_statuses"].get("pipewire.service")
        pw_socket = data["pipewire_statuses"].get("pipewire.socket")
        pw_running = (pw_service and pw_service.is_active) or (pw_socket and pw_socket.is_active)
        if pw_running:
            self.env_labels["pipewire"].setText("✅ Running")
        else:
            self.env_labels["pipewire"].setText("❌ Not Running")
        
        # Portal status
        portal_status = data["portal_statuses"].get("xdg-desktop-portal.service")
        if portal_status and portal_status.is_active:
            self.env_labels["portal"].setText("✅ Running")
        else:
            self.env_labels["portal"].setText("❌ Not Running")
        
        # Active backend
        active_backends = []
        for name, status in data["portal_statuses"].items():
            if status.is_active and "portal" in name and name != "xdg-desktop-portal.service":
                backend_name = name.replace("xdg-desktop-portal-", "").replace(".service", "")
                active_backends.append(backend_name)
        
        if active_backends:
            self.env_labels["backend"].setText(", ".join(active_backends))
        else:
            self.env_labels["backend"].setText("None")
        
        # Update findings table
        self._update_findings_table(findings)
        
        # Emit signals
        self.findings_updated.emit(findings)
        self.data_ready.emit(data)
    
    def _on_diagnostics_error(self, error_msg):
        """Handle diagnostics error."""
        self.refresh_btn.setEnabled(True)
        self.status_icon.setText("❌")
        self.status_text.setText(f"Error: {error_msg}")
    
    def _update_findings_table(self, findings):
        """Update the findings table."""
        self.findings_table.setRowCount(len(findings))
        
        severity_icons = {
            Severity.ERROR: ("❌", "#ff6b6b"),
            Severity.WARNING: ("⚠️", "#ffd93d"),
            Severity.INFO: ("ℹ️", "#6bcbff"),
        }
        
        for row, finding in enumerate(findings):
            icon, color = severity_icons.get(finding.severity, ("•", "#ccc"))
            
            # Severity
            severity_item = QTableWidgetItem(icon)
            severity_item.setTextAlignment(Qt.AlignCenter)
            self.findings_table.setItem(row, 0, severity_item)
            
            # Component
            component_item = QTableWidgetItem(finding.component)
            self.findings_table.setItem(row, 1, component_item)
            
            # Finding
            finding_item = QTableWidgetItem(finding.title)
            finding_item.setToolTip(finding.details)
            self.findings_table.setItem(row, 2, finding_item)
            
            # Suggested action
            action_text = ""
            if finding.recommended_actions:
                action_text = finding.recommended_actions[0].label
            action_item = QTableWidgetItem(action_text)
            self.findings_table.setItem(row, 3, action_item)
        
        self.findings_table.resizeRowsToContents()
    
    def update_from_screencast_failure(self, screencast_findings):
        """Update overview status when screencast test fails.
        
        This adds the screencast findings to the display and updates status.
        """
        if not screencast_findings:
            return
        
        # Merge with existing findings
        current_findings = []
        if self.diagnostic_data and "findings" in self.diagnostic_data:
            current_findings = list(self.diagnostic_data["findings"])
        
        # Add screencast findings 
        all_findings = screencast_findings + current_findings
        
        # Update status based on combined findings
        status_icon, status_text = get_overall_status(all_findings)
        
        # Override status text if screencast failed
        has_screencast_error = any(f.severity == Severity.ERROR for f in screencast_findings)
        if has_screencast_error:
            status_icon = "❌"
            status_text = "Screen Sharing Issue Detected"
        
        self.status_icon.setText(status_icon)
        self.status_text.setText(status_text)
        
        # Update status frame color
        if status_icon == "❌":
            self.status_frame.setStyleSheet("""
                QFrame { background-color: #3d1f1f; border-radius: 8px; }
            """)
        elif status_icon == "⚠️":
            self.status_frame.setStyleSheet("""
                QFrame { background-color: #3d3a1f; border-radius: 8px; }
            """)
        
        # Update findings table
        self._update_findings_table(all_findings)
        
        # Emit updated findings
        self.findings_updated.emit(all_findings)
