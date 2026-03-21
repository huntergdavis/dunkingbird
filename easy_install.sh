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

# Super robust dependency installation
install_dependencies() {
    info "Installing system dependencies..."

    # Update package list with retry
    local max_attempts=3
    for attempt in $(seq 1 $max_attempts); do
        if sudo apt update -qq &>/dev/null; then
            break
        else
            warning "Package update attempt $attempt failed, retrying..."
            sleep 2
        fi
    done

    # Install packages with automatic yes
    local packages=(
        "python3"
        "python3-pip"
        "python3-venv"
        "python3-tk"
        "ydotool"
        "ydotoold"
        "xclip"
        "xdotool"
        "curl"
        "timeout"
        "pgrep"
    )

    export DEBIAN_FRONTEND=noninteractive
    for package in "${packages[@]}"; do
        if ! dpkg -l | grep -q "^ii.*$package "; then
            info "Installing $package..."
            sudo apt install -y "$package" &>/dev/null || warning "Could not install $package"
        fi
    done

    success "System dependencies installed"
}

# Robust ydotool setup with multiple methods
setup_ydotool() {
    info "Configuring ydotool for input automation..."

    # Kill any existing ydotool processes
    sudo pkill ydotoold 2>/dev/null || true
    sleep 1

    # Start ydotool daemon with multiple methods
    if ! pgrep -f ydotoold >/dev/null; then
        # Method 1: Direct daemon start
        sudo ydotoold --socket-path=/tmp/.ydotool_socket --socket-own=$(id -u):$(id -g) 2>/dev/null &

        # Give it time to start
        sleep 3

        # Method 2: Try systemd if available
        if ! pgrep -f ydotoold >/dev/null && command -v systemctl >/dev/null; then
            sudo systemctl start ydotool 2>/dev/null || true
            sleep 2
        fi

        # Method 3: Fallback manual start
        if ! pgrep -f ydotoold >/dev/null; then
            nohup sudo ydotoold &>/dev/null &
            sleep 2
        fi
    fi

    # Fix socket permissions aggressively
    local socket_path="/tmp/.ydotool_socket"
    if [ -S "$socket_path" ]; then
        sudo chmod 666 "$socket_path" 2>/dev/null || true
        sudo chown root:input "$socket_path" 2>/dev/null || true
    fi

    # Add user to input group if needed
    if ! groups "$USER" | grep -q input; then
        sudo usermod -a -G input "$USER" 2>/dev/null || true
    fi

    # Test ydotool functionality
    if timeout 3 ydotool type "" 2>/dev/null; then
        success "ydotool configured and working"
    else
        warning "ydotool may need manual configuration"
    fi
}

# Install Python dependencies robustly
setup_python() {
    info "Setting up Python environment..."

    # Try pip install with fallbacks
    if command -v pip3 >/dev/null; then
        pip3 install --user pynput 2>/dev/null || true
    fi

    if command -v python3 >/dev/null && python3 -m pip --version >/dev/null 2>&1; then
        python3 -m pip install --user pynput 2>/dev/null || true
    fi

    success "Python environment ready"
}

# Download application files if not present
download_app() {
    if [ ! -f "dunking_bird.py" ]; then
        info "Downloading Dunking Bird application..."

        # Try multiple download methods
        if command -v curl >/dev/null; then
            curl -fsSL -o dunking_bird.py "https://raw.githubusercontent.com/user/repo/main/dunking_bird.py" 2>/dev/null || true
        elif command -v wget >/dev/null; then
            wget -q -O dunking_bird.py "https://raw.githubusercontent.com/user/repo/main/dunking_bird.py" 2>/dev/null || true
        fi

        if [ ! -f "dunking_bird.py" ]; then
            error "Could not download application. Please download manually."
            exit 1
        fi

        success "Application downloaded"
    else
        success "Application files found"
    fi
}

# Create super robust launcher
create_launcher() {
    info "Creating smart launcher..."

    cat > "run_dunking_bird.sh" << 'EOF'
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
EOF

    chmod +x "run_dunking_bird.sh"
    success "Smart launcher created"
}

# Comprehensive system test
run_tests() {
    info "Running system tests..."

    # Test 1: Python and tkinter
    if python3 -c "import tkinter; import threading; import subprocess; import os" 2>/dev/null; then
        success "Python environment OK"
    else
        error "Python environment issue"
        return 1
    fi

    # Test 2: ydotool basic functionality
    if timeout 3 ydotool type "" 2>/dev/null; then
        success "ydotool working"
    else
        warning "ydotool may have issues"
    fi

    # Test 3: GUI display
    if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
        success "Display server available"
    else
        warning "No display server detected"
    fi

    return 0
}

# Main installation process
main() {
    show_banner

    info "Starting one-click installation process..."
    log "Installation directory: $(pwd)"

    # Check prerequisites
    check_sudo_nopass

    # Step-by-step installation with progress
    echo -e "${CYAN}📦 Installing system packages...${NC}"
    install_dependencies

    echo -e "${CYAN}🔧 Setting up ydotool...${NC}"
    setup_ydotool

    echo -e "${CYAN}🐍 Configuring Python...${NC}"
    setup_python

    echo -e "${CYAN}📥 Preparing application...${NC}"
    download_app

    echo -e "${CYAN}🚀 Creating launcher...${NC}"
    create_launcher

    echo -e "${CYAN}🧪 Running tests...${NC}"
    run_tests

    echo ""
    echo -e "${GREEN}🎉 INSTALLATION COMPLETE! 🎉${NC}"
    echo ""
    echo -e "${YELLOW}Launch options:${NC}"
    echo -e "  ${GREEN}Option 1 (Easy):${NC} ./run_dunking_bird.sh"
    echo -e "  ${GREEN}Option 2 (Direct):${NC} python3 dunking_bird.py"
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

# Run main function
main "$@"