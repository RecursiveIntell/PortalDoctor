"""Report tab for Portal Doctor."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ..report.generator import generate_report, save_report, report_to_clipboard


class ReportTab(QWidget):
    """Tab for generating and exporting diagnostic reports."""
    
    def __init__(self):
        super().__init__()
        self.diagnostic_data = None
        self.current_report = ""
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the tab UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header = QLabel("Diagnostic Report")
        header.setFont(QFont("", 16, QFont.Bold))
        layout.addWidget(header)
        
        # Description
        desc = QLabel(
            "Generate a comprehensive diagnostic report that you can share in bug reports, "
            "forum posts, or support tickets. The report includes system information, "
            "service status, and recommended fixes. Personal information is automatically "
            "sanitized."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #bbb;")
        layout.addWidget(desc)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.generate_btn = QPushButton("📋 Generate Report")
        self.generate_btn.setFont(QFont("", 11, QFont.Bold))
        self.generate_btn.setMinimumHeight(40)
        self.generate_btn.clicked.connect(self._generate_report)
        btn_layout.addWidget(self.generate_btn)
        
        self.copy_btn = QPushButton("📄 Copy to Clipboard")
        self.copy_btn.setMinimumHeight(40)
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        self.copy_btn.setEnabled(False)
        btn_layout.addWidget(self.copy_btn)
        
        self.save_btn = QPushButton("💾 Save to File")
        self.save_btn.setMinimumHeight(40)
        self.save_btn.clicked.connect(self._save_to_file)
        self.save_btn.setEnabled(False)
        btn_layout.addWidget(self.save_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Report preview
        preview_label = QLabel("Report Preview:")
        preview_label.setFont(QFont("", 11, QFont.Bold))
        layout.addWidget(preview_label)
        
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 4px;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        self.report_text.setPlaceholderText(
            "Click 'Generate Report' to create a diagnostic report...\n\n"
            "The report will include:\n"
            "• System environment information\n"
            "• Service status (xdg-desktop-portal, PipeWire, etc.)\n"
            "• Portal backend configuration\n"
            "• Diagnostic findings and recommendations\n"
            "• Recent journal logs (sanitized)"
        )
        layout.addWidget(self.report_text, 1)
        
        # Status bar
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.status_label)
    
    def set_diagnostic_data(self, data):
        """Set diagnostic data from overview tab."""
        self.diagnostic_data = data
    
    def _generate_report(self):
        """Generate a diagnostic report."""
        if not self.diagnostic_data:
            QMessageBox.warning(
                self,
                "No Data",
                "No diagnostic data available. Please run diagnostics from the Overview tab first."
            )
            return
        
        try:
            data = self.diagnostic_data
            
            # Get service statuses as list
            services = list(data["portal_statuses"].values()) + \
                       list(data["pipewire_statuses"].values())
            
            self.current_report = generate_report(
                environment=data["environment"],
                services=services,
                backends=data["backends"],
                portals_config=data["portals_config"],
                findings=data["findings"],
                journal_excerpts=data["journal_excerpts"],
            )
            
            self.report_text.setPlainText(self.current_report)
            self.copy_btn.setEnabled(True)
            self.save_btn.setEnabled(True)
            self.status_label.setText(f"Report generated ({len(self.current_report)} characters)")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to generate report: {e}"
            )
    
    def _copy_to_clipboard(self):
        """Copy report to clipboard."""
        if not self.current_report:
            return
        
        success, message = report_to_clipboard(self.current_report)
        
        if success:
            self.status_label.setText("✅ Report copied to clipboard")
        else:
            # Fallback: use Qt clipboard
            from PySide6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(self.current_report)
            self.status_label.setText("✅ Report copied to clipboard")
    
    def _save_to_file(self):
        """Save report to a file."""
        if not self.current_report:
            return
        
        # Use default location or let user choose
        success, result = save_report(self.current_report)
        
        if success:
            self.status_label.setText(f"✅ Report saved to: {result}")
            QMessageBox.information(
                self,
                "Report Saved",
                f"Report saved successfully to:\n{result}"
            )
        else:
            # Let user choose a custom location
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                "Save Report",
                "portal-doctor-report.md",
                "Markdown (*.md);;Text (*.txt);;All Files (*)"
            )
            
            if filepath:
                try:
                    with open(filepath, 'w') as f:
                        f.write(self.current_report)
                    self.status_label.setText(f"✅ Report saved to: {filepath}")
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Error",
                        f"Failed to save report: {e}"
                    )
