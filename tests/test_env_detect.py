"""Tests for environment detection."""

import os
from unittest.mock import patch

import pytest

from portal_doctor.diagnostics.env_detect import (
    detect_environment,
    _detect_session_type,
    _detect_current_desktop,
    _detect_compositor,
)
from portal_doctor.models import EnvironmentInfo


class TestDetectSessionType:
    """Tests for session type detection."""
    
    def test_wayland_session(self):
        """Test detection of Wayland session."""
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}, clear=False):
            result = _detect_session_type()
            assert result == "wayland"
    
    def test_x11_session(self):
        """Test detection of X11 session."""
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"}, clear=False):
            result = _detect_session_type()
            assert result == "x11"
    
    def test_tty_session(self):
        """Test detection of TTY session."""
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "tty"}, clear=False):
            result = _detect_session_type()
            assert result == "tty"
    
    def test_fallback_wayland_display(self):
        """Test fallback to WAYLAND_DISPLAY."""
        env = {
            "XDG_SESSION_TYPE": "",
            "WAYLAND_DISPLAY": "wayland-0",
        }
        with patch.dict(os.environ, env, clear=False):
            result = _detect_session_type()
            assert result == "wayland"
    
    def test_fallback_display(self):
        """Test fallback to DISPLAY for X11."""
        env = {
            "XDG_SESSION_TYPE": "",
            "WAYLAND_DISPLAY": "",
            "DISPLAY": ":0",
        }
        with patch.dict(os.environ, env, clear=False):
            result = _detect_session_type()
            assert result == "x11"


class TestDetectCurrentDesktop:
    """Tests for desktop detection."""
    
    def test_kde_desktop(self):
        """Test KDE detection."""
        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "KDE"}, clear=False):
            result = _detect_current_desktop()
            assert result == "KDE"
    
    def test_gnome_desktop(self):
        """Test GNOME detection."""
        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "GNOME"}, clear=False):
            result = _detect_current_desktop()
            assert result == "GNOME"
    
    def test_sway_desktop(self):
        """Test Sway detection."""
        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "sway"}, clear=False):
            result = _detect_current_desktop()
            assert result == "sway"
    
    def test_hyprland_fallback(self):
        """Test Hyprland detection via signature."""
        env = {
            "XDG_CURRENT_DESKTOP": "",
            "DESKTOP_SESSION": "",
            "KDE_FULL_SESSION": "",
            "GNOME_DESKTOP_SESSION_ID": "",
            "HYPRLAND_INSTANCE_SIGNATURE": "12345",
        }
        with patch.dict(os.environ, env, clear=False):
            result = _detect_current_desktop()
            assert result == "Hyprland"
    
    def test_sway_fallback(self):
        """Test Sway detection via SWAYSOCK."""
        env = {
            "XDG_CURRENT_DESKTOP": "",
            "DESKTOP_SESSION": "",
            "KDE_FULL_SESSION": "",
            "GNOME_DESKTOP_SESSION_ID": "",
            "HYPRLAND_INSTANCE_SIGNATURE": "",
            "SWAYSOCK": "/run/user/1000/sway-ipc.sock",
        }
        with patch.dict(os.environ, env, clear=False):
            result = _detect_current_desktop()
            assert result == "sway"


class TestEnvironmentInfo:
    """Tests for EnvironmentInfo model."""
    
    def test_is_wayland(self):
        """Test is_wayland property."""
        env = EnvironmentInfo(
            session_type="wayland",
            current_desktop="KDE",
            desktop_session="plasma",
        )
        assert env.is_wayland is True
        assert env.is_x11 is False
    
    def test_is_kde(self):
        """Test is_kde property."""
        env = EnvironmentInfo(
            session_type="wayland",
            current_desktop="KDE",
            desktop_session="plasma",
        )
        assert env.is_kde is True
        assert env.is_gnome is False
    
    def test_is_gnome(self):
        """Test is_gnome property."""
        env = EnvironmentInfo(
            session_type="wayland",
            current_desktop="GNOME",
            desktop_session="gnome",
        )
        assert env.is_gnome is True
        assert env.is_kde is False
    
    def test_is_wlroots_sway(self):
        """Test is_wlroots for Sway."""
        env = EnvironmentInfo(
            session_type="wayland",
            current_desktop="sway",
            desktop_session="sway",
            compositor="Sway",
        )
        assert env.is_wlroots is True
    
    def test_is_hyprland(self):
        """Test is_hyprland property."""
        env = EnvironmentInfo(
            session_type="wayland",
            current_desktop="Hyprland",
            desktop_session="hyprland",
            compositor="Hyprland",
        )
        assert env.is_hyprland is True
        assert env.is_wlroots is True  # Hyprland is also wlroots-based
