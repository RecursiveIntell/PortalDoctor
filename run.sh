#!/bin/bash
# Portal Doctor launcher

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check and install dependencies if needed
if ! python3 -c "import dbus_next, PySide6" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install --user dbus-next PySide6
fi

# Set app ID to suppress Qt portal registration warning
export QT_QPA_PLATFORMTHEME_APP_ID="portal-doctor"
export DESKTOP_FILE_HINT="portal-doctor"

# Suppress the harmless Qt portal warning
export QT_LOGGING_RULES="qt.qpa.services=false"

# Run the application
python3 -m portal_doctor "$@"
