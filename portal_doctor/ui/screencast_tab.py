"""ScreenCast test tab for Portal Doctor."""

import asyncio
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtGui import QFont

from ..models import ScreenCastTestResult, Finding, Severity, Action, ActionType
from ..screencast_test.xdg_screencast import run_screencast_test


class ScreenCastWorker(QObject):
    """Worker to run screencast test in background thread."""
    
    finished = Signal(object)  # Emits ScreenCastTestResult
    progress = Signal(str)  # Emits step name
    
    def run(self):
        """Run the screencast test."""
        try:
            # Run the async test
            result = asyncio.run(run_screencast_test())
            self.finished.emit(result)
        except Exception as e:
            result = ScreenCastTestResult(
                success=False,
                step_reached="Initialize",
                error_name=type(e).__name__,
                error_message=str(e),
            )
            self.finished.emit(result)


class ScreenCastTab(QWidget):
    """Tab for running screencast portal tests."""
    
    # Signal emitted when test fails with findings to show in Fixes tab
    test_failed = Signal(list)  # List of Finding objects
    
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
        
        # Header
        header = QLabel("ScreenCast Portal Test")
        header.setFont(QFont("", 16, QFont.Bold))
        layout.addWidget(header)
        
        # Description
        desc = QLabel(
            "This test performs a real XDG portal screencast flow to verify that "
            "screen sharing is working correctly. The test will:\n\n"
            "1. Connect to the XDG Desktop Portal via DBus\n"
            "2. Create a screen capture session\n"
            "3. Request source selection (you may see a picker dialog)\n"
            "4. Start the capture and verify PipeWire stream"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #bbb; line-height: 1.5;")
        layout.addWidget(desc)
        
        # Warning for X11
        self.x11_warning = QFrame()
        self.x11_warning.setStyleSheet("""
            QFrame {
                background-color: #3d3a1f;
                border: 1px solid #665d00;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        warning_layout = QHBoxLayout(self.x11_warning)
        warning_icon = QLabel("⚠️")
        warning_icon.setFont(QFont("", 16))
        warning_layout.addWidget(warning_icon)
        warning_text = QLabel(
            "You appear to be running an X11 session. This test is designed for "
            "Wayland and may not work correctly on X11."
        )
        warning_text.setWordWrap(True)
        warning_text.setStyleSheet("color: #e6d600;")
        warning_layout.addWidget(warning_text, 1)
        self.x11_warning.hide()
        layout.addWidget(self.x11_warning)
        
        # Test controls
        controls_layout = QHBoxLayout()
        
        self.test_btn = QPushButton("▶️ Run ScreenCast Test")
        self.test_btn.setFont(QFont("", 11, QFont.Bold))
        self.test_btn.setMinimumHeight(44)
        self.test_btn.clicked.connect(self._run_test)
        controls_layout.addWidget(self.test_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Progress indicator
        self.progress_frame = QFrame()
        self.progress_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        progress_layout = QVBoxLayout(self.progress_frame)
        
        self.progress_label = QLabel("Ready to test")
        self.progress_label.setFont(QFont("", 11))
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addWidget(self.progress_frame)
        
        # Result display
        result_label = QLabel("Test Output:")
        result_label.setFont(QFont("", 11, QFont.Bold))
        layout.addWidget(result_label)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 4px;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        self.result_text.setPlaceholderText("Test results will appear here...")
        layout.addWidget(self.result_text, 1)
    
    def set_diagnostic_data(self, data):
        """Set diagnostic data from overview tab."""
        self.diagnostic_data = data
        
        # Check if X11
        if data and data.get("environment"):
            env = data["environment"]
            if env.is_x11:
                self.x11_warning.show()
            else:
                self.x11_warning.hide()
    
    def _run_test(self):
        """Run the screencast test."""
        self.test_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_label.setText("Running screencast test...")
        self.result_text.clear()
        self.result_text.append("Starting XDG ScreenCast test...\n")
        
        # Create worker and thread
        self.worker = ScreenCastWorker()
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        
        # Connect signals
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_test_complete)
        self.worker.finished.connect(self.worker_thread.quit)
        
        # Start thread
        self.worker_thread.start()
    
    def _on_test_complete(self, result: ScreenCastTestResult):
        """Handle test completion."""
        self.test_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if result.success:
            self.progress_label.setText("✅ Test Passed!")
            self.progress_frame.setStyleSheet("""
                QFrame {
                    background-color: #1f3d1f;
                    border: 1px solid #198754;
                    border-radius: 8px;
                    padding: 16px;
                }
            """)
            
            self.result_text.append("=" * 50)
            self.result_text.append("✅ SCREENCAST TEST PASSED")
            self.result_text.append("=" * 50)
            self.result_text.append("")
            self.result_text.append(f"Step reached: {result.step_reached}")
            if result.pipewire_node_id:
                self.result_text.append(f"PipeWire Node ID: {result.pipewire_node_id}")
            if result.stream_properties:
                self.result_text.append(f"Stream properties: {result.stream_properties}")
            self.result_text.append("")
            self.result_text.append("Screen sharing appears to be working correctly!")
            self.result_text.append("Applications should be able to capture your screen.")
            
        else:
            self.progress_label.setText("❌ Test Failed")
            self.progress_frame.setStyleSheet("""
                QFrame {
                    background-color: #3d1f1f;
                    border: 1px solid #dc3545;
                    border-radius: 8px;
                    padding: 16px;
                }
            """)
            
            self.result_text.append("=" * 50)
            self.result_text.append("❌ SCREENCAST TEST FAILED")
            self.result_text.append("=" * 50)
            self.result_text.append("")
            self.result_text.append(f"Step reached: {result.step_reached}")
            self.result_text.append("")
            
            if result.error_name:
                self.result_text.append(f"Error: {result.error_name}")
            if result.error_message:
                self.result_text.append(f"Message: {result.error_message}")
            
            self.result_text.append("")
            self.result_text.append("Possible causes:")
            
            if result.step_reached == "Connect":
                self.result_text.append("  • DBus session bus not available")
                self.result_text.append("  • Not running in a graphical session")
            elif result.step_reached == "GetPortal":
                self.result_text.append("  • xdg-desktop-portal service not running")
                self.result_text.append("  • Try: systemctl --user start xdg-desktop-portal")
            elif result.step_reached == "CreateSession":
                self.result_text.append("  • Portal backend not responding")
                self.result_text.append("  • Check if the correct backend is running")
            elif result.step_reached == "SelectSources":
                if "cancelled" in (result.error_message or "").lower():
                    self.result_text.append("  • You cancelled the source selection")
                else:
                    self.result_text.append("  • Portal picker failed to appear")
                    self.result_text.append("  • Backend may not support ScreenCast")
            elif result.step_reached == "Start":
                self.result_text.append("  • Stream creation failed")
                self.result_text.append("  • PipeWire may not be running")
            
            self.result_text.append("")
            self.result_text.append("Check the Fixes tab for recommended solutions.")
            
            # Generate findings and emit to Fixes tab
            findings = self._generate_failure_findings(result)
            if findings:
                self.test_failed.emit(findings)
        
        if result.log_excerpt:
            self.result_text.append("")
            self.result_text.append("Log output:")
            self.result_text.append(result.log_excerpt)
    
    def _generate_failure_findings(self, result: ScreenCastTestResult) -> list[Finding]:
        """Generate findings based on the screencast test failure."""
        findings = []
        
        error_msg = result.error_message or ""
        error_name = result.error_name or ""
        step = result.step_reached
        
        if step == "Connect":
            findings.append(Finding(
                id="screencast_dbus_failed",
                severity=Severity.ERROR,
                title="DBus Connection Failed",
                component="DBus",
                details=(
                    "Could not connect to the DBus session bus. This is required for "
                    "portal communication.\n\n"
                    "This usually means you're not running in a proper graphical session."
                ),
                evidence=f"{error_name}: {error_msg}",
                recommended_actions=[
                    Action(
                        id="check_session",
                        type=ActionType.GUIDANCE,
                        label="Check Session",
                        description="Make sure you're running in a graphical session (not SSH or TTY)",
                    ),
                ],
            ))
        
        elif step == "GetPortal":
            # Check for specific power-saver-enabled error
            if "power-saver-enabled" in error_msg.lower() or "power-saver" in error_msg.lower():
                findings.append(Finding(
                    id="screencast_power_saver_dbus_bug",
                    severity=Severity.ERROR,
                    title="DBus Power-Saver Interface Bug",
                    component="Portal DBus",
                    details=(
                        "This error is caused by an incompatibility between the dbus-next Python library "
                        "and newer xdg-desktop-portal versions that include the PowerSaveMonitor interface.\n\n"
                        "The portal has a 'power-saver-enabled' property that uses hyphens in its name, "
                        "which dbus-next incorrectly rejects.\n\n"
                        "**Workarounds:**\n"
                        "1. Update dbus-next to the latest version\n"
                        "2. Try a different portal backend\n"
                        "3. Use applications that don't rely on this Python DBus library"
                    ),
                    evidence=f"Error: {error_name}: {error_msg}",
                    recommended_actions=[
                        Action(
                            id="upgrade_dbus_next",
                            type=ActionType.RESTART_SERVICE,
                            label="Upgrade dbus-next",
                            description="Try upgrading the dbus-next Python package",
                            command="pip install --user --upgrade dbus-next",
                        ),
                        Action(
                            id="restart_portal_full",
                            type=ActionType.RESTART_SERVICE,
                            label="Restart Portal Stack",
                            description="Restart all portal and PipeWire services",
                            command="systemctl --user restart xdg-desktop-portal.service pipewire.service wireplumber.service",
                        ),
                        Action(
                            id="check_portal_version",
                            type=ActionType.SHOW_COMMAND,
                            label="Check Portal Version",
                            description="Check installed xdg-desktop-portal version",
                            command="xdg-desktop-portal --version 2>/dev/null || rpm -q xdg-desktop-portal 2>/dev/null || dpkg -s xdg-desktop-portal 2>/dev/null | grep Version",
                        ),
                        Action(
                            id="test_native_screenshare",
                            type=ActionType.GUIDANCE,
                            label="Test with Native Apps",
                            description=(
                                "The Portal Doctor test uses dbus-next which has this bug. "
                                "Try testing screen sharing directly in Discord, OBS, or a browser - "
                                "they use different DBus libraries that may work correctly."
                            ),
                        ),
                    ],
                ))
            else:
                findings.append(Finding(
                    id="screencast_portal_unreachable",
                    severity=Severity.ERROR,
                    title="XDG Desktop Portal Unreachable",
                    component="Portal Service",
                    details=(
                        "Could not connect to the xdg-desktop-portal service. "
                        "The service may not be running or is unresponsive.\n\n"
                        "This is a critical issue that prevents all screen sharing."
                    ),
                    evidence=f"Step: {step}, Error: {error_name}: {error_msg}",
                    recommended_actions=[
                        Action(
                            id="restart_portal",
                            type=ActionType.RESTART_SERVICE,
                            label="Restart xdg-desktop-portal",
                            description="Restart the portal service to fix connectivity",
                            command="systemctl --user restart xdg-desktop-portal.service",
                        ),
                        Action(
                            id="view_portal_status",
                            type=ActionType.SHOW_COMMAND,
                            label="Check Service Status",
                            description="View the portal service status",
                            command="systemctl --user status xdg-desktop-portal.service",
                        ),
                    ],
                ))
        
        elif step == "CreateSession":
            findings.append(Finding(
                id="screencast_session_failed",
                severity=Severity.ERROR,
                title="Portal Session Creation Failed",
                component="Portal Backend",
                details=(
                    "The portal accepted our connection but failed to create a screen "
                    "capture session. This usually means the portal backend isn't working.\n\n"
                    "Check that the correct backend for your desktop is installed and running."
                ),
                evidence=f"Step: {step}, Error: {error_name}: {error_msg}",
                recommended_actions=[
                    Action(
                        id="restart_all_portals",
                        type=ActionType.RESTART_SERVICE,
                        label="Restart All Portal Services",
                        description="Restart portal and backend services",
                        command="systemctl --user restart xdg-desktop-portal.service xdg-desktop-portal-kde.service xdg-desktop-portal-gnome.service xdg-desktop-portal-wlr.service 2>/dev/null; echo 'Services restarted'",
                    ),
                    Action(
                        id="view_logs",
                        type=ActionType.OPEN_LOGS,
                        label="View Portal Logs",
                        description="Check portal logs for errors",
                        command="journalctl --user -xeu 'xdg-desktop-portal*' --since '5 min ago'",
                    ),
                ],
            ))
        
        elif step == "SelectSources":
            if "cancelled" in error_msg.lower():
                findings.append(Finding(
                    id="screencast_cancelled",
                    severity=Severity.INFO,
                    title="Screen Selection Cancelled",
                    component="User Action",
                    details="You cancelled the screen selection dialog. This is not an error.",
                    evidence="User cancelled source selection",
                    recommended_actions=[
                        Action(
                            id="retry_test",
                            type=ActionType.GUIDANCE,
                            label="Try Again",
                            description="Run the test again and select a screen/window from the picker",
                        ),
                    ],
                ))
            elif "interfacenotfound" in error_name.lower() or "interface not found" in error_msg.lower():
                # ScreenCast interface not available on this portal
                findings.append(Finding(
                    id="screencast_interface_missing",
                    severity=Severity.ERROR,
                    title="ScreenCast Interface Not Found",
                    component="Portal Backend",
                    details=(
                        "The portal service is running but does NOT expose the ScreenCast "
                        "interface. This means your portal backend doesn't support screen sharing.\n\n"
                        "**Common causes:**\n"
                        "• Wrong portal backend for your desktop environment\n"
                        "• Portal backend not running (only main portal is running)\n"
                        "• GTK-only backend (xdg-desktop-portal-gtk doesn't support ScreenCast)\n\n"
                        "You need a backend that supports ScreenCast:\n"
                        "• KDE Plasma → xdg-desktop-portal-kde\n"
                        "• GNOME → xdg-desktop-portal-gnome\n"
                        "• Hyprland → xdg-desktop-portal-hyprland\n"
                        "• Sway/wlroots → xdg-desktop-portal-wlr"
                    ),
                    evidence=f"{error_name}: {error_msg}",
                    recommended_actions=[
                        Action(
                            id="check_running_backends",
                            type=ActionType.SHOW_COMMAND,
                            label="Check Running Backends",
                            description="See which portal backends are currently running",
                            command="systemctl --user list-units 'xdg-desktop-portal*' --all",
                        ),
                        Action(
                            id="restart_all_portal_services",
                            type=ActionType.RESTART_SERVICE,
                            label="Restart All Portal Services",
                            description="Restart portal to trigger backend activation",
                            command="systemctl --user restart xdg-desktop-portal.service",
                        ),
                        Action(
                            id="check_installed_portals",
                            type=ActionType.SHOW_COMMAND,
                            label="Check Installed Portals",
                            description="List all installed portal packages",
                            command="rpm -qa 'xdg-desktop-portal*' 2>/dev/null || dpkg -l 'xdg-desktop-portal*' 2>/dev/null || pacman -Qs xdg-desktop-portal 2>/dev/null",
                        ),
                    ],
                ))
            else:
                findings.append(Finding(
                    id="screencast_select_failed",
                    severity=Severity.ERROR,
                    title="Source Selection Failed",
                    component="Portal Backend",
                    details=(
                        "The screen picker dialog failed or didn't appear. "
                        "Your portal backend may not support the ScreenCast interface.\n\n"
                        "This can happen if you have the wrong backend installed for your desktop."
                    ),
                    evidence=f"Step: {step}, Error: {error_name}: {error_msg}",
                    recommended_actions=[
                        Action(
                            id="check_backend",
                            type=ActionType.SHOW_COMMAND,
                            label="Check Active Backend",
                            description="See which portal backend is running",
                            command="systemctl --user list-units 'xdg-desktop-portal*' --state=active",
                        ),
                    ],
                ))
        
        elif step == "Start":
            findings.append(Finding(
                id="screencast_stream_failed",
                severity=Severity.ERROR,
                title="Stream Start Failed",
                component="PipeWire",
                details=(
                    "The screen was selected but the capture stream couldn't start. "
                    "This usually indicates a PipeWire issue.\n\n"
                    "Make sure PipeWire and WirePlumber are running correctly."
                ),
                evidence=f"Step: {step}, Error: {error_name}: {error_msg}",
                recommended_actions=[
                    Action(
                        id="restart_pipewire",
                        type=ActionType.RESTART_SERVICE,
                        label="Restart PipeWire Stack",
                        description="Restart PipeWire and WirePlumber",
                        command="systemctl --user restart pipewire.service wireplumber.service",
                    ),
                    Action(
                        id="check_pipewire",
                        type=ActionType.SHOW_COMMAND,
                        label="Check PipeWire Status",
                        description="View PipeWire service status",
                        command="systemctl --user status pipewire.service wireplumber.service",
                    ),
                ],
            ))
        
        else:
            # Generic failure
            findings.append(Finding(
                id="screencast_generic_failure",
                severity=Severity.ERROR,
                title="ScreenCast Test Failed",
                component="Screen Sharing",
                details=(
                    f"The screencast test failed at step: {step}\n\n"
                    "Try restarting the portal services and running the test again."
                ),
                evidence=f"Step: {step}, Error: {error_name}: {error_msg}",
                recommended_actions=[
                    Action(
                        id="restart_all",
                        type=ActionType.RESTART_SERVICE,
                        label="Restart Portal Services",
                        description="Restart all portal-related services",
                        command="systemctl --user restart xdg-desktop-portal.service pipewire.service wireplumber.service",
                    ),
                ],
            ))
        
        return findings

