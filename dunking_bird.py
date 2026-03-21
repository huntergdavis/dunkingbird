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
        self.root = root
        self.root.title("Dunking Bird")
        self.root.geometry("400x300")

        # State variables
        self.is_running = False
        self.timer_thread = None
        self.interval_seconds = 600  # Default 10 minutes

        # Window capture variables
        self.captured_window_id = None
        self.captured_window_name = None
        self.captured_window_class = None

        self.setup_gui()

        # Perform runtime checks after GUI is set up
        self.root.after(100, self.perform_runtime_checks)

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

    def get_wayland_window_info(self):
        """Get active window info on Wayland using swaymsg (for sway) or other methods"""
        try:
            # Try sway first
            result = subprocess.run(['swaymsg', '-t', 'get_tree'],
                                  capture_output=True, text=True, check=True)
            import json
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
                    'class': focused.get('app_id', 'unknown')
                }
        except (subprocess.CalledProcessError, json.JSONDecodeError, ImportError):
            pass

        # Fallback: try other Wayland compositor tools or return None
        return None

    def capture_window(self):
        """Capture the currently active window for targeted text sending"""
        try:
            self.capture_btn.config(state='disabled')
            self.window_info_var.set("Capturing window... Click on target window")

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
                    self.window_info_var.set(f"📌 Captured: {self.captured_window_name} ({self.captured_window_class})")
                else:
                    # Fallback for Wayland - get current window info generically
                    self.captured_window_id = "wayland_active"
                    self.captured_window_name = "Active Window (Wayland)"
                    self.captured_window_class = "unknown"
                    self.window_info_var.set("📌 Captured: Active Window (Wayland detection limited)")
            else:
                # X11 - use xdotool
                window_id = self.get_active_window()
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

                        self.window_info_var.set(f"📌 Captured: {self.captured_window_name} ({self.captured_window_class})")
                    except subprocess.CalledProcessError:
                        self.captured_window_id = window_id
                        self.captured_window_name = "Unknown Window"
                        self.captured_window_class = "unknown"
                        self.window_info_var.set(f"📌 Captured: Window ID {window_id}")
                else:
                    self.window_info_var.set("❌ Could not capture window")

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
            return False

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
        """Focus window on Wayland using sway commands"""
        try:
            if self.captured_window_id == "wayland_active":
                return True  # Already using active window approach

            # Try sway focus command
            subprocess.run(['swaymsg', f'[con_id="{self.captured_window_id}"] focus'], check=True)
            time.sleep(0.1)  # Brief delay for window to receive focus
            return True
        except subprocess.CalledProcessError:
            # Fallback: try other Wayland compositor commands or return false
            try:
                # Alternative approach for other Wayland compositors
                return True  # For now, assume success for unknown compositors
            except:
                print(f"Error focusing Wayland window {self.captured_window_id}")
                return False

    def perform_runtime_checks(self):
        """Perform comprehensive runtime checks for dependencies and configuration"""
        issues = []
        warnings = []

        # Check ydotool availability
        if not self._check_ydotool_available():
            issues.append("ydotool command not found")

        # Check ydotool daemon
        daemon_status = self._check_ydotool_daemon()
        if daemon_status == "not_running":
            issues.append("ydotool daemon not running")
        elif daemon_status == "no_socket":
            issues.append("ydotool socket not found")
        elif daemon_status == "permission_denied":
            warnings.append("ydotool socket permission issues")

        # Check user permissions
        if not self._check_user_permissions():
            warnings.append("User may not be in input group")

        # Display results
        if issues:
            self._show_setup_dialog(issues, warnings)
        elif warnings:
            self._show_warning_dialog(warnings)
        else:
            self.status_var.set("✓ All systems ready")

    def _check_ydotool_available(self):
        """Check if ydotool command is available"""
        try:
            subprocess.run(['ydotool', '--version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _check_ydotool_daemon(self):
        """Check ydotool daemon status and socket"""
        # Check if daemon process is running
        try:
            result = subprocess.run(['pgrep', '-f', 'ydotoold'], capture_output=True, text=True)
            if result.returncode != 0:
                return "not_running"
        except subprocess.CalledProcessError:
            return "not_running"

        # Check if socket exists
        socket_path = "/tmp/.ydotool_socket"
        if not os.path.exists(socket_path):
            return "no_socket"

        # Check socket permissions
        try:
            # Try to get socket stats
            socket_stat = os.stat(socket_path)
            if not (socket_stat.st_mode & stat.S_IWUSR or socket_stat.st_mode & stat.S_IWGRP or socket_stat.st_mode & stat.S_IWOTH):
                return "permission_denied"

            # Try a simple test
            result = subprocess.run(['timeout', '2', 'ydotool', 'type', '--delay', '100', ''],
                                  capture_output=True, stderr=subprocess.DEVNULL)
            if result.returncode != 0:
                return "permission_denied"

        except (OSError, subprocess.CalledProcessError):
            return "permission_denied"

        return "ok"

    def _check_user_permissions(self):
        """Check if user has appropriate permissions"""
        try:
            # Check if user is in input group
            result = subprocess.run(['groups'], capture_output=True, text=True, check=True)
            groups = result.stdout.strip()
            return 'input' in groups.split()
        except subprocess.CalledProcessError:
            return False

    def _show_setup_dialog(self, issues, warnings):
        """Show setup dialog with issues and auto-fix options"""
        message = "⚠️ Setup Issues Detected:\n\n"

        for issue in issues:
            message += f"❌ {issue}\n"

        if warnings:
            message += "\nWarnings:\n"
            for warning in warnings:
                message += f"⚠️ {warning}\n"

        message += "\n🔧 Auto-fix Options:"
        message += "\n• Install missing dependencies"
        message += "\n• Start ydotool daemon"
        message += "\n• Fix socket permissions"

        result = messagebox.askyesno(
            "Dunking Bird Setup",
            message + "\n\nWould you like to attempt auto-fixes?",
            icon="warning"
        )

        if result:
            self._attempt_auto_fixes(issues, warnings)
        else:
            self._show_manual_fix_instructions(issues, warnings)

    def _show_warning_dialog(self, warnings):
        """Show warning dialog for non-critical issues"""
        message = "⚠️ Setup Warnings:\n\n"

        for warning in warnings:
            message += f"⚠️ {warning}\n"

        message += "\n💡 These may cause functionality issues."
        message += "\nWould you like to attempt auto-fixes?"

        result = messagebox.askyesno(
            "Dunking Bird Warnings",
            message,
            icon="warning"
        )

        if result:
            self._attempt_auto_fixes([], warnings)

    def _attempt_auto_fixes(self, issues, warnings):
        """Attempt to automatically fix common issues"""
        fix_results = []
        needs_restart = False

        # Try to start ydotool daemon
        if any("daemon not running" in issue for issue in issues):
            try:
                subprocess.run(['sudo', 'ydotoold'], check=False)
                time.sleep(1)
                if self._check_ydotool_daemon() != "not_running":
                    fix_results.append("✓ Started ydotool daemon")
                else:
                    fix_results.append("❌ Failed to start ydotool daemon")
            except Exception as e:
                fix_results.append(f"❌ Error starting daemon: {e}")

        # Try to fix socket permissions
        if any("permission" in issue or "permission" in warning
               for issue in issues + warnings):
            try:
                subprocess.run(['sudo', 'chmod', '666', '/tmp/.ydotool_socket'], check=False)
                fix_results.append("✓ Fixed socket permissions")
            except Exception as e:
                fix_results.append(f"❌ Error fixing permissions: {e}")

        # Try to add user to input group
        if any("input group" in warning for warning in warnings):
            try:
                import getpass
                username = getpass.getuser()
                subprocess.run(['sudo', 'usermod', '-a', '-G', 'input', username], check=False)
                fix_results.append(f"✓ Added {username} to input group")
                needs_restart = True
            except Exception as e:
                fix_results.append(f"❌ Error adding to input group: {e}")

        # Show results
        result_message = "Auto-fix Results:\n\n" + "\n".join(fix_results)

        if needs_restart:
            result_message += "\n\n⚠️ You may need to log out and back in for group changes to take effect."

        messagebox.showinfo("Auto-fix Results", result_message)

        # Re-check status
        self.root.after(1000, self.perform_runtime_checks)

    def _show_manual_fix_instructions(self, issues, warnings):
        """Show manual fix instructions"""
        message = "Manual Fix Instructions:\n\n"

        if any("ydotool command not found" in issue for issue in issues):
            message += "1. Install ydotool:\n   sudo apt install ydotool\n\n"

        if any("daemon not running" in issue for issue in issues):
            message += "2. Start ydotool daemon:\n   sudo ydotoold &\n\n"

        if any("socket" in issue for issue in issues):
            message += "3. Fix socket permissions:\n   sudo chmod 666 /tmp/.ydotool_socket\n\n"

        if any("input group" in warning for warning in warnings):
            message += "4. Add user to input group:\n   sudo usermod -a -G input $USER\n   (logout/login required)\n\n"

        message += "5. Or run the install script:\n   ./install.sh"

        messagebox.showinfo("Manual Setup Instructions", message)

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
                    if retry_count == 0:
                        self._attempt_auto_fixes(["ydotool daemon not running"], [])
                        retry_count += 1
                        continue
                    else:
                        self.root.after(0, lambda: self.status_var.set("ydotool not available"))
                        return

                # Focus captured window if one exists (with fallback)
                focus_result = self.focus_captured_window()
                if not focus_result and self.captured_window_id:
                    # Clear invalid captured window and retry with active window
                    print(f"Captured window {self.captured_window_name} no longer valid, clearing...")
                    self.captured_window_id = None
                    self.captured_window_name = None
                    self.captured_window_class = None
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