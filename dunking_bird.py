#!/usr/bin/env python3
"""
Dunking Bird - Automated text sender for active windows
Sends text to the currently active window at regular intervals
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
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

        # Timer interval input
        ttk.Label(main_frame, text="Interval (minutes):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.interval_var = tk.StringVar(value="10")
        interval_entry = ttk.Entry(main_frame, textvariable=self.interval_var, width=10)
        interval_entry.grid(row=1, column=1, sticky=tk.W, pady=5)

        # Start/Stop button
        self.start_stop_btn = ttk.Button(main_frame, text="Start", command=self.toggle_running)
        self.start_stop_btn.grid(row=2, column=0, columnspan=2, pady=10)

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
                self.send_text()

    def send_text(self):
        """Send the text from the text area to the active window"""
        try:
            text_to_send = self.text_area.get(1.0, tk.END).strip()
            if text_to_send:
                # Create a keyboard controller
                controller = keyboard.Controller()

                # Small delay to ensure window focus
                time.sleep(0.1)

                # Type the text
                controller.type(text_to_send)

                # Press Enter
                controller.press(Key.enter)
                controller.release(Key.enter)

                print(f"Sent text: {text_to_send}")

        except Exception as e:
            print(f"Error sending text: {e}")
            self.status_var.set(f"Error sending text: {e}")


def main():
    root = tk.Tk()
    app = DunkingBird(root)
    root.mainloop()


if __name__ == "__main__":
    main()