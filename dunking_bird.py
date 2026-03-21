#!/usr/bin/env python3
"""
Dunking Bird - Automated text sender for active windows
Sends text to the currently active window at regular intervals
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import subprocess
import os
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

        self.setup_gui()

    def setup_gui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

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

        # Text area label
        ttk.Label(main_frame, text="Text to send:").grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.N), pady=(10, 5))

        # Text area
        self.text_area = scrolledtext.ScrolledText(main_frame, width=40, height=8, wrap=tk.WORD)
        self.text_area.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        self.text_area.insert(tk.END, "continue")

        # Status label
        self.status_var = tk.StringVar(value="Stopped")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, font=("Arial", 10))
        status_label.grid(row=5, column=0, columnspan=2, pady=5)

        # Next send countdown
        self.countdown_var = tk.StringVar(value="")
        countdown_label = ttk.Label(main_frame, textvariable=self.countdown_var, font=("Arial", 9))
        countdown_label.grid(row=6, column=0, columnspan=2, pady=5)

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
        """Send text using ydotool - Wayland compatible"""
        try:
            text_to_send = self.text_area.get(1.0, tk.END).strip()
            if not text_to_send:
                return

            print(f"Sending text via ydotool: {text_to_send}")

            # Use ydotool to type text with newline (works on Wayland)
            text_with_enter = text_to_send + '\n'
            subprocess.run(['ydotool', 'type', '--delay', '50', text_with_enter], check=True)

            print(f"Successfully sent text via ydotool: {text_to_send}")
            current_time = time.strftime("%H:%M:%S")
            self.root.after(0, lambda: self.status_var.set(f"Running - Last sent at {current_time}"))

        except subprocess.CalledProcessError as e:
            print(f"Error sending text via ydotool: {e}")
            self.root.after(0, lambda: self.status_var.set(f"Error sending text via ydotool"))
        except Exception as e:
            print(f"Unexpected error with ydotool: {e}")
            self.root.after(0, lambda: self.status_var.set(f"Error: {e}"))

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