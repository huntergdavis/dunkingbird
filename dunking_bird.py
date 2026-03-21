#!/usr/bin/env python3
"""
Dunking Bird - Automated text sender for active windows
Sends text to the currently active window at regular intervals
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import subprocess
import os
import stat
from pynput import keyboard
from pynput.keyboard import Key, Listener


class DunkingBird:
    def __init__(self, root):
        try:
            self.root = root
            self.root.title("Dunking Bird")
            self.root.geometry("600x500")
            self.root.minsize(500, 400)  # Set minimum window size
            self.root.resizable(True, True)  # Make window resizable

            # State variables
            self.is_running = False
            self.timer_thread = None
            self.interval_seconds = 600  # Default 10 minutes

            # Window capture variables
            self.captured_window_id = None
            self.captured_window_name = None
            self.captured_window_class = None
            self.captured_compositor = None

            # Setup GUI with error handling
            try:
                self.setup_gui()
            except Exception as e:
                print(f"Error setting up GUI: {e}")
                messagebox.showerror("GUI Error", f"Failed to setup interface: {e}")
                return

            # Perform runtime checks after GUI is set up (with delay and error handling)
            self.root.after(500, self.safe_runtime_checks)

        except Exception as e:
            print(f"Critical error during initialization: {e}")
            try:
                messagebox.showerror("Initialization Error", f"Failed to initialize application: {e}")
            except:
                print("Could not show error dialog")

    def safe_runtime_checks(self):
        """Safely perform runtime checks with error handling"""
        try:
            self.perform_runtime_checks()
        except Exception as e:
            print(f"Error during runtime checks: {e}")
            self.status_var.set("⚠️ Setup check failed - app may still work")

    def setup_gui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(6, weight=1)

        # Title
        title_label = ttk.Label(main_frame, text="Dunking Bird", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))

        # Timer interval input with spinbox
        ttk.Label(main_frame, text="Interval (minutes):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.interval_var = tk.StringVar(value="10")
        interval_spinbox = ttk.Spinbox(main_frame, from_=0.5, to=120, increment=0.5,
                                     textvariable=self.interval_var, width=8, format="%.1f")
        interval_spinbox.grid(row=1, column=1, sticky=tk.W, pady=5)

        # Start/Stop button
        self.start_stop_btn = ttk.Button(main_frame, text="Start", command=self.toggle_running)
        self.start_stop_btn.grid(row=2, column=0, pady=10, padx=(0, 5), sticky=tk.W)

        # Test Send button
        self.test_btn = ttk.Button(main_frame, text="Test Send (2s delay)", command=self.test_send)
        self.test_btn.grid(row=2, column=1, pady=10, padx=(5, 0), sticky=tk.W)

        # Capture Window button
        self.capture_btn = ttk.Button(main_frame, text="Capture Window", command=self.capture_window)
        self.capture_btn.grid(row=3, column=0, columnspan=2, pady=5, sticky=tk.EW)

        # Captured window info display
        self.window_info_var = tk.StringVar(value="No window captured - will send to active window")
        window_info_label = ttk.Label(main_frame, textvariable=self.window_info_var,
                                    font=("Arial", 9), foreground="blue")
        window_info_label.grid(row=4, column=0, columnspan=2, pady=5, sticky=tk.W)

        # Text area label
        ttk.Label(main_frame, text="Text to send:").grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.N), pady=(10, 5))

        # Text area
        self.text_area = scrolledtext.ScrolledText(main_frame, width=40, height=8, wrap=tk.WORD)
        self.text_area.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        self.text_area.insert(tk.END, "continue")

        # Status label
        self.status_var = tk.StringVar(value="Stopped")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, font=("Arial", 10))
        status_label.grid(row=7, column=0, columnspan=2, pady=5)

        # Removed fix setup button - use separate setup.py script instead

        # Next send countdown
        self.countdown_var = tk.StringVar(value="")
        countdown_label = ttk.Label(main_frame, textvariable=self.countdown_var, font=("Arial", 9))
        countdown_label.grid(row=8, column=0, columnspan=2, pady=5)

    def toggle_running(self):
        if self.is_running:
            self.stop()
        else:
            self.start()

    def start(self):
        try:
            # Validate interval
            interval_minutes = float(self.interval_var.get())
            if interval_minutes <= 0:
                raise ValueError("Interval must be positive")

            self.interval_seconds = interval_minutes * 60
            self.is_running = True
            self.start_stop_btn.config(text="Stop")
            self.status_var.set(f"Running - sending every {interval_minutes} minutes")

            # Start the timer thread
            self.timer_thread = threading.Thread(target=self.timer_loop, daemon=True)
            self.timer_thread.start()

        except ValueError:
            self.status_var.set("Error: Invalid interval")

    def stop(self):
        self.is_running = False
        self.start_stop_btn.config(text="Start")
        self.status_var.set("Stopped")
        self.countdown_var.set("")

    def test_send(self):
        """Test send text immediately with countdown"""
        # Disable the test button temporarily
        self.test_btn.config(state='disabled')

        # Start countdown in separate thread
        test_thread = threading.Thread(target=self.test_send_countdown, daemon=True)
        test_thread.start()

    def test_send_countdown(self):
        """Run countdown then send text using ydotool"""
        try:
            # Show countdown
            for i in range(2, 0, -1):
                self.root.after(0, lambda i=i: self.status_var.set(f"Test sending in {i}..."))
                time.sleep(1)

            # Focus captured window if one exists
            if not self.focus_captured_window():
                self.root.after(0, lambda: self.status_var.set("Failed to focus target window"))
                return

            self.root.after(0, lambda: self.status_var.set("Sending test text now..."))

            # Send the text using ydotool
            self.send_text_wayland()

        finally:
            # Re-enable the test button
            self.root.after(0, lambda: self.test_btn.config(state='normal'))

    def get_active_window(self):
        """Get the currently active window ID using xdotool"""
        try:
            result = subprocess.run(['xdotool', 'getactivewindow'],
                                  capture_output=True, text=True, check=True)
            window_id = result.stdout.strip()

            # Get window name for debugging
            name_result = subprocess.run(['xdotool', 'getwindowname', window_id],
                                       capture_output=True, text=True, check=True)
            window_name = name_result.stdout.strip()

            print(f"Active window: {window_name} (ID: {window_id})")
            return window_id

        except subprocess.CalledProcessError as e:
            print(f"Error getting active window: {e}")
            return None

    def select_window_interactive(self):
        """Let user click on a window to select it using xdotool"""
        try:
            print("Waiting for user to click on target window...")

            # Use xdotool selectwindow to let user click on a window
            # This will change the mouse cursor to crosshairs and wait for a click
            result = subprocess.run(['xdotool', 'selectwindow'],
                                  capture_output=True, text=True, check=True, timeout=30)
            window_id = result.stdout.strip()

            if window_id:
                # Get window name for confirmation
                try:
                    name_result = subprocess.run(['xdotool', 'getwindowname', window_id],
                                               capture_output=True, text=True, check=True)
                    window_name = name_result.stdout.strip()
                    print(f"User selected window: {window_name} (ID: {window_id})")
                except subprocess.CalledProcessError:
                    print(f"User selected window ID: {window_id}")

                return window_id
            else:
                print("No window selected")
                return None

        except subprocess.TimeoutExpired:
            print("Window selection timed out (30 seconds)")
            return None
        except subprocess.CalledProcessError as e:
            print(f"Error selecting window: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error during window selection: {e}")
            return None

    def get_wayland_window_info(self):
        """Get active window info on Wayland using various compositor tools"""
        import json

        # Helper to safely check if command exists
        def command_exists(cmd):
            try:
                subprocess.run(['which', cmd], capture_output=True, check=True)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                return False

        # Try sway first (most complete support)
        if command_exists('swaymsg'):
            try:
                result = subprocess.run(['swaymsg', '-t', 'get_tree'],
                                      capture_output=True, text=True, check=True)
                tree = json.loads(result.stdout)

                # Find focused window recursively
                def find_focused(node):
                    if node.get('focused', False):
                        return node
                    for child in node.get('nodes', []) + node.get('floating_nodes', []):
                        focused = find_focused(child)
                        if focused:
                            return focused
                    return None

                focused = find_focused(tree)
                if focused:
                    return {
                        'id': str(focused.get('id', 'unknown')),
                        'name': focused.get('name', 'Unknown Window'),
                        'class': focused.get('app_id', 'unknown'),
                        'compositor': 'sway'
                    }
            except (subprocess.CalledProcessError, json.JSONDecodeError, ImportError):
                pass

        # Try Hyprland
        if command_exists('hyprctl'):
            try:
                result = subprocess.run(['hyprctl', 'activewindow', '-j'],
                                      capture_output=True, text=True, check=True)
                window = json.loads(result.stdout)
                if window and 'address' in window:
                    return {
                        'id': window.get('address', 'unknown'),
                        'name': window.get('title', 'Unknown Window'),
                        'class': window.get('class', 'unknown'),
                        'compositor': 'hyprland'
                    }
            except (subprocess.CalledProcessError, json.JSONDecodeError, ImportError):
                pass

        # Try GNOME Shell / Mutter (limited support)
        if command_exists('gdbus'):
            try:
                result = subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.gnome.Shell',
                                       '--object-path', '/org/gnome/Shell', '--method',
                                       'org.gnome.Shell.Eval', 'global.display.focus_window.get_title()'],
                                      capture_output=True, text=True, check=True)
                # Parse gdbus response - it's in format: (true, "'Window Title'")
                if result.stdout and "'" in result.stdout:
                    title_start = result.stdout.find("'") + 1
                    title_end = result.stdout.rfind("'")
                    if title_start > 0 and title_end > title_start:
                        window_title = result.stdout[title_start:title_end]
                        return {
                            'id': 'gnome_active',
                            'name': window_title,
                            'class': 'unknown',
                            'compositor': 'gnome'
                        }
            except (subprocess.CalledProcessError, json.JSONDecodeError, ImportError):
                pass

        # Try KDE/KWin - use newer queryWindowInfo method
        qdbus_cmd = None
        for cmd in ['qdbus6', 'qdbus-qt5', 'qdbus']:
            if command_exists(cmd):
                qdbus_cmd = cmd
                break

        if qdbus_cmd:
            try:
                # Use queryWindowInfo which gives active window info
                result = subprocess.run([qdbus_cmd, 'org.kde.KWin', '/KWin',
                                       'org.kde.KWin.queryWindowInfo'],
                                      capture_output=True, text=True,
                                      timeout=3, check=True)

                # Parse the result - it's usually in a key=value format
                window_info = result.stdout.strip()
                if window_info and 'caption' in window_info:
                    # Extract window title from the output
                    title = "KDE Window"
                    for line in window_info.split('\n'):
                        if 'caption' in line and '=' in line:
                            title = line.split('=', 1)[1].strip().strip('"')
                            break

                    return {
                        'id': 'kde_active_window',
                        'name': title if title else "KDE Window",
                        'class': 'unknown',
                        'compositor': 'kde'
                    }

            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                # If queryWindowInfo fails, try simpler approach
                try:
                    # Just return basic KDE info
                    return {
                        'id': 'kde_fallback',
                        'name': "Active KDE Window",
                        'class': 'unknown',
                        'compositor': 'kde'
                    }
                except:
                    pass

        # Fallback: return basic info indicating no specific compositor support
        return {
            'id': 'wayland_fallback',
            'name': 'Active Window (Generic Wayland)',
            'class': 'unknown',
            'compositor': 'wayland_generic'
        }

    def capture_window(self):
        """Capture the currently active window for targeted text sending"""
        try:
            self.capture_btn.config(state='disabled')

            # Check session type to provide appropriate instructions
            if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
                self.window_info_var.set("📋 Capturing active window info (Wayland - sends to active window)")
            else:
                self.window_info_var.set("🎯 Click on the window you want to capture (30s timeout)")

            # Small delay to let user see the message
            self.root.after(1000, self._do_capture_window)

        except Exception as e:
            print(f"Error starting window capture: {e}")
            self.window_info_var.set("Error capturing window")
            self.capture_btn.config(state='normal')

    def _do_capture_window(self):
        """Perform the actual window capture"""
        try:
            # Detect if we're on X11 or Wayland
            if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
                window_info = self.get_wayland_window_info()
                if window_info:
                    self.captured_window_id = window_info['id']
                    self.captured_window_name = window_info['name']
                    self.captured_window_class = window_info['class']
                    self.captured_compositor = window_info.get('compositor', 'unknown')
                    self.window_info_var.set(f"📌 Captured: {self.captured_window_name} ({self.captured_compositor})")
                else:
                    # Fallback for Wayland - get current window info generically
                    self.captured_window_id = "wayland_active"
                    self.captured_window_name = "Active Window (Wayland)"
                    self.captured_window_class = "unknown"
                    self.captured_compositor = "unknown"
                    self.window_info_var.set("📌 Captured: Active Window (compositor detection failed)")
            else:
                # X11 - use interactive window selection
                window_id = self.select_window_interactive()
                if window_id:
                    # Get additional window info
                    try:
                        name_result = subprocess.run(['xdotool', 'getwindowname', window_id],
                                                   capture_output=True, text=True, check=True)
                        class_result = subprocess.run(['xdotool', 'getwindowclassname', window_id],
                                                    capture_output=True, text=True, check=True)

                        self.captured_window_id = window_id
                        self.captured_window_name = name_result.stdout.strip()
                        self.captured_window_class = class_result.stdout.strip()
                        self.captured_compositor = "x11"

                        self.window_info_var.set(f"📌 Captured: {self.captured_window_name} ({self.captured_window_class})")
                    except subprocess.CalledProcessError:
                        self.captured_window_id = window_id
                        self.captured_window_name = "Unknown Window"
                        self.captured_window_class = "unknown"
                        self.captured_compositor = "x11"
                        self.window_info_var.set(f"📌 Captured: Window ID {window_id}")
                else:
                    self.window_info_var.set("❌ Window selection cancelled or timed out")

        except Exception as e:
            print(f"Error capturing window: {e}")
            self.window_info_var.set("❌ Error capturing window")

        finally:
            self.capture_btn.config(state='normal')

    def focus_captured_window(self):
        """Focus the captured window before sending text"""
        if not self.captured_window_id:
            return True  # No captured window, continue with active window

        try:
            # Detect if we're on X11 or Wayland
            if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
                return self._focus_wayland_window()
            else:
                return self._focus_x11_window()
        except Exception as e:
            print(f"Error focusing captured window: {e}")
            return True  # Continue anyway since ydotool works with active window

    def _focus_x11_window(self):
        """Focus window on X11 using xdotool"""
        try:
            subprocess.run(['xdotool', 'windowactivate', self.captured_window_id], check=True)
            time.sleep(0.1)  # Brief delay for window to receive focus
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error focusing X11 window {self.captured_window_id}: {e}")
            return False

    def _focus_wayland_window(self):
        """Focus window on Wayland using compositor-specific methods and fallbacks"""
        try:
            if self.captured_window_id in ["wayland_active", "gnome_active"]:
                return True  # Already using active window approach

            compositor = getattr(self, 'captured_compositor', 'unknown')
            print(f"Attempting to focus {self.captured_window_name} on {compositor}")

            # Method 1: Compositor-specific focus commands
            focus_success = self._try_compositor_focus(compositor)
            if focus_success:
                print(f"Successfully focused window using {compositor} method")
                return True

            # Method 2: KWin scripting approach (for KDE)
            if compositor == 'kde' or 'kde' in compositor:
                kwin_success = self._try_kwin_scripting_focus()
                if kwin_success:
                    print("Successfully focused window using KWin scripting")
                    return True

            # Method 3: Input simulation fallback (Alt+Tab cycling)
            if self.captured_window_name and self.captured_window_name != "Unknown Window":
                input_success = self._try_input_focus()
                if input_success:
                    print("Successfully focused window using input simulation")
                    return True

            print(f"Could not focus Wayland window {self.captured_window_name}")
            return False

        except Exception as e:
            print(f"Error in Wayland window focus: {e}")
            return False

    def _try_compositor_focus(self, compositor):
        """Try compositor-specific focus methods"""
        try:
            # Sway
            if compositor == 'sway':
                subprocess.run(['swaymsg', f'[con_id="{self.captured_window_id}"] focus'],
                             check=True, timeout=3)
                return True

            # Hyprland
            elif compositor == 'hyprland':
                subprocess.run(['hyprctl', 'dispatch', 'focuswindow', f'address:{self.captured_window_id}'],
                             check=True, timeout=3)
                return True

            # KDE (try direct qdbus if we have a proper window ID)
            elif compositor == 'kde' and self.captured_window_id.isdigit():
                for qdbus_cmd in ['qdbus6', 'qdbus-qt5', 'qdbus']:
                    try:
                        subprocess.run([qdbus_cmd, 'org.kde.KWin', f'/KWin/Window_{self.captured_window_id}',
                                      'org.kde.KWin.Window.activate'], check=True, timeout=3)
                        return True
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return False

    def _try_kwin_scripting_focus(self):
        """Use KWin scripting to focus window by title"""
        try:
            if not self.captured_window_name or self.captured_window_name == "Unknown Window":
                return False

            # Create a temporary KWin script to focus window by title
            script_content = f"""
