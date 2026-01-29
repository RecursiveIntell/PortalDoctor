"""Main window for Portal Doctor GUI."""

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QStatusBar, QApplication, QMenuBar, QMenu, QMessageBox, QDialog,
    QPushButton, QFrame, QProgressBar
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QFont, QAction, QKeySequence, QIcon, QPixmap, QPainter, QColor

from .. import __version__
from .overview_tab import OverviewTab
from .fixes_tab import FixesTab
from .screencast_tab import ScreenCastTab
from .report_tab import ReportTab


def create_app_icon() -> QIcon:
    """Create a simple application icon programmatically."""
    # Create a simple icon with a stethoscope-like design
    sizes = [16, 32, 48, 64, 128]
    icon = QIcon()

    for size in sizes:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background circle
        painter.setBrush(QColor("#0d6efd"))
        painter.setPen(Qt.NoPen)
        margin = size // 8
        painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)

        # Inner design (simplified portal/screen icon)
        painter.setBrush(QColor("#ffffff"))
        inner_margin = size // 4
        inner_size = size - 2 * inner_margin
        painter.drawRoundedRect(
            inner_margin, inner_margin,
            inner_size, inner_size,
            size // 8, size // 8
        )

        # Screen area
        painter.setBrush(QColor("#1e1e1e"))
        screen_margin = size // 3
        screen_size = size - 2 * screen_margin
        painter.drawRoundedRect(
            screen_margin, screen_margin,
            screen_size, screen_size // 2,
            size // 16, size // 16
        )

        painter.end()
        icon.addPixmap(pixmap)

    return icon


