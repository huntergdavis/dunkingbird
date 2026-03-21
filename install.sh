#!/bin/bash

# Dunking Bird - Robust Installation Script
# Installs and configures all dependencies for modern Linux systems

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_LOG="$SCRIPT_DIR/install.log"

# Logging function
log() {
    echo -e "$1" | tee -a "$INSTALL_LOG"
}

# Error handling
error_exit() {
    log "${RED}ERROR: $1${NC}"
    log "${RED}Installation failed. Check $INSTALL_LOG for details.${NC}"
    exit 1
}

# Success message
success() {
    log "${GREEN}✓ $1${NC}"
}

# Warning message
warning() {
    log "${YELLOW}⚠ $1${NC}"
}

# Info message
info() {
    log "${BLUE}ℹ $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        error_exit "Do not run this script as root. Run as a regular user with sudo access."
    fi
}

# Check distribution
check_distro() {
    if ! command -v apt &> /dev/null; then
        error_exit "This script requires apt package manager (Debian/Ubuntu-based systems)"
    fi

    # Check if sudo is available
    if ! command -v sudo &> /dev/null; then
        error_exit "sudo is required but not installed"
    fi
}

# Update package lists
update_packages() {
    info "Updating package lists..."
    if ! sudo apt update &>> "$INSTALL_LOG"; then
        error_exit "Failed to update package lists"
    fi
    success "Package lists updated"
}