// Focus window by title
var clients = workspace.clientList();
for (var i = 0; i < clients.length; i++) {{
    var client = clients[i];
    if (client.caption.includes("{self.captured_window_name}")) {{
        workspace.activateClient(client);
        break;
    }}
}}
"""

            script_path = "/tmp/focus_by_title.js"
            with open(script_path, 'w') as f:
                f.write(script_content)

            # Load and execute the script
            for qdbus_cmd in ['qdbus6', 'qdbus-qt5', 'qdbus']:
                try:
                    result = subprocess.run([qdbus_cmd, 'org.kde.KWin', '/Scripting',
                                          'org.kde.kwin.Scripting.loadScript', script_path],
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        time.sleep(0.2)  # Give KWin time to execute
                        # Cleanup
                        os.remove(script_path)
                        return True
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                    continue

        except Exception as e:
            print(f"KWin scripting focus error: {e}")

        return False

    def _try_input_focus(self):
        """Use input simulation to focus window by title"""
        try:
            if not self.captured_window_name or self.captured_window_name == "Unknown Window":
                return False

            print(f"Trying to focus '{self.captured_window_name}' using input simulation")

            # Use Alt+Tab to cycle through windows and find our target
            # This is a simplified approach - in practice, you'd need more sophisticated matching

            # First, try Super+W (KDE's Present Windows effect) if available
            try:
                subprocess.run(['ydotool', 'key', 'Super+W'], timeout=2, check=False)
                time.sleep(0.5)
                # Type the window name to search
                subprocess.run(['ydotool', 'type', self.captured_window_name[:10]], timeout=3, check=False)
                time.sleep(0.3)
                # Press Enter to select
                subprocess.run(['ydotool', 'key', 'Return'], timeout=2, check=False)
                time.sleep(0.3)
                return True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass

            # Fallback: Just ensure current window has focus by clicking on it
            # This is crude but often works
            try:
                subprocess.run(['ydotool', 'key', 'alt+Tab'], timeout=2, check=False)
                time.sleep(0.1)
                subprocess.run(['ydotool', 'key', 'alt+Tab'], timeout=2, check=False)
                time.sleep(0.1)
                return True
            except:
                pass

        except Exception as e:
            print(f"Input focus simulation error: {e}")

        return False

    def perform_runtime_checks(self):
        """Perform minimal runtime checks"""
        try:
            # Just check if ydotool is available - if not, show helpful message
            if not self._check_ydotool_available():
                self.status_var.set("⚠️ ydotool not found - run ./setup.py to fix")
            else:
                self.status_var.set("✓ Ready")
        except Exception as e:
            # Don't crash on runtime checks
            self.status_var.set("Ready")
            print(f"Runtime check error: {e}")

    # Removed setup dialog functionality - use setup.py script instead

    def _check_ydotool_available(self):
        """Check if ydotool command is available"""
        try:
            # Use 'help' command - ydotool outputs to stderr but that's normal
            result = subprocess.run(['ydotool', 'help'],
                                  capture_output=True, text=True, timeout=5)
            # ydotool help may return non-zero but still show help text in stderr
            return 'Usage:' in result.stderr or 'Usage:' in result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        except subprocess.CalledProcessError:
            # ydotool may return error code but still be functional
            return True

    # Removed all setup/installation functions - use setup.py script instead

    def send_text_to_window(self, window_id):
        """Send text using ydotool for Wayland compatibility"""
        try:
            text_to_send = self.text_area.get(1.0, tk.END).strip()
            if not text_to_send:
                return

            print(f"Sending text using ydotool: {text_to_send}")

            # Use ydotool which works on Wayland
            # Small delay before typing
            time.sleep(0.5)

            # Type the text with newline
            text_with_enter = text_to_send + '\n'
            subprocess.run(['ydotool', 'type', '--delay', '50', text_with_enter], check=True)

            print(f"Successfully sent text using ydotool")
            current_time = time.strftime("%H:%M:%S")
            self.root.after(0, lambda: self.status_var.set(f"Sent at {current_time}"))

        except subprocess.CalledProcessError as e:
            print(f"Error sending text with ydotool: {e}")
            self.root.after(0, lambda: self.status_var.set(f"Failed to send text"))
        except Exception as e:
            print(f"Unexpected error: {e}")
            self.root.after(0, lambda: self.status_var.set(f"Error: {e}"))

    def send_text_wayland(self):
        """Send text using ydotool - Wayland compatible with robust error handling"""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                text_to_send = self.text_area.get(1.0, tk.END).strip()
                if not text_to_send:
                    self.root.after(0, lambda: self.status_var.set("No text to send"))
                    return

                # Validate text length and content
                if len(text_to_send) > 1000:
                    self.root.after(0, lambda: self.status_var.set("Text too long (max 1000 chars)"))
                    return

                # Check ydotool availability before sending
                if not self._check_ydotool_available():
                    self.root.after(0, lambda: self.status_var.set("ydotool not available - run ./setup.py"))
                    return

                # Focus captured window if one exists (with fallback)
                focus_result = self.focus_captured_window()
                if not focus_result and self.captured_window_id and os.environ.get('XDG_SESSION_TYPE') != 'wayland':
                    # Only clear window on X11 if focus truly failed
                    print(f"Captured window {self.captured_window_name} no longer valid, clearing...")
                    self.captured_window_id = None
                    self.captured_window_name = None
                    self.captured_window_class = None
                    self.captured_compositor = None
                    self.root.after(0, lambda: self.window_info_var.set("Window lost - using active window"))

                print(f"Sending text via ydotool: {text_to_send}")

                # Additional delay for window focus
                time.sleep(0.3)

                # Escape special characters that might cause issues
                safe_text = text_to_send.replace('\\', '\\\\').replace('"', '\\"')
                text_with_enter = safe_text + '\n'

                # Use ydotool with timeout for robustness
                result = subprocess.run(['timeout', '10', 'ydotool', 'type', '--delay', '50', text_with_enter],
                                      capture_output=True, text=True, check=True)

                print(f"Successfully sent text via ydotool: {text_to_send}")
                current_time = time.strftime("%H:%M:%S")

                # Update status with window info if captured
                if self.captured_window_id:
                    status_text = f"✅ Sent to {self.captured_window_name} at {current_time}"
                else:
                    status_text = f"✅ Running - Last sent at {current_time}"

                self.root.after(0, lambda: self.status_var.set(status_text))
                return  # Success, exit retry loop

            except subprocess.TimeoutExpired:
                retry_count += 1
                print(f"ydotool timeout, retry {retry_count}/{max_retries}")
                if retry_count < max_retries:
                    time.sleep(1)
                    continue
                else:
                    self.root.after(0, lambda: self.status_var.set("❌ Timeout sending text"))

            except subprocess.CalledProcessError as e:
                retry_count += 1
                print(f"Error sending text via ydotool: {e}, retry {retry_count}/{max_retries}")
                if retry_count < max_retries:
                    # Try to restart daemon
                    subprocess.run(['sudo', 'pkill', 'ydotoold'], capture_output=True)
                    subprocess.run(['sudo', 'ydotoold'], capture_output=True)
                    time.sleep(2)
                    continue
                else:
                    self.root.after(0, lambda: self.status_var.set("❌ Error sending text - check setup"))

            except Exception as e:
                retry_count += 1
                print(f"Unexpected error with ydotool: {e}, retry {retry_count}/{max_retries}")
                if retry_count < max_retries:
                    time.sleep(1)
                    continue
                else:
                    self.root.after(0, lambda: self.status_var.set(f"❌ Unexpected error: {str(e)[:50]}"))

    def timer_loop(self):
        """Main timer loop that runs in a separate thread"""
        while self.is_running:
            # Wait for the interval, but check every second for stop signal
            for i in range(int(self.interval_seconds)):
                if not self.is_running:
                    return

                # Update countdown display
                remaining = self.interval_seconds - i
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                self.countdown_var.set(f"Next send in: {minutes:02d}:{seconds:02d}")

                time.sleep(1)

            # Send the text if still running
            if self.is_running:
                self.send_text_wayland()

    def send_text_clipboard(self, text):
        """Fallback method using clipboard and Ctrl+V"""
        try:
            # Copy text to clipboard using xclip
            process = subprocess.run(['xclip', '-selection', 'clipboard'],
                                   input=text, text=True, check=True)

            # Create keyboard controller
            controller = keyboard.Controller()

            # Wait a moment
            time.sleep(0.2)

            # Send Ctrl+V
            controller.press(Key.ctrl)
            controller.press('v')
            controller.release('v')
            controller.release(Key.ctrl)

            return True
        except Exception as e:
            print(f"Clipboard method failed: {e}")
            return False

    def send_text(self):
        """Send the text from the text area to the active window"""
        try:
            text_to_send = self.text_area.get(1.0, tk.END).strip()
            if text_to_send:
                # Create a keyboard controller
                controller = keyboard.Controller()

                # Brief delay to ensure window focus
                time.sleep(0.2)

                print(f"Attempting to send text: {text_to_send}")

                # Try Method 1: Character by character
                success = True
                try:
                    for char in text_to_send:
                        try:
                            controller.press(char)
                            controller.release(char)
                            time.sleep(0.01)  # Small delay between characters
                        except Exception as char_error:
                            print(f"Error sending character '{char}': {char_error}")
                            success = False
                            break
                except Exception:
                    success = False

                # Try Method 2: Clipboard fallback if character method failed
                if not success:
                    print("Trying clipboard method...")
                    success = self.send_text_clipboard(text_to_send)

                # Try Method 3: Direct typing as last resort
                if not success:
                    print("Trying direct typing method...")
                    try:
                        controller.type(text_to_send)
                        success = True
                    except Exception as e:
                        print(f"Direct typing failed: {e}")

                if success:
                    # Small delay before Enter
                    time.sleep(0.1)

                    # Press Enter
                    controller.press(Key.enter)
                    controller.release(Key.enter)

                    print(f"Successfully sent text: {text_to_send}")
                    # Update status to show last sent time
                    current_time = time.strftime("%H:%M:%S")
                    self.root.after(0, lambda: self.status_var.set(f"Running - Last sent at {current_time}"))
                else:
                    print("All text sending methods failed!")
                    self.root.after(0, lambda: self.status_var.set(f"Failed to send text"))

        except Exception as e:
            print(f"Error sending text: {e}")
            self.root.after(0, lambda: self.status_var.set(f"Error sending text: {e}"))


def main():
    root = tk.Tk()
    app = DunkingBird(root)
    root.mainloop()


if __name__ == "__main__":
    main()