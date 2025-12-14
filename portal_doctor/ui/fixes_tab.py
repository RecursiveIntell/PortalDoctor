"""Fixes tab for Portal Doctor."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTextEdit, QDialog, QDialogButtonBox,
    QMessageBox, QSizePolicy, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ..models import Finding, Severity, Action, ActionType


class FixCard(QFrame):
    """A card displaying a finding and its fixes."""
    
    def __init__(self, finding: Finding, parent=None):
        super().__init__(parent)
        self.finding = finding
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the card UI."""
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet("""
            FixCard {
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 8px;
                margin: 4px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header with severity icon and title
        header_layout = QHBoxLayout()
        
        severity_icons = {
            Severity.ERROR: ("❌", "#ff6b6b"),
            Severity.WARNING: ("⚠️", "#ffd93d"),
            Severity.INFO: ("ℹ️", "#6bcbff"),
        }
        icon, color = severity_icons.get(self.finding.severity, ("•", "#ccc"))
        
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("", 16))
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(self.finding.title)
        title_label.setFont(QFont("", 12, QFont.Bold))
        title_label.setStyleSheet(f"color: {color};")
        header_layout.addWidget(title_label, 1)
        
        component_label = QLabel(self.finding.component)
        component_label.setStyleSheet("color: #888; font-size: 11px;")
        header_layout.addWidget(component_label)
        
        layout.addLayout(header_layout)
        
        # Details
        details_label = QLabel(self.finding.details)
        details_label.setWordWrap(True)
        details_label.setStyleSheet("color: #bbb; line-height: 1.4;")
        layout.addWidget(details_label)
        
        # Evidence
        if self.finding.evidence:
            evidence_label = QLabel(f"📋 {self.finding.evidence}")
            evidence_label.setWordWrap(True)
            evidence_label.setStyleSheet("""
                color: #999;
                background-color: #222;
                padding: 8px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 11px;
            """)
            layout.addWidget(evidence_label)
        
        # Actions
        if self.finding.recommended_actions:
            actions_layout = QHBoxLayout()
            actions_layout.addStretch()
            
            for action in self.finding.recommended_actions:
                btn = self._create_action_button(action)
                actions_layout.addWidget(btn)
            
            layout.addLayout(actions_layout)
    
    def _create_action_button(self, action: Action) -> QPushButton:
        """Create a button for an action."""
        btn = QPushButton(action.label)
        
        # Style based on action type
        if action.type == ActionType.RESTART_SERVICE:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #198754;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #157347; }
            """)
        elif action.type == ActionType.GENERATE_CONFIG:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0d6efd;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #0b5ed7; }
            """)
        elif action.type == ActionType.OPEN_LOGS:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #5c636a; }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #444;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #555; }
            """)
        
        btn.setToolTip(action.description)
        btn.clicked.connect(lambda: self._execute_action(action))
        
        return btn
    
    def _execute_action(self, action: Action):
        """Execute an action."""
        if action.type == ActionType.GUIDANCE:
            # Just show information
            QMessageBox.information(
                self,
                action.label,
                action.description
            )
            return
        
        if action.type == ActionType.OPEN_LOGS:
            # Run command and show output in dialog
            if action.command:
                self._run_command_with_output(action.label, action.command, is_log_view=True)
            return
        
        if action.type == ActionType.SHOW_COMMAND:
            # Run command and show output
            if action.command:
                self._run_command_with_output(action.label, action.command, is_log_view=True)
            return
        
        if action.type == ActionType.RESTART_SERVICE:
            # Run restart command directly
            if action.execute_callback:
                # Use the callback if provided
                reply = QMessageBox.question(
                    self,
                    "Confirm Action",
                    f"{action.description}\n\nDo you want to proceed?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    success, message = action.execute_callback()
                    if success:
                        QMessageBox.information(self, "Success", f"✅ {message}")
                    else:
                        QMessageBox.warning(self, "Failed", f"❌ {message}")
            elif action.command:
                # Run the command directly
                self._run_command_with_output(action.label, action.command, confirm_first=True)
            return
        
        # For GENERATE_CONFIG actions with preview
        if action.type == ActionType.GENERATE_CONFIG:
            if action.preview_callback:
                preview = action.get_preview()
                
                dialog = ActionConfirmDialog(
                    title=action.label,
                    description=action.description,
                    preview=preview,
                    action=action,
                    parent=self
                )
                
                if dialog.exec() == QDialog.Accepted:
                    if action.execute_callback:
                        success, message = action.execute_callback()
                        if success:
                            QMessageBox.information(self, "Success", f"✅ {message}")
                        else:
                            QMessageBox.warning(self, "Failed", f"❌ {message}")
            return
        
        # Fallback for any action with a command
        if action.command:
            self._run_command_with_output(action.label, action.command, confirm_first=True)
    
    def _run_command_with_output(self, title: str, command: str, 
                                  confirm_first: bool = False, is_log_view: bool = False):
        """Run a command and show its output in a dialog."""
        import subprocess
        
        if confirm_first:
            reply = QMessageBox.question(
                self,
                "Confirm Action",
                f"Run this command?\n\n{command}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply != QMessageBox.Yes:
                return
        
        # Show running dialog
        dialog = CommandOutputDialog(title, command, parent=self)
        dialog.exec()


class CommandOutputDialog(QDialog):
    """Dialog that runs a command and shows its output."""
    
    def __init__(self, title: str, command: str, parent=None):
        super().__init__(parent)
        self.command = command
        
        self.setWindowTitle(title)
        self.setMinimumSize(700, 500)
        
        layout = QVBoxLayout(self)
        
        # Command display
        cmd_label = QLabel(f"Command: <code>{command}</code>")
        cmd_label.setTextFormat(Qt.RichText)
        cmd_label.setWordWrap(True)
        cmd_label.setStyleSheet("background-color: #2d2d2d; padding: 8px; border-radius: 4px;")
        layout.addWidget(cmd_label)
        
        # Output area
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ddd;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.output_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.copy_btn = QPushButton("📋 Copy Output")
        self.copy_btn.clicked.connect(self._copy_output)
        btn_layout.addWidget(self.copy_btn)
        
        btn_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
        
        # Run command when dialog shows
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._run_command)
    
    def _run_command(self):
        """Execute the command and show output."""
        import subprocess
        import shlex
        
        self.output_edit.append("Running command...\n")
        self.output_edit.append("-" * 50 + "\n")
        
        try:
            # Only use bash -c for commands that need shell features
            # (pipes, redirects, semicolons, etc.)
            shell_operators = ['|', '>', '<', ';', '&&', '||', '`', '$(',  '2>', '2>&1']
            needs_shell = any(op in self.command for op in shell_operators)
            
            if needs_shell:
                # Command needs shell features - use bash -c
                result = subprocess.run(
                    ["bash", "-c", self.command],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            else:
                # Simple command - run directly without shell
                try:
                    args = shlex.split(self.command)
                    result = subprocess.run(
                        args,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                except ValueError:
                    # shlex.split failed, fall back to bash
                    result = subprocess.run(
                        ["bash", "-c", self.command],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
            
            if result.stdout:
                self.output_edit.append(result.stdout)
            if result.stderr:
                self.output_edit.append(f"\n[stderr]\n{result.stderr}")
            
            self.output_edit.append("\n" + "-" * 50)
            
            if result.returncode == 0:
                self.output_edit.append("\n✅ Command completed successfully")
            else:
                self.output_edit.append(f"\n⚠️ Command exited with code {result.returncode}")
                
        except subprocess.TimeoutExpired:
            self.output_edit.append("\n❌ Command timed out after 60 seconds")
        except Exception as e:
            self.output_edit.append(f"\n❌ Error running command: {e}")
    
    def _copy_output(self):
        """Copy output to clipboard."""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.output_edit.toPlainText())


class CommandPreviewDialog(QDialog):
    """Dialog showing a command to copy."""
    
    def __init__(self, title: str, command: str, description: str, parent=None):
        super().__init__(parent)
        self.command = command
        
        self.setWindowTitle(title)
        self.setMinimumSize(500, 200)
        
        layout = QVBoxLayout(self)
        
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        self.command_edit = QTextEdit()
        self.command_edit.setPlainText(command)
        self.command_edit.setReadOnly(True)
        self.command_edit.setMaximumHeight(100)
        layout.addWidget(self.command_edit)
        
        btn_layout = QHBoxLayout()
        
        copy_btn = QPushButton("📋 Copy Command")
        copy_btn.clicked.connect(self._copy_command)
        btn_layout.addWidget(copy_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def _copy_command(self):
        """Copy command to clipboard."""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.command)


class ActionConfirmDialog(QDialog):
    """Dialog to confirm an action with preview showing diff."""
    
    def __init__(self, title: str, description: str, preview: str, 
                 action: Action, parent=None):
        super().__init__(parent)
        self.action = action
        self.preview = preview
        self.diff_text = None
        self.showing_diff = True
        
        self.setWindowTitle(f"Confirm: {title}")
        self.setMinimumSize(700, 500)
        
        layout = QVBoxLayout(self)
        
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # View toggle row
        toggle_row = QHBoxLayout()
        
        preview_label = QLabel("Preview:")
        preview_label.setFont(QFont("", 10, QFont.Bold))
        toggle_row.addWidget(preview_label)
        
        toggle_row.addStretch()
        
        self.toggle_btn = QPushButton("📄 Show Full Config")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.clicked.connect(self._toggle_view)
        toggle_row.addWidget(self.toggle_btn)
        
        layout.addLayout(toggle_row)
        
        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ddd;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.preview_edit)
        
        # Generate and show diff
        self._generate_diff()
        self._show_diff()
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.button(QDialogButtonBox.Ok).setText("Apply Changes")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _generate_diff(self):
        """Generate a unified diff between current and new config."""
        from ..diagnostics.portals import read_portals_config, get_config_diff
        
        current_config = read_portals_config()
        current_text = ""
        if current_config:
            lines = []
            for section, values in current_config.items():
                lines.append(f"[{section}]")
                for key, value in values.items():
                    lines.append(f"{key}={value}")
                lines.append("")
            current_text = "\n".join(lines)
        
        self.diff_text = get_config_diff(current_text, self.preview)
    
    def _show_diff(self):
        """Show the diff view with syntax highlighting."""
        if not self.diff_text or self.diff_text == "(No changes)":
            self.preview_edit.setPlainText("No changes detected.")
            return
        
        # Color-code the diff
        html_lines = ['<pre style="font-family: monospace; margin: 0;">']
        for line in self.diff_text.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                html_lines.append(f'<span style="color: #a6e3a1;">  {self._escape_html(line)}</span>')
            elif line.startswith('-') and not line.startswith('---'):
                html_lines.append(f'<span style="color: #f38ba8;">  {self._escape_html(line)}</span>')
            elif line.startswith('@@'):
                html_lines.append(f'<span style="color: #89b4fa;">{self._escape_html(line)}</span>')
            else:
                html_lines.append(f'<span style="color: #cdd6f4;">{self._escape_html(line)}</span>')
        html_lines.append('</pre>')
        
        self.preview_edit.setHtml('\n'.join(html_lines))
    
    def _escape_html(self, text):
        """Escape HTML special characters."""
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    def _toggle_view(self):
        """Toggle between diff and full config view."""
        self.showing_diff = not self.showing_diff
        
        if self.showing_diff:
            self.toggle_btn.setText("📄 Show Full Config")
            self._show_diff()
        else:
            self.toggle_btn.setText("📊 Show Diff")
            self.preview_edit.setPlainText(self.preview)


class BackupBrowserDialog(QDialog):
    """Dialog for browsing and restoring backups."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_backup = None
        self._setup_ui()
        self._load_backups()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Backup Browser")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Available Backups")
        header.setFont(QFont("", 12, QFont.Bold))
        layout.addWidget(header)
        
        info = QLabel("Select a backup to preview and restore.")
        info.setStyleSheet("color: #aaa;")
        layout.addWidget(info)
        
        # Backup list
        self.backup_list = QListWidget()
        self.backup_list.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:selected {
                background-color: #0d6efd;
            }
        """)
        self.backup_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.backup_list)
        
        # Preview area
        preview_label = QLabel("Preview:")
        preview_label.setFont(QFont("", 10, QFont.Bold))
        layout.addWidget(preview_label)
        
        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setMaximumHeight(150)
        self.preview_edit.setPlaceholderText("Select a backup to preview its contents")
        layout.addWidget(self.preview_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.restore_btn = QPushButton("🔄 Restore Selected")
        self.restore_btn.setEnabled(False)
        self.restore_btn.setStyleSheet("""
            QPushButton {
                background-color: #198754;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #157347; }
            QPushButton:disabled { background-color: #444; color: #888; }
        """)
        self.restore_btn.clicked.connect(self._restore_selected)
        btn_layout.addWidget(self.restore_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_backups(self):
        """Load available backups into the list."""
        from ..diagnostics.portals import list_backups
        
        backups = list_backups()
        
        if not backups:
            item = QListWidgetItem("No backups available")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.backup_list.addItem(item)
            return
        
        for backup_path in backups:
            # Format the timestamp nicely
            name = backup_path.name
            # Extract timestamp from filename like portals.conf.bak-20241213-120000
            if "-" in name:
                parts = name.split("-")
                if len(parts) >= 3:
                    date_str = parts[1]  # 20241213
                    time_str = parts[2]  # 120000
                    try:
                        formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:]}"
                        display = f"📄 {formatted}"
                    except (IndexError, ValueError):
                        display = f"📄 {name}"
                else:
                    display = f"📄 {name}"
            else:
                display = f"📄 {name}"
            
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, str(backup_path))
            self.backup_list.addItem(item)
    
    def _on_selection_changed(self):
        """Handle backup selection change."""
        items = self.backup_list.selectedItems()
        if not items:
            self.restore_btn.setEnabled(False)
            self.preview_edit.clear()
            return
        
        backup_path = items[0].data(Qt.UserRole)
        if not backup_path:
            self.restore_btn.setEnabled(False)
            return
        
        self.restore_btn.setEnabled(True)
        self.selected_backup = backup_path
        
        # Load preview
        try:
            from pathlib import Path
            content = Path(backup_path).read_text()
            self.preview_edit.setPlainText(content)
        except Exception as e:
            self.preview_edit.setPlainText(f"Error reading backup: {e}")
    
    def _restore_selected(self):
        """Restore the selected backup."""
        if not self.selected_backup:
            return
        
        from ..diagnostics.portals import restore_portals_config
        
        reply = QMessageBox.question(
            self,
            "Confirm Restore",
            f"Are you sure you want to restore from this backup?\n\nThis will overwrite your current portals.conf.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, message = restore_portals_config(self.selected_backup)
            if success:
                QMessageBox.information(self, "Success", f"✅ {message}")
                self.accept()
            else:
                QMessageBox.warning(self, "Failed", f"❌ {message}")


class FixesTab(QWidget):
    """Fixes tab showing recommended actions for findings."""
    
    def __init__(self):
        super().__init__()
        self.findings = []
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header = QLabel("Recommended Fixes")
        header.setFont(QFont("", 16, QFont.Bold))
        layout.addWidget(header)
        
        subtitle = QLabel(
            "Review each finding below and apply fixes as needed. "
            "All changes show a preview first and can be undone."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #aaa; margin-bottom: 8px;")
        layout.addWidget(subtitle)
        
        # Restore buttons row
        restore_row = QHBoxLayout()
        restore_row.addStretch()
        
        undo_btn = QPushButton("↩️ Undo Last Change")
        undo_btn.setToolTip("Restore portals.conf from the most recent backup")
        undo_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #5c636a; }
        """)
        undo_btn.clicked.connect(self._undo_last_change)
        restore_row.addWidget(undo_btn)
        
        browse_btn = QPushButton("📂 Browse Backups")
        browse_btn.setToolTip("Browse and restore from all available backups")
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #0b5ed7; }
        """)
        browse_btn.clicked.connect(self._browse_backups)
        restore_row.addWidget(browse_btn)
        
        layout.addLayout(restore_row)
        
        # Scrollable area for fix cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(12)
        self.cards_layout.addStretch()
        
        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll, 1)
        
        # No findings message
        self.no_findings_label = QLabel("✅ No issues to fix!")
        self.no_findings_label.setAlignment(Qt.AlignCenter)
        self.no_findings_label.setFont(QFont("", 14))
        self.no_findings_label.setStyleSheet("color: #6bcbff; margin: 32px;")
        self.no_findings_label.hide()
        layout.addWidget(self.no_findings_label)
    
    def update_findings(self, findings: list[Finding]):
        """Update the displayed findings."""
        self.findings = findings
        
        # Clear existing cards
        while self.cards_layout.count() > 1:  # Keep the stretch
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Filter to actionable findings (not just info)
        actionable = [f for f in findings if f.recommended_actions]
        
        if not actionable:
            self.no_findings_label.show()
            return
        
        self.no_findings_label.hide()
        
        # Add cards for each finding
        for finding in actionable:
            card = FixCard(finding)
            self.cards_layout.insertWidget(
                self.cards_layout.count() - 1,  # Before stretch
                card
            )
    
    def _undo_last_change(self):
        """Restore from the most recent backup."""
        from ..diagnostics.portals import restore_portals_config, get_latest_backup
        
        latest = get_latest_backup()
        if not latest:
            QMessageBox.information(
                self,
                "No Backups",
                "No backup files found. Changes you make will create backups automatically."
            )
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Undo",
            f"Restore portals.conf from the last backup?\n\nBackup: {latest.name}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, message = restore_portals_config()
            if success:
                QMessageBox.information(self, "Success", f"✅ {message}")
            else:
                QMessageBox.warning(self, "Failed", f"❌ {message}")
    
    def _browse_backups(self):
        """Open the backup browser dialog."""
        dialog = BackupBrowserDialog(self)
        dialog.exec()

