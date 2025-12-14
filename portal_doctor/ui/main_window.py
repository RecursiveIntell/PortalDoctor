"""Main window for Portal Doctor GUI."""

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel,
    QStatusBar, QApplication, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from .overview_tab import OverviewTab
from .fixes_tab import FixesTab
from .screencast_tab import ScreenCastTab
from .report_tab import ReportTab


class MainWindow(QMainWindow):
    """Main application window with tabbed interface."""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Portal Doctor")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        self._setup_ui()
        self._setup_statusbar()
        
        # Run initial diagnostics after window is shown
        QTimer.singleShot(100, self._run_initial_diagnostics)
    
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
        
        # Add tabs
        self.tabs.addTab(self.overview_tab, "🔍 Overview")
        self.tabs.addTab(self.fixes_tab, "🔧 Fixes")
        self.tabs.addTab(self.screencast_tab, "📺 Test Screencast")
        self.tabs.addTab(self.report_tab, "📋 Report")
        
        # Connect signals
        self.overview_tab.findings_updated.connect(self._on_findings_updated)
        self.overview_tab.data_ready.connect(self._on_data_ready)
        self.screencast_tab.test_failed.connect(self._on_screencast_failed)
        
        # Apply styling
        self._apply_styles()
    
    def _apply_styles(self):
        """Apply application styles."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QTabWidget::pane {
                border: 1px solid #333;
                background-color: #252525;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #ccc;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #252525;
                color: #fff;
            }
            QTabBar::tab:hover:!selected {
                background-color: #353535;
            }
            QLabel {
                color: #ddd;
            }
            QPushButton {
                background-color: #0d6efd;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
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
                gridline-color: #444;
                border: 1px solid #444;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #0d6efd;
            }
            QHeaderView::section {
                background-color: #333;
                color: #fff;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #444;
            }
            QTextEdit, QPlainTextEdit {
                background-color: #2d2d2d;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 4px;
                font-family: monospace;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #666;
            }
        """)
    
    def _setup_statusbar(self):
        """Set up the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready")
    
    def _run_initial_diagnostics(self):
        """Run diagnostics when the window first opens."""
        self.statusbar.showMessage("Running diagnostics...")
        self.overview_tab.run_diagnostics()
    
    def _on_findings_updated(self, findings):
        """Handle updated findings from diagnostics."""
        self.fixes_tab.update_findings(findings)
        self.statusbar.showMessage(f"Found {len(findings)} issue(s)")
    
    def _on_data_ready(self, data):
        """Handle diagnostic data being ready."""
        self.report_tab.set_diagnostic_data(data)
        self.screencast_tab.set_diagnostic_data(data)
    
    def _on_screencast_failed(self, findings):
        """Handle screencast test failure with generated findings."""
        self.fixes_tab.update_findings(findings)
        self.overview_tab.update_from_screencast_failure(findings)
        self.statusbar.showMessage(f"Screencast test failed - {len(findings)} fix(es) available")
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
    app.setApplicationVersion("0.1.0")
    
    window = MainWindow()
    window.show()
    
    return app.exec()