class AboutDialog(QDialog):
    """About dialog for Portal Doctor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Portal Doctor")
        self.setFixedSize(450, 350)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # App name and version
        title = QLabel("Portal Doctor")
        title.setFont(QFont("", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        version = QLabel(f"Version {__version__}")
        version.setFont(QFont("", 12))
        version.setStyleSheet("color: #888;")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)

        # Description
        desc = QLabel(
            "A diagnostic tool for Linux Wayland screen sharing.\n\n"
            "Portal Doctor helps diagnose and fix issues with XDG Desktop Portals, "
            "PipeWire, and screen sharing on Wayland-based Linux desktops."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #bbb; line-height: 1.5;")
        layout.addWidget(desc)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #444;")
        layout.addWidget(sep)

        # Supported environments
        envs = QLabel(
            "Supports: KDE Plasma, GNOME, Hyprland, Sway,\n"
            "and other wlroots-based compositors"
        )
        envs.setAlignment(Qt.AlignCenter)
        envs.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(envs)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)


class MainWindow(QMainWindow):
    """Main application window with tabbed interface."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Portal Doctor")
        self.setMinimumSize(900, 650)
        self.resize(1100, 750)

        # Set application icon
        self.setWindowIcon(create_app_icon())

        self._setup_menubar()
        self._setup_ui()
        self._setup_statusbar()
        self._setup_shortcuts()

        # Run initial diagnostics after window is shown
        QTimer.singleShot(100, self._run_initial_diagnostics)

    def _setup_menubar(self):
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        refresh_action = QAction("&Refresh Diagnostics", self)
        refresh_action.setShortcut(QKeySequence("Ctrl+R"))
        refresh_action.setStatusTip("Run diagnostics again")
        refresh_action.triggered.connect(self._refresh_diagnostics)
        file_menu.addAction(refresh_action)

        file_menu.addSeparator()

        export_action = QAction("&Export Report...", self)
        export_action.setShortcut(QKeySequence("Ctrl+S"))
        export_action.setStatusTip("Save diagnostic report to file")
        export_action.triggered.connect(self._export_report)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.setStatusTip("Exit the application")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        overview_action = QAction("&Overview", self)
        overview_action.setShortcut(QKeySequence("Ctrl+1"))
        overview_action.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        view_menu.addAction(overview_action)

        fixes_action = QAction("&Fixes", self)
        fixes_action.setShortcut(QKeySequence("Ctrl+2"))
        fixes_action.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
        view_menu.addAction(fixes_action)

        screencast_action = QAction("&Test Screencast", self)
        screencast_action.setShortcut(QKeySequence("Ctrl+3"))
        screencast_action.triggered.connect(lambda: self.tabs.setCurrentIndex(2))
        view_menu.addAction(screencast_action)

        report_action = QAction("&Report", self)
        report_action.setShortcut(QKeySequence("Ctrl+4"))
        report_action.triggered.connect(lambda: self.tabs.setCurrentIndex(3))
        view_menu.addAction(report_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        screencast_test_action = QAction("Run &ScreenCast Test", self)
        screencast_test_action.setShortcut(QKeySequence("F5"))
        screencast_test_action.setStatusTip("Run the screen sharing test")
        screencast_test_action.triggered.connect(self._run_screencast_test)
        tools_menu.addAction(screencast_test_action)

        tools_menu.addSeparator()

        restart_portal_action = QAction("Restart &Portal Services", self)
        restart_portal_action.setStatusTip("Restart xdg-desktop-portal and related services")
        restart_portal_action.triggered.connect(self._restart_portal_services)
        tools_menu.addAction(restart_portal_action)

        restart_pipewire_action = QAction("Restart P&ipeWire", self)
        restart_pipewire_action.setStatusTip("Restart PipeWire and WirePlumber")
        restart_pipewire_action.triggered.connect(self._restart_pipewire)
        tools_menu.addAction(restart_pipewire_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        shortcuts_action = QAction("&Keyboard Shortcuts", self)
        shortcuts_action.setShortcut(QKeySequence("Ctrl+/"))
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        about_action = QAction("&About Portal Doctor", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        about_qt_action = QAction("About &Qt", self)
        about_qt_action.triggered.connect(QApplication.aboutQt)
        help_menu.addAction(about_qt_action)

    def _setup_ui(self):
        """Set up the main UI."""
        # Central widget with tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create tabs
        self.overview_tab = OverviewTab()
        self.fixes_tab = FixesTab()
        self.screencast_tab = ScreenCastTab()
        self.report_tab = ReportTab()

        # Add tabs with icons
        self.tabs.addTab(self.overview_tab, "Overview")
        self.tabs.addTab(self.fixes_tab, "Fixes")
        self.tabs.addTab(self.screencast_tab, "Test Screencast")
        self.tabs.addTab(self.report_tab, "Report")

        # Set tab tooltips
        self.tabs.setTabToolTip(0, "System health check and diagnostics (Ctrl+1)")
        self.tabs.setTabToolTip(1, "Recommended fixes for detected issues (Ctrl+2)")
        self.tabs.setTabToolTip(2, "Test screen sharing functionality (Ctrl+3)")
        self.tabs.setTabToolTip(3, "Generate diagnostic report (Ctrl+4)")

        # Connect signals
        self.overview_tab.findings_updated.connect(self._on_findings_updated)
        self.overview_tab.data_ready.connect(self._on_data_ready)
        self.screencast_tab.test_failed.connect(self._on_screencast_failed)

        # Apply styling
        self._apply_styles()

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # F5 to refresh is already set in menu
        pass

    def _apply_styles(self):
        """Apply application styles."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QMenuBar {
                background-color: #252525;
                color: #ddd;
                padding: 4px;
            }
            QMenuBar::item {
                padding: 6px 12px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: #353535;
            }
            QMenu {
                background-color: #2d2d2d;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px 8px 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0d6efd;
            }
            QMenu::separator {
                height: 1px;
                background-color: #444;
                margin: 4px 8px;
            }
            QTabWidget::pane {
                border: 1px solid #333;
                background-color: #252525;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #999;
                padding: 12px 24px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #252525;
                color: #fff;
            }
            QTabBar::tab:hover:!selected {
                background-color: #353535;
                color: #ccc;
            }
            QLabel {
                color: #ddd;
            }
            QPushButton {
                background-color: #0d6efd;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
            QPushButton:pressed {
                background-color: #0a58ca;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
            QTableWidget {
                background-color: #2d2d2d;
                color: #ddd;
                gridline-color: #3a3a3a;
                border: 1px solid #444;
                border-radius: 6px;
                selection-background-color: #0d6efd;
            }
            QTableWidget::item {
                padding: 10px;
            }
            QTableWidget::item:selected {
                background-color: #0d6efd;
            }
            QHeaderView::section {
                background-color: #333;
                color: #fff;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #0d6efd;
                font-weight: bold;
            }
            QTextEdit, QPlainTextEdit {
                background-color: #1a1a1a;
                color: #ddd;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
                font-size: 12px;
                padding: 8px;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 14px;
                border-radius: 7px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background-color: #444;
                border-radius: 5px;
                min-height: 30px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #555;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 14px;
                border-radius: 7px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal {
                background-color: #444;
                border-radius: 5px;
                min-width: 30px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #555;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
            QStatusBar {
                background-color: #252525;
                color: #888;
                border-top: 1px solid #333;
                padding: 4px;
            }
            QProgressBar {
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                text-align: center;
                color: #fff;
            }
            QProgressBar::chunk {
                background-color: #0d6efd;
                border-radius: 3px;
            }
            QToolTip {
                background-color: #333;
                color: #fff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px;
            }
        """)

    def _setup_statusbar(self):
        """Set up the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        # Add permanent widgets
        self.status_label = QLabel("Ready")
        self.statusbar.addWidget(self.status_label, 1)

        # Version label on the right
        version_label = QLabel(f"v{__version__}")
        version_label.setStyleSheet("color: #666; padding-right: 8px;")
        self.statusbar.addPermanentWidget(version_label)

    def _run_initial_diagnostics(self):
        """Run diagnostics when the window first opens."""
        self.status_label.setText("Running diagnostics...")
        self.overview_tab.run_diagnostics()

    def _refresh_diagnostics(self):
        """Refresh diagnostics."""
        self.status_label.setText("Refreshing diagnostics...")
        self.overview_tab.run_diagnostics()

    def _export_report(self):
        """Export the diagnostic report."""
        self.tabs.setCurrentWidget(self.report_tab)
        self.report_tab._save_report()

    def _run_screencast_test(self):
        """Run the screencast test."""
        self.tabs.setCurrentWidget(self.screencast_tab)
        self.screencast_tab._run_test()

    def _restart_portal_services(self):
        """Restart portal services."""
        from ..diagnostics.services import restart_service

        reply = QMessageBox.question(
            self,
            "Restart Portal Services",
            "This will restart xdg-desktop-portal and its backends.\n\n"
            "Any active screen sharing sessions may be interrupted.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.status_label.setText("Restarting portal services...")
            success, msg = restart_service("xdg-desktop-portal.service")
            if success:
                QMessageBox.information(self, "Success", "Portal services restarted successfully.\n\nRefreshing diagnostics...")
                self._refresh_diagnostics()
            else:
                QMessageBox.warning(self, "Failed", f"Failed to restart portal services:\n\n{msg}")
            self.status_label.setText("Ready")

    def _restart_pipewire(self):
        """Restart PipeWire services."""
        from ..diagnostics.services import restart_service

        reply = QMessageBox.question(
            self,
            "Restart PipeWire",
            "This will restart PipeWire and WirePlumber.\n\n"
            "Audio playback may be briefly interrupted.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.status_label.setText("Restarting PipeWire...")
            success1, msg1 = restart_service("pipewire.service")
            success2, msg2 = restart_service("wireplumber.service")

            if success1 and success2:
                QMessageBox.information(self, "Success", "PipeWire restarted successfully.\n\nRefreshing diagnostics...")
                self._refresh_diagnostics()
            else:
                errors = []
                if not success1:
                    errors.append(f"PipeWire: {msg1}")
                if not success2:
                    errors.append(f"WirePlumber: {msg2}")
                QMessageBox.warning(self, "Failed", f"Failed to restart:\n\n" + "\n".join(errors))
            self.status_label.setText("Ready")

    def _show_shortcuts(self):
        """Show keyboard shortcuts dialog."""
        shortcuts = """
<h3>Keyboard Shortcuts</h3>
<table style="border-collapse: collapse; width: 100%;">
<tr><td style="padding: 6px;"><b>Ctrl+R</b></td><td style="padding: 6px;">Refresh diagnostics</td></tr>
<tr><td style="padding: 6px;"><b>Ctrl+S</b></td><td style="padding: 6px;">Save report to file</td></tr>
<tr><td style="padding: 6px;"><b>Ctrl+Q</b></td><td style="padding: 6px;">Quit application</td></tr>
<tr><td style="padding: 6px;"><b>F5</b></td><td style="padding: 6px;">Run screencast test</td></tr>
<tr><td style="padding: 6px;"><b>Ctrl+1</b></td><td style="padding: 6px;">Go to Overview tab</td></tr>
<tr><td style="padding: 6px;"><b>Ctrl+2</b></td><td style="padding: 6px;">Go to Fixes tab</td></tr>
<tr><td style="padding: 6px;"><b>Ctrl+3</b></td><td style="padding: 6px;">Go to Test Screencast tab</td></tr>
<tr><td style="padding: 6px;"><b>Ctrl+4</b></td><td style="padding: 6px;">Go to Report tab</td></tr>
<tr><td style="padding: 6px;"><b>Ctrl+/</b></td><td style="padding: 6px;">Show this help</td></tr>
</table>
        """
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts)

    def _show_about(self):
        """Show about dialog."""
        dialog = AboutDialog(self)
        dialog.exec()

    def _on_findings_updated(self, findings):
        """Handle updated findings from diagnostics."""
        self.fixes_tab.update_findings(findings)

        errors = sum(1 for f in findings if f.severity.value == "error")
        warnings = sum(1 for f in findings if f.severity.value == "warning")

        if errors > 0:
            self.status_label.setText(f"Found {errors} error(s), {warnings} warning(s)")
        elif warnings > 0:
            self.status_label.setText(f"Found {warnings} warning(s)")
        elif findings:
            self.status_label.setText(f"Found {len(findings)} info item(s)")
        else:
            self.status_label.setText("No issues detected")

    def _on_data_ready(self, data):
        """Handle diagnostic data being ready."""
        self.report_tab.set_diagnostic_data(data)
        self.screencast_tab.set_diagnostic_data(data)

    def _on_screencast_failed(self, findings):
        """Handle screencast test failure with generated findings."""
        self.fixes_tab.update_findings(findings)
        self.overview_tab.update_from_screencast_failure(findings)
        self.status_label.setText(f"Screencast test failed - {len(findings)} fix(es) available")
        # Switch to Fixes tab
        self.tabs.setCurrentWidget(self.fixes_tab)


def run_gui():
    """Run the GUI application."""
    import sys

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # Set application metadata
    app.setApplicationName("Portal Doctor")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Portal Doctor")
    app.setWindowIcon(create_app_icon())

    window = MainWindow()
    window.show()

    return app.exec()
