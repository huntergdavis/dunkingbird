#!/bin/bash

# Dunking Bird Smart Launcher - Handles everything automatically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/.local/bin:$PATH"

mode="tui"
if [ "${1:-}" = "--gui" ]; then
    mode="gui"
    shift
elif [ "${1:-}" = "--tui" ]; then
    shift
fi

echo "🦆 Starting Dunking Bird ($mode)..."

# Make sure the ydotool socket is usable even if the daemon recreates it as root-only.
ensure_ydotool_ready() {
    local runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    local socket_path="${YDOTOOL_SOCKET:-$runtime_dir/.ydotool_socket}"
    local waited=0

    export YDOTOOL_SOCKET="$socket_path"
    mkdir -p "$(dirname "$socket_path")"

    if [ ! -S "$socket_path" ] || ! timeout 2 ydotool type "" >/dev/null 2>&1; then
        echo "🔧 Starting ydotool daemon..."
        sudo pkill ydotoold 2>/dev/null || true
        nohup sudo ydotoold --socket-path="$socket_path" --socket-own="$(id -u):$(id -g)" >/dev/null 2>&1 &
    fi

    while [ $waited -lt 50 ]; do
        if [ -S "$socket_path" ]; then
            break
        fi
        sleep 0.1
        waited=$((waited + 1))
    done

    if [ -S "$socket_path" ]; then
        sudo chown "$(id -u):$(id -g)" "$socket_path" 2>/dev/null || true
        sudo chmod 600 "$socket_path" 2>/dev/null || true
    fi
}

# Check if virtual environment exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    echo "Activating virtual environment..."
    source "$SCRIPT_DIR/venv/bin/activate"
fi

ensure_ydotool_ready

# Launch with error handling
cd "$SCRIPT_DIR"
if [ "$mode" = "gui" ]; then
    app="dunking_bird.py"
else
    app="dunking_bird_tui.py"
fi

python3 "$app" "$@" || {
    echo "❌ Error launching application"
    echo "💡 Try running the installation script again"
    exit 1
}