# Install system dependencies
install_system_deps() {
    info "Installing system dependencies..."

    local packages=(
        "python3"
        "python3-pip"
        "python3-venv"
        "python3-tk"    # Tkinter GUI
        "ydotool"       # Wayland input automation
        "xclip"         # Clipboard operations
        "xdotool"       # X11 window management (optional)
        "curl"          # For potential future downloads
    )

    # Check which packages are missing
    local missing_packages=()
    for package in "${packages[@]}"; do
        if ! dpkg -l | grep -q "^ii.*$package "; then
            missing_packages+=("$package")
        fi
    done

    if [ ${#missing_packages[@]} -eq 0 ]; then
        success "All system dependencies already installed"
    else
        info "Installing missing packages: ${missing_packages[*]}"
        if ! sudo apt install -y "${missing_packages[@]}" &>> "$INSTALL_LOG"; then
            error_exit "Failed to install system dependencies"
        fi
        success "System dependencies installed"
    fi
}

# Install Python dependencies
install_python_deps() {
    info "Setting up Python dependencies..."

    # Check if we need to create a virtual environment
    local use_venv=false
    if [ "$1" = "--venv" ] || [ "$1" = "-v" ]; then
        use_venv=true
    fi

    if [ "$use_venv" = true ]; then
        info "Creating Python virtual environment..."
        if [ ! -d "$SCRIPT_DIR/venv" ]; then
            if ! python3 -m venv "$SCRIPT_DIR/venv" &>> "$INSTALL_LOG"; then
                error_exit "Failed to create virtual environment"
            fi
        fi

        # Activate virtual environment
        source "$SCRIPT_DIR/venv/bin/activate"
        success "Virtual environment created and activated"

        # Upgrade pip in venv
        pip install --upgrade pip &>> "$INSTALL_LOG"
    else
        # Install globally using system pip
        info "Installing Python packages system-wide..."
    fi

    # Install pynput (for X11 fallback)
    if [ "$use_venv" = true ]; then
        pip install pynput &>> "$INSTALL_LOG" || warning "Failed to install pynput in venv"
    else
        python3 -m pip install --user pynput &>> "$INSTALL_LOG" || warning "Failed to install pynput for user"
    fi

    success "Python dependencies configured"
}

# Check and configure ydotool
check_ydotool() {
    info "Checking ydotool configuration..."

    # Check if ydotool service is available
    if ! command -v ydotool &> /dev/null; then
        error_exit "ydotool not found after installation"
    fi

    # Check if ydotool daemon is running
    if ! pgrep -f ydotoold &> /dev/null; then
        warning "ydotool daemon not running, starting it..."

        # Try to start ydotool daemon
        if command -v systemctl &> /dev/null; then
            # Try systemd service first
            if sudo systemctl is-enabled ydotool &> /dev/null; then
                sudo systemctl start ydotool &>> "$INSTALL_LOG" || true
            fi
        fi

        # Fallback: start manually
        if ! pgrep -f ydotoold &> /dev/null; then
            info "Starting ydotool daemon manually..."
            sudo ydotoold &>> "$INSTALL_LOG" &
            sleep 2

            if ! pgrep -f ydotoold &> /dev/null; then
                error_exit "Failed to start ydotool daemon"
            fi
        fi

        success "ydotool daemon started"
    else
        success "ydotool daemon already running"
    fi

    # Check socket permissions
    local socket_path="/tmp/.ydotool_socket"
    if [ -S "$socket_path" ]; then
        # Check if we can write to the socket
        if [ -w "$socket_path" ]; then
            success "ydotool socket permissions OK"
        else
            warning "ydotool socket not writable by current user"
            info "Attempting to fix socket permissions..."

            # Try to add user to input group
            if ! groups "$USER" | grep -q input; then
                sudo usermod -a -G input "$USER" &>> "$INSTALL_LOG"
                warning "Added $USER to input group. You may need to log out and back in."
            fi

            # Try to change socket permissions
            sudo chmod 666 "$socket_path" &>> "$INSTALL_LOG" || true
        fi
    else
        warning "ydotool socket not found at $socket_path"
    fi
}

# Test functionality
test_functionality() {
    info "Testing basic functionality..."

    # Test Python import
    if ! python3 -c "import tkinter; import threading; import subprocess; import os; import time" &>> "$INSTALL_LOG"; then
        error_exit "Python import test failed"
    fi
    success "Python imports working"

    # Test ydotool
    if ! timeout 5 ydotool type --delay 100 "" &>> "$INSTALL_LOG"; then
        warning "ydotool test failed - you may need to check permissions or restart"
    else
        success "ydotool basic test passed"
    fi
}

# Create launcher script
create_launcher() {
    info "Creating launcher script..."

    local launcher_path="$SCRIPT_DIR/run_dunking_bird.sh"

    cat > "$launcher_path" << 'EOF'
#!/bin/bash

# Dunking Bird Launcher
# Handles environment setup and starts the application

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if virtual environment exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    echo "Activating virtual environment..."
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Ensure ydotool daemon is running
if ! pgrep -f ydotoold &> /dev/null; then
    echo "Starting ydotool daemon..."
    sudo ydotoold &
    sleep 2
fi

# Start the application
echo "Starting Dunking Bird..."
cd "$SCRIPT_DIR"
python3 dunking_bird.py "$@"
EOF

    chmod +x "$launcher_path"
    success "Launcher script created at $launcher_path"
}

# Main installation function
main() {
    log "${BLUE}===========================================${NC}"
    log "${BLUE}  Dunking Bird - Installation Script${NC}"
    log "${BLUE}===========================================${NC}"
    log ""

    # Clear previous log
    > "$INSTALL_LOG"
    log "Installation started at $(date)"
    log "Installation directory: $SCRIPT_DIR"

    check_root
    check_distro
    update_packages
    install_system_deps
    install_python_deps "$@"
    check_ydotool
    test_functionality
    create_launcher

    log ""
    log "${GREEN}===========================================${NC}"
    log "${GREEN}  Installation Complete!${NC}"
    log "${GREEN}===========================================${NC}"
    log ""
    info "To run Dunking Bird:"
    info "  Method 1: $SCRIPT_DIR/run_dunking_bird.sh"
    info "  Method 2: cd $SCRIPT_DIR && python3 dunking_bird.py"
    log ""

    if [ -d "$SCRIPT_DIR/venv" ]; then
        warning "Virtual environment was created. Remember to activate it if running manually:"
        info "  source $SCRIPT_DIR/venv/bin/activate"
    fi

    log ""
    info "If you encounter permission issues:"
    info "  1. You may need to log out and back in (if added to input group)"
    info "  2. Try running: sudo chmod 666 /tmp/.ydotool_socket"
    info "  3. Ensure ydotool daemon is running: sudo ydotoold &"
    log ""
    success "Installation complete! Check $INSTALL_LOG for details."
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --venv|-v)
            VENV_ARG="--venv"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --venv, -v    Install in Python virtual environment"
            echo "  --help, -h    Show this help message"
            echo ""
            echo "Quick install: curl -fsSL https://raw.githubusercontent.com/user/repo/main/install.sh | bash"
            echo "With venv:     curl -fsSL https://raw.githubusercontent.com/user/repo/main/install.sh | bash -s -- --venv"
            exit 0
            ;;
        *)
            error_exit "Unknown option: $1. Use --help for usage."
            ;;
    esac
done

# Run main installation
main $VENV_ARG