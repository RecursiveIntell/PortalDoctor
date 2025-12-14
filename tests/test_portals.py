"""Tests for portals.conf management."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from portal_doctor.diagnostics.portals import (
    read_portals_config,
    write_portals_config,
    backup_portals_config,
    restore_portals_config,
    generate_recommended_config,
    get_config_diff,
    list_backups,
)
from portal_doctor.models import EnvironmentInfo, PortalBackend, PortalsConfig


class TestReadPortalsConfig:
    """Tests for reading portals.conf."""
    
    def test_read_existing_config(self, tmp_path):
        """Test reading an existing config file."""
        config_file = tmp_path / "portals.conf"
        config_file.write_text("""
[preferred]
default=kde
org.freedesktop.impl.portal.Screenshot=gtk
""")
        
        result = read_portals_config(config_file)
        
        assert result is not None
        assert result.default_backend == "kde"
        # ConfigParser lowercases keys
        assert result.interface_backends.get("org.freedesktop.impl.portal.screenshot") == "gtk"
    
    def test_read_nonexistent_config(self, tmp_path):
        """Test reading a file that doesn't exist."""
        config_file = tmp_path / "nonexistent.conf"
        
        result = read_portals_config(config_file)
        
        assert result is None
    
    def test_read_empty_config(self, tmp_path):
        """Test reading an empty config file."""
        config_file = tmp_path / "portals.conf"
        config_file.write_text("")
        
        result = read_portals_config(config_file)
        
        assert result is not None
        assert result.default_backend is None


class TestWritePortalsConfig:
    """Tests for writing portals.conf."""
    
    def test_write_new_config(self, tmp_path):
        """Test writing a new config file."""
        config_file = tmp_path / "portals.conf"
        content = "[preferred]\ndefault=kde\n"
        
        success, message = write_portals_config(content, config_file, create_backup=False)
        
        assert success is True
        assert config_file.exists()
        assert config_file.read_text() == content
    
    def test_write_creates_directory(self, tmp_path):
        """Test that writing creates parent directories."""
        config_file = tmp_path / "subdir" / "portals.conf"
        content = "[preferred]\ndefault=gnome\n"
        
        success, message = write_portals_config(content, config_file, create_backup=False)
        
        assert success is True
        assert config_file.exists()
    
    def test_write_with_backup(self, tmp_path):
        """Test that writing creates a backup of existing file."""
        config_file = tmp_path / "portals.conf"
        backup_dir = tmp_path / "backups"
        
        # Create original file
        config_file.write_text("[preferred]\ndefault=old\n")
        
        # Patch backup directory
        with patch("portal_doctor.diagnostics.portals.BACKUP_DIR", backup_dir):
            success, message = write_portals_config(
                "[preferred]\ndefault=new\n",
                config_file,
                create_backup=True,
            )
        
        assert success is True
        assert backup_dir.exists()
        backups = list(backup_dir.glob("portals.conf.bak-*"))
        assert len(backups) == 1


class TestBackupRestore:
    """Tests for backup and restore functionality."""
    
    def test_backup_creates_file(self, tmp_path):
        """Test that backup creates a timestamped file."""
        config_file = tmp_path / "portals.conf"
        backup_dir = tmp_path / "backups"
        config_file.write_text("[preferred]\ndefault=test\n")
        
        with patch("portal_doctor.diagnostics.portals.BACKUP_DIR", backup_dir):
            success, backup_path = backup_portals_config(config_file)
        
        assert success is True
        assert Path(backup_path).exists()
        assert "portals.conf.bak-" in backup_path
    
    def test_restore_from_backup(self, tmp_path):
        """Test restoring from a backup file."""
        config_file = tmp_path / "portals.conf"
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        # Create backup
        backup_file = backup_dir / "portals.conf.bak-20241213-120000"
        backup_file.write_text("[preferred]\ndefault=backup\n")
        
        with patch("portal_doctor.diagnostics.portals.USER_PORTALS_CONF", config_file):
            success, message = restore_portals_config(str(backup_file))
        
        assert success is True
        assert config_file.exists()
        assert "default=backup" in config_file.read_text()
    
    def test_list_backups(self, tmp_path):
        """Test listing backup files."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        # Create some backups
        (backup_dir / "portals.conf.bak-20241213-100000").write_text("old")
        (backup_dir / "portals.conf.bak-20241213-120000").write_text("new")
        
        with patch("portal_doctor.diagnostics.portals.BACKUP_DIR", backup_dir):
            backups = list_backups()
        
        assert len(backups) == 2
        # Should be sorted newest first
        assert "120000" in str(backups[0])


class TestGenerateRecommendedConfig:
    """Tests for generating recommended configurations."""
    
    def test_generate_for_kde(self):
        """Test generating config for KDE."""
        env = EnvironmentInfo(
            session_type="wayland",
            current_desktop="KDE",
            desktop_session="plasma",
        )
        backends = [
            PortalBackend(name="kde"),
            PortalBackend(name="gtk"),
        ]
        
        config = generate_recommended_config(env, backends)
        
        assert "default=kde" in config
    
    def test_generate_for_gnome(self):
        """Test generating config for GNOME."""
        env = EnvironmentInfo(
            session_type="wayland",
            current_desktop="GNOME",
            desktop_session="gnome",
        )
        backends = [
            PortalBackend(name="gnome"),
            PortalBackend(name="gtk"),
        ]
        
        config = generate_recommended_config(env, backends)
        
        assert "default=gnome" in config
    
    def test_generate_for_hyprland(self):
        """Test generating config for Hyprland."""
        env = EnvironmentInfo(
            session_type="wayland",
            current_desktop="Hyprland",
            desktop_session="hyprland",
            compositor="Hyprland",
        )
        backends = [
            PortalBackend(name="hyprland"),
            PortalBackend(name="gtk"),
        ]
        
        config = generate_recommended_config(env, backends)
        
        assert "default=hyprland" in config
    
    def test_generate_for_sway(self):
        """Test generating config for Sway."""
        env = EnvironmentInfo(
            session_type="wayland",
            current_desktop="sway",
            desktop_session="sway",
            compositor="Sway",
        )
        backends = [
            PortalBackend(name="wlr"),
            PortalBackend(name="gtk"),
        ]
        
        config = generate_recommended_config(env, backends)
        
        assert "default=wlr" in config
    
    def test_generate_fallback_to_gtk(self):
        """Test fallback to GTK when no match."""
        env = EnvironmentInfo(
            session_type="wayland",
            current_desktop="unknown",
            desktop_session="unknown",
        )
        backends = [
            PortalBackend(name="gtk"),
        ]
        
        config = generate_recommended_config(env, backends)
        
        assert "default=gtk" in config


class TestConfigDiff:
    """Tests for configuration diff generation."""
    
    def test_diff_shows_changes(self):
        """Test that diff shows added and removed lines."""
        current = "[preferred]\ndefault=old\n"
        new = "[preferred]\ndefault=new\n"
        
        diff = get_config_diff(current, new)
        
        # unified_diff format: no space after +/-
        assert "-default=old" in diff
        assert "+default=new" in diff
    
    def test_diff_no_changes(self):
        """Test diff with no changes."""
        content = "[preferred]\ndefault=kde\n"
        
        diff = get_config_diff(content, content)
        
        assert "(No changes)" in diff
