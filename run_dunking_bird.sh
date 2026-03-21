#!/bin/bash

# Dunking Bird Smart Launcher - Handles everything automatically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🦆 Starting Dunking Bird..."

# Ensure ydotool daemon is running
if ! pgrep -f ydotoold >/dev/null; then
    echo "🔧 Starting ydotool daemon..."
    sudo ydotoold &
    sleep 2
fi

# Fix socket permissions if needed
if [ -S "/tmp/.ydotool_socket" ]; then
    sudo chmod 666 /tmp/.ydotool_socket 2>/dev/null || true
fi

# Try virtual environment if it exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Launch with error handling
cd "$SCRIPT_DIR"
python3 dunking_bird.py "$@" || {
    echo "❌ Error launching application"
    echo "💡 Try running: ./easy_install.sh"
    exit 1
}
