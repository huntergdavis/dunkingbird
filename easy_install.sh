#!/bin/bash

# Dunking Bird - Ultimate One-Click Install and Run
# This script does EVERYTHING: install, configure, and launch

set -e

# Colors for beautiful output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Fancy banner
show_banner() {
    echo -e "${CYAN}"
    echo "  ██████  ██    ██ ███    ██ ██   ██ ██ ███    ██  ██████  "
    echo "  ██   ██ ██    ██ ████   ██ ██  ██  ██ ████   ██ ██       "
    echo "  ██   ██ ██    ██ ██ ██  ██ █████   ██ ██ ██  ██ ██   ███ "
    echo "  ██   ██ ██    ██ ██  ██ ██ ██  ██  ██ ██  ██ ██ ██    ██ "
    echo "  ██████   ██████  ██   ████ ██   ██ ██ ██   ████  ██████  "
    echo -e "${NC}"
    echo -e "  ${PURPLE}🦆 BIRD - Automated Text Sender for Coding Agents${NC}"
    echo -e "  ${GREEN}✨ One-Click Install & Launch ✨${NC}"
    echo ""
}

# Animated loading
loading_animation() {
    local pid=$1
    local delay=0.1
    local spinstr='|/-\'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# Logging with timestamp
log() {
    echo -e "[$(date +'%H:%M:%S')] $1"
}

# Success with checkmark
success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Error with X
error() {
    echo -e "${RED}❌ $1${NC}"
}

# Info with arrow
info() {
    echo -e "${BLUE}➡️  $1${NC}"
}

# Warning with triangle
warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if we can run without user input
check_sudo_nopass() {
    if sudo -n true 2>/dev/null; then
        return 0
    else
        warning "This script needs sudo access for system packages"
        warning "You may be prompted for your password"
        return 1
    fi
}

# Check distribution compatibility
check_distro() {
    if ! command -v apt &> /dev/null; then
        error "This script requires apt package manager (Debian/Ubuntu-based systems)"
        exit 1
    fi

    # Check if sudo is available
    if ! command -v sudo &> /dev/null; then
        error "sudo is required but not installed"
        exit 1
    fi
}

# Update package lists
update_packages() {
    info "Updating package lists..."
    local max_attempts=3
    for attempt in $(seq 1 $max_attempts); do
        if sudo apt update -qq &>/dev/null; then
            success "Package lists updated"
            return 0
        else
            warning "Package update attempt $attempt failed, retrying..."
            sleep 2
        fi
    done
    error "Failed to update package lists after $max_attempts attempts"
    return 1
}

# Install system dependencies with robust error handling
install_system_deps() {
    info "Installing system dependencies..."
    local install_gui=false
    if [[ "$*" == *"--gui"* ]]; then
        install_gui=true
    fi

    local packages=(
        "python3"
        "python3-pip"
        "python3-venv"
        "ydotool"
        "cargo"
        "rustc"
        "libdbus-1-dev"
        "pkg-config"
        "xclip"
        "xdotool"
        "curl"
        "coreutils"
        "procps"
    )
    if [ "$install_gui" = true ]; then
        packages+=("python3-tk")
    fi

    # Check which packages are missing and available on this distro release.
    local missing_packages=()
    for package in "${packages[@]}"; do
        if ! dpkg -l | grep -q "^ii.*$package "; then
            if apt-cache show "$package" >/dev/null 2>&1; then
                missing_packages+=("$package")
            else
                warning "Package '$package' is not available in the configured apt repos; skipping"
            fi
        fi
    done

    if [ ${#missing_packages[@]} -eq 0 ]; then
        success "All system dependencies already installed"
        return 0
    fi

    info "Installing missing packages: ${missing_packages[*]}"
    export DEBIAN_FRONTEND=noninteractive

    if sudo apt install -y "${missing_packages[@]}" &>/dev/null; then
        success "System dependencies installed successfully"
        return 0
    else
        error "Failed to install some system dependencies"
        return 1
    fi
}

# Install and verify Python dependencies
install_python_deps() {
    info "Setting up Python dependencies..."

    # Check if we need to create a virtual environment
    local use_venv=false
    if [[ "$*" == *"--venv"* ]] || [[ "$*" == *"-v"* ]]; then
        use_venv=true
    fi

    if [ "$use_venv" = true ]; then
        info "Creating Python virtual environment..."
        if [ ! -d "./venv" ]; then
            if python3 -m venv "./venv" &>/dev/null; then
                success "Virtual environment created"
            else
                error "Failed to create virtual environment"
                return 1
            fi
        fi

        # Activate virtual environment
        source "./venv/bin/activate"
        success "Virtual environment activated"

        # Upgrade pip in venv
        pip install --upgrade pip &>/dev/null || true
    fi

    # Install Python packages from requirements.txt
    if [ -f "requirements.txt" ]; then
        info "Installing Python packages from requirements.txt..."
        if [ "$use_venv" = true ]; then
            pip install -r requirements.txt &>/dev/null || warning "Some Python packages failed to install in venv"
        else
            python3 -m pip install --user -r requirements.txt &>/dev/null || warning "Some Python packages failed to install for user"
        fi
    fi

    if [[ "$*" == *"--gui"* ]]; then
        info "Verifying optional GUI fallback dependency..."
        if python3 -c "import pynput; print('OK')" &>/dev/null; then
            success "pynput installed and working"
        else
            warning "pynput not found, installing..."
            if command -v pip3 >/dev/null; then
                if [ "$use_venv" = true ]; then
                    pip3 install pynput &>/dev/null || true
                else
                    pip3 install --user pynput &>/dev/null || true
                fi
            fi
        fi
    fi

    success "Python environment configured"
    return 0
}

# Install KDE Wayland window capture/focus backend
install_kdotool_backend() {
    if [ "${XDG_SESSION_TYPE:-}" != "wayland" ]; then
        return 0
    fi

    local desktop="${XDG_CURRENT_DESKTOP:-}${XDG_SESSION_DESKTOP:-}"
    if [[ "${desktop,,}" != *kde* && "${desktop,,}" != *plasma* ]]; then
        return 0
    fi

    export PATH="$HOME/.local/bin:$PATH"
    if command -v kdotool >/dev/null 2>&1; then
        success "kdotool already installed"
        return 0
    fi

    info "Installing kdotool for KDE Wayland capture/focus..."
    if cargo install --git https://github.com/jinliu/kdotool --root "$HOME/.local" &>/dev/null; then
        success "kdotool installed to $HOME/.local/bin"
        return 0
    fi

    warning "Could not install kdotool automatically; window capture may be limited on KDE Wayland"
    return 0
}

# Configure ydotool daemon and permissions
setup_ydotool() {
    info "Configuring ydotool for input automation..."
    local runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    local socket_path="${YDOTOOL_SOCKET:-$runtime_dir/.ydotool_socket}"
    export YDOTOOL_SOCKET="$socket_path"
    mkdir -p "$(dirname "$socket_path")"

    # Kill any existing ydotool processes
    sudo pkill ydotoold 2>/dev/null || true
    sleep 1

    # Start ydotool daemon with multiple methods
    if ! pgrep -f ydotoold >/dev/null; then
        # Method 1: Direct daemon start
        sudo ydotoold --socket-path="$socket_path" --socket-own=$(id -u):$(id -g) 2>/dev/null &

        # Give it time to start
        sleep 3

        # Method 2: Try systemd if available
        if ! pgrep -f ydotoold >/dev/null && command -v systemctl >/dev/null; then
            sudo systemctl start ydotool 2>/dev/null || true
            sleep 2
        fi

        # Method 3: Fallback manual start
        if ! pgrep -f ydotoold >/dev/null; then
            nohup sudo ydotoold --socket-path="$socket_path" --socket-own="$(id -u):$(id -g)" &>/dev/null &
            sleep 2
        fi
    fi

    # Fix socket permissions aggressively after the daemon recreates the socket.
    for _ in 1 2 3 4 5; do
        [ -S "$socket_path" ] && break
        sleep 1
    done
    if [ -S "$socket_path" ]; then
        sudo chown "$(id -u):$(id -g)" "$socket_path" 2>/dev/null || true
        sudo chmod 600 "$socket_path" 2>/dev/null || true
    fi

    # Add user to input group if needed
    if ! groups "$USER" | grep -q input; then
        sudo usermod -a -G input "$USER" 2>/dev/null || warning "Could not add user to input group"
    fi

    # Test ydotool functionality
    if timeout 3 ydotool type "" 2>/dev/null; then
        success "ydotool configured and working"
        return 0
    else
        warning "ydotool may need manual configuration"
        return 1
    fi
}

# Create smart launcher script
create_launcher() {
    info "Creating smart launcher..."

    cat > "run_dunking_bird.sh" << 'EOF'
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
EOF

    chmod +x "run_dunking_bird.sh"
    success "Smart launcher created"
    return 0
}

# Test system functionality
test_functionality() {
    info "Running system tests..."

    # Test 1: Python and dependencies
    if python3 -c "import curses; import threading; import subprocess; import os; import time" &>/dev/null; then
        success "Python environment working"
    else
        error "Python environment test failed"
        return 1
    fi

    # Test 2: ydotool basic functionality
    if timeout 5 ydotool type --key-delay 100 "" &>/dev/null; then
        success "ydotool working"
    else
        warning "ydotool test failed - you may need to check permissions or restart"
    fi

    # Test 3: GUI display
    if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
        success "Display server available"
    else
        warning "No display server detected"
    fi

    success "System tests completed"
    return 0
}

# Main installation process
run_installation() {
    info "Running comprehensive installation..."

    check_distro
    update_packages || return 1
    install_system_deps || return 1
    install_python_deps "$@" || return 1
    install_kdotool_backend || return 1
    setup_ydotool || return 1
    create_launcher || return 1
    test_functionality || return 1

    success "Installation completed successfully"
    return 0
}

# Main installation process
main() {
    show_banner

    info "Starting one-click installation process..."
    log "Installation directory: $(pwd)"

    # Check prerequisites
    check_sudo_nopass

    # Run the main installation.
    echo -e "${CYAN}🔧 Running core installation...${NC}"
    if ! run_installation "$@"; then
        error "Installation failed!"
        exit 1
    fi

    echo ""
    echo -e "${GREEN}🎉 INSTALLATION COMPLETE! 🎉${NC}"
    echo ""
    echo -e "${YELLOW}Launch options:${NC}"
    echo -e "  ${GREEN}Option 1 (Default TUI):${NC} ./run_dunking_bird.sh"
    echo -e "  ${GREEN}Option 2 (Direct TUI):${NC} python3 dunking_bird_tui.py"
    echo -e "  ${GREEN}Option 3 (GUI):${NC} ./run_dunking_bird.sh --gui"
    echo ""
    echo -e "${CYAN}💡 Tip: Use window capture for precise targeting!${NC}"

    # Auto-launch option
    echo ""
    read -p "🚀 Launch Dunking Bird now? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}🦆 Launching Dunking Bird...${NC}"
        ./run_dunking_bird.sh &
        echo -e "${GREEN}✅ Application started! Check your desktop.${NC}"
    else
        echo -e "${BLUE}👍 Ready to go! Run ./run_dunking_bird.sh when you're ready.${NC}"
    fi
}

# Error handling
trap 'echo -e "\n${RED}❌ Installation interrupted${NC}"' INT TERM

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --venv, -v    Install in Python virtual environment"
            echo "  --help, -h    Show this help message"
            echo ""
            echo "The ultimate one-click install script for Dunking Bird!"
            echo "Installs all dependencies, configures the system, and creates a launcher."
            exit 0
            ;;
        *)
            # Pass unknown arguments to main
            break
            ;;
    esac
    shift
done

# Run main function
main "$@"
