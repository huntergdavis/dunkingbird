# Dunking Bird

<img src="dunkingbird.png" alt="Dunking Bird" width="50%">

A robust terminal-first automation tool that sends text to windows at regular intervals. Perfect for keeping coding agents engaged with prompts like "continue" or "keep going". The default interface is now Dunking Bird TUI, with the original GUI still available as an optional launcher mode.

## 🖼️ Screenshots

<img src="tui_screenshot.png" alt="Dunking Bird TUI" width="80%">

*The default TUI interface with multiple dunkers, live status, window targeting, tests, custom text, and start/stop controls.*

<img src="screenshot.png" alt="Dunking Bird in Action" width="80%">

*The optional GUI capturing and focusing the "Untitled * — Kate" window with real-time window detection and precise targeting.*

## ✨ Features

- **🎯 Window Capture**: Capture and target specific windows instead of just the active window
- **⌨️ Terminal-first TUI**: Manage dunkers from your terminal workflow
- **⚙️ Optional GUI**: The original Tkinter interface is still available with `--gui`
- **⏱️ Configurable Interval**: Set custom time intervals (0.5-120 minutes)
- **📝 Custom Text**: Send any text you want to the targeted window
- **🔄 Automatic Enter**: Automatically presses Enter after sending text
- **⏰ Real-time Countdown**: Shows when the next text will be sent
- **🖥️ Background Operation**: Runs in the background while you work
- **🔧 Auto-Setup Verification**: Automatically checks and fixes common configuration issues
- **🌐 Wayland & X11 Compatible**: Works on modern Wayland and legacy X11 desktop environments

## 🚀 Installation

### Method 1: Automated Installer (Recommended)

**From this checkout:**
```bash
./easy_install.sh
```

**With Virtual Environment:**
```bash
./easy_install.sh --venv
```

The installer automatically:
- ✅ Installs all system dependencies
- ✅ Sets up Python environment (optional venv)
- ✅ Configures ydotool daemon and permissions
- ✅ Uses `kdotool` for KDE Wayland capture/focus when available
- ✅ Tests functionality and provides fixes
- ✅ Creates convenient launcher script

### Method 2: Manual Installation

1. **Clone or download the repository:**
   ```bash
   git clone https://github.com/user/repo.git
   cd dunkingbird
   ```

2. **Run the install script:**
   ```bash
   chmod +x easy_install.sh
   ./easy_install.sh --venv
   ```

3. **Or install manually:**
   ```bash
   sudo apt update
   sudo apt install -y ydotool xclip xdotool python3-venv cargo rustc libdbus-1-dev pkg-config
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   cargo install --git https://github.com/jinliu/kdotool --root "$HOME/.local"
   export YDOTOOL_SOCKET="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/.ydotool_socket"
   sudo ydotoold --socket-path="$YDOTOOL_SOCKET" --socket-own="$(id -u):$(id -g)" &
   ```

### Method 3: Quick Test (One-liner)
```bash
./run_dunking_bird.sh
```

### 🖥️ Desktop Environment Support

**Wayland (Modern):**
- ✅ GNOME Shell
- ✅ KDE Plasma
- ✅ Sway
- ✅ Hyprland
- ✅ Other wlroots compositors

**X11 (Legacy):**
- ✅ GNOME (X11 mode)
- ✅ KDE (X11 mode)
- ✅ i3 / i3-gaps
- ✅ XFCE
- ✅ Any X11 window manager

## 🎯 Usage

### Basic Usage

1. **Launch the TUI application**:
   ```bash
   ./run_dunking_bird.sh    # If using installer
   # OR
   python3 dunking_bird_tui.py   # Direct launch
   ```

2. **Configure your settings**:
   - Select a dunker with `j`/`k` or the arrow keys
   - Press `i` to set the interval in minutes (default: 10); `Enter` saves and `Esc` cancels
   - Press `e` to open the full-screen text editor; `Ctrl+G` saves and `Esc` cancels

3. **Target a specific window (NEW!)**:
   - Press `c` to capture a window
   - The currently active window will be captured and targeted
   - See captured window info displayed in the Window column
   - All future text will go to this specific window

4. **Test your setup**:
   - Press `t` to immediately send text with a 2-second countdown
   - Verify the text reaches your target window

5. **Start automation**:
   - Press `Space` or `s` to begin automatic sending
   - Real-time countdown shows time until next send
   - Press `Space` or `s` again to pause

6. **Manage dunkers**:
   - Press `a` to add another dunker
   - Press `d` to remove the selected dunker
   - Press `q` to quit

### Optional GUI

The original GUI is still available, but it is no longer required for the default workflow.

```bash
./run_dunking_bird.sh --gui
# OR
python3 dunking_bird.py
```

