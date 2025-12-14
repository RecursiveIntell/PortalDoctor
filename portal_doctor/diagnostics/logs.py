"""Journal log collection and sanitization for Portal Doctor."""

import os
import re
import subprocess
from typing import Optional


def collect_journal_logs(services: list[str], since: str = "30 min ago",
                         max_lines: int = 200, timeout: int = 15) -> dict[str, str]:
    """Collect journal logs for multiple services.
    
    Args:
        services: List of service names to collect logs for
        since: Time specification for --since
        max_lines: Maximum lines per service
        timeout: Timeout in seconds
        
    Returns:
        Dictionary mapping service name to log output
    """
    logs = {}
    for service in services:
        logs[service] = _get_journal_for_service(service, since, max_lines, timeout)
    return logs


def _get_journal_for_service(service: str, since: str, max_lines: int, timeout: int) -> str:
    """Get journal logs for a single service."""
    try:
        result = subprocess.run(
            [
                "journalctl", "--user",
                "-u", service,
                "--since", since,
                "--no-pager",
                "-n", str(max_lines),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        output = result.stdout.strip()
        if not output or "No entries" in output:
            return "(No log entries found)"
        
        return sanitize_log_output(output)
        
    except subprocess.TimeoutExpired:
        return f"(Timeout collecting logs for {service})"
    except FileNotFoundError:
        return "(journalctl not found)"
    except subprocess.SubprocessError as e:
        return f"(Error: {e})"


def collect_combined_logs(services: list[str], since: str = "30 min ago",
                           max_lines: int = 500, timeout: int = 30) -> str:
    """Collect combined and chronologically sorted logs for multiple services.
    
    Args:
        services: List of service names
        since: Time specification for --since
        max_lines: Maximum total lines
        timeout: Timeout in seconds
        
    Returns:
        Combined log output
    """
    try:
        # Build command with multiple -u flags
        cmd = ["journalctl", "--user", "--since", since, "--no-pager", "-n", str(max_lines)]
        for service in services:
            cmd.extend(["-u", service])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        output = result.stdout.strip()
        if not output or "No entries" in output:
            return "(No log entries found)"
        
        return sanitize_log_output(output)
        
    except subprocess.TimeoutExpired:
        return "(Timeout collecting combined logs)"
    except FileNotFoundError:
        return "(journalctl not found)"
    except subprocess.SubprocessError as e:
        return f"(Error: {e})"


def sanitize_log_output(output: str, max_length: int = 50000) -> str:
    """Sanitize log output for safe sharing.
    
    - Replaces /home/username/ with /home/<user>/
    - Removes or masks potential sensitive patterns
    - Limits total output size
    
    Args:
        output: Raw log output
        max_length: Maximum output length in characters
        
    Returns:
        Sanitized log output
    """
    # Get current username to sanitize
    username = os.environ.get("USER", os.environ.get("LOGNAME", ""))
    home_dir = os.environ.get("HOME", "")
    
    result = output
    
    # Replace home directory path
    if home_dir:
        result = result.replace(home_dir, "/home/<user>")
    
    # Replace username in paths
    if username:
        # Pattern: /home/username/
        result = re.sub(rf"/home/{re.escape(username)}(?=/|$|\s)", "/home/<user>", result)
        # Pattern: username@ (like in SSH)
        result = re.sub(rf"\b{re.escape(username)}@", "<user>@", result)
    
    # Remove potential tokens/keys (long alphanumeric strings)
    result = re.sub(r"\b[a-zA-Z0-9]{40,}\b", "<redacted>", result)
    
    # Truncate if too long
    if len(result) > max_length:
        truncated_lines = result[:max_length].rsplit("\n", 1)[0]
        result = truncated_lines + f"\n\n... (output truncated, {len(output) - max_length} characters omitted)"
    
    return result


def get_relevant_log_services() -> list[str]:
    """Get list of services relevant for portal diagnostics.
    
    Returns:
        List of service names to collect logs for
    """
    return [
        "xdg-desktop-portal.service",
        "xdg-desktop-portal-kde.service",
        "xdg-desktop-portal-gnome.service",
        "xdg-desktop-portal-gtk.service",
        "xdg-desktop-portal-wlr.service",
        "xdg-desktop-portal-hyprland.service",
        "pipewire.service",
        "wireplumber.service",
    ]


def extract_error_lines(log_output: str, max_errors: int = 20) -> list[str]:
    """Extract lines that look like errors from log output.
    
    Args:
        log_output: Log output to scan
        max_errors: Maximum number of error lines to return
        
    Returns:
        List of error lines
    """
    error_patterns = [
        r"error",
        r"failed",
        r"fatal",
        r"critical",
        r"exception",
        r"denied",
        r"refused",
        r"timeout",
        r"not found",
        r"missing",
    ]
    
    pattern = re.compile("|".join(error_patterns), re.IGNORECASE)
    
    errors = []
    for line in log_output.split("\n"):
        if pattern.search(line):
            errors.append(line.strip())
            if len(errors) >= max_errors:
                break
    
    return errors