GUI mode requires Tkinter:

```bash
sudo apt install python3-tk
```

### 🎯 Window Targeting Modes

**Mode 1: Active Window (Default)**
- Text sent to whatever window is currently active
- Traditional behavior, good for simple use cases

**Mode 2: Captured Window (NEW!)**
- Click "Capture Window" to lock onto a specific window
- Text always sent to that window, even if it's not active
- Perfect for targeting specific terminals, coding agents, etc.

## 💡 Use Cases

- **🤖 Coding Agents**: Keep AI assistants engaged ("continue", "keep going", "proceed")
- **💻 Terminal Sessions**: Send commands to specific terminals automatically
- **📱 Chat Applications**: Send regular messages to specific chat windows
- **🎮 Gaming**: Send periodic inputs to game windows
- **🔧 Development**: Keep development servers or tools active

## 🚀 Example Workflows

### Workflow 1: Coding Agent Assistant
1. Start your AI coding assistant (Claude, ChatGPT, etc.)
2. Launch Dunking Bird
3. Click "Capture Window" while the AI chat is active
4. Set interval to 15 minutes, text to "continue with the implementation"
5. Click Start - now your AI stays engaged automatically!

### Workflow 2: Terminal Keep-Alive
1. Open your terminal or SSH session
2. Run Dunking Bird
3. Capture the terminal window
4. Set a short interval (1 minute) with a harmless command like "echo 'alive'"
5. Keep your session from timing out

### Workflow 3: Development Server
1. Start your development server in a terminal
2. Capture that terminal window
3. Send periodic commands to check status or restart services

## 🔧 Troubleshooting

### Automatic Fixes
Dunking Bird automatically detects and offers to fix common issues:
- **Setup Issues**: Missing dependencies, daemon not running
- **Permission Problems**: Socket permissions, user group membership
- **Configuration**: Auto-starts ydotool daemon, fixes permissions

### Manual Troubleshooting

**❌ "ydotool: No such device"**
```bash
export YDOTOOL_SOCKET="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/.ydotool_socket"
sudo ydotoold --socket-path="$YDOTOOL_SOCKET" --socket-own="$(id -u):$(id -g)" &
sleep 2
# Try running the app again
```

**❌ "Permission denied" on socket**
```bash
sudo chmod 600 "${YDOTOOL_SOCKET:-${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/.ydotool_socket}"
# OR add user to input group:
sudo usermod -a -G input $USER
# (logout/login required)
```

**❌ "ModuleNotFoundError: tkinter" in GUI mode**
```bash
sudo apt install python3-tk
```

The default TUI does not require Tkinter or any GUI Python dependency.

**❌ Window capture not working**
- **KDE Wayland**: install `kdotool` with `cargo install --git https://github.com/jinliu/kdotool --root "$HOME/.local"`
- **X11**: Install `sudo apt install xdotool`
- **Wayland/Sway**: Ensure `swaymsg` is available
- **GNOME or generic Wayland**: This app cannot reliably capture and refocus another window without a compositor-specific backend

**Important**: `ydotoold` socket permissions affect typing, not window capture. If capture fails on Wayland, the usual cause is a missing capture backend such as `kdotool`, not the background service.

**❌ Text not reaching target**
- Ensure target window can accept keyboard input
- Try "Test Send" button to verify functionality
- Check that captured window still exists
- Re-capture window if target application was restarted

**❌ Installation issues**
```bash
# Clean install using the automated script
./easy_install.sh --venv
```

### Getting Help
- Run `./easy_install.sh --venv` for automatic dependency checking
- Check installation log: `cat install.log`
- Verify ydotool: `YDOTOOL_SOCKET="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/.ydotool_socket" ydotool type "test"`

## 📋 System Requirements

### Minimum Requirements
- **OS**: Ubuntu 20.04+ / Debian 10+ / other apt-based distros
- **Python**: 3.6+ (usually pre-installed)
- **Memory**: 50MB RAM
- **Desktop**: Any X11 or Wayland environment

### Dependencies (Auto-installed)
- `ydotool` - Modern input automation (Wayland compatible)
- `kdotool` - KDE Wayland window discovery/focus
- `xclip` - Clipboard operations (fallback)
- `xdotool` - X11 window management (optional)

### Optional GUI Dependencies
- `python3-tk` - Tkinter GUI framework
- `pynput` - Python input library (X11 fallback)

## 🎉 Success Stories

*"Keeps my Claude coding sessions active for hours! Game changer for long development projects."*

*"Perfect for maintaining SSH connections and development servers. Set it and forget it."*

*"Works flawlessly on both my Wayland laptop and X11 desktop. Installation was super smooth."*

---

**Ready to keep your systems engaged? Install now with one command! 🚀**
