#!/usr/bin/env python3
"""
Dunking Bird - Automated text sender for multiple windows
Sends configurable text to specified windows at regular intervals.
Supports multiple concurrent dunkers, each targeting a different window.
All sends are serialized with a 2-second gap to avoid OS race conditions.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import subprocess
import os
import json

# Import pynput with error handling
try:
    from pynput import keyboard
    from pynput.keyboard import Key, Listener
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

    class Key:
        pass

    class Listener:
        def __init__(self, *args, **kwargs):
            pass
        def start(self):
            pass
        def stop(self):
            pass

    class keyboard:
        @staticmethod
        def press_and_release(*args):
            pass


class DunkerRow:
    """One dunking bird instance — a single row in the grid."""

    def __init__(self, app, parent_frame, row_num):
        self.app = app
        self.parent_frame = parent_frame
        self.row_num = row_num
        self.is_running = False
        self.timer_thread = None
        self.interval_seconds = 600

        # Window capture state
        self.captured_window_id = None
        self.captured_window_name = None
        self.captured_window_class = None
        self.captured_compositor = None

        self._build_widgets()

    def _build_widgets(self):
        r = self.row_num
        f = self.parent_frame

        self.num_label = ttk.Label(f, text=f"#{r}", width=3, anchor=tk.CENTER)
        self.num_label.grid(row=r, column=0, padx=(2, 4), pady=3)

        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(f, textvariable=self.status_var, width=22, anchor=tk.W)
        self.status_label.grid(row=r, column=1, padx=2, pady=3, sticky=tk.W)

        self.window_var = tk.StringVar(value="(no window)")
        self.window_label = ttk.Label(f, textvariable=self.window_var, width=24, anchor=tk.W,
                                       foreground="blue")
        self.window_label.grid(row=r, column=2, padx=2, pady=3, sticky=tk.W)

        self.interval_var = tk.StringVar(value="10.0")
        self.interval_spin = ttk.Spinbox(f, from_=0.5, to=120, increment=0.5,
                                          textvariable=self.interval_var, width=5, format="%.1f")
        self.interval_spin.grid(row=r, column=3, padx=2, pady=3)

        self.text_var = tk.StringVar(value="continue")
        self.text_entry = ttk.Entry(f, textvariable=self.text_var, width=15)
        self.text_entry.grid(row=r, column=4, padx=2, pady=3)

        self.capture_btn = ttk.Button(f, text="Capture", command=self.capture_window, width=7)
        self.capture_btn.grid(row=r, column=5, padx=2, pady=3)

        self.test_btn = ttk.Button(f, text="Test", command=self.test_send, width=5)
        self.test_btn.grid(row=r, column=6, padx=2, pady=3)

        self.start_stop_btn = ttk.Button(f, text="Start", command=self.toggle_running, width=6)
        self.start_stop_btn.grid(row=r, column=7, padx=2, pady=3)

        self._all_widgets = [
            self.num_label, self.status_label, self.window_label,
            self.interval_spin, self.text_entry, self.capture_btn,
            self.test_btn, self.start_stop_btn,
        ]

    def destroy(self):
        self.stop()
        for w in self._all_widgets:
            w.destroy()

    def regrid(self, new_row):
        """Move this row to a new grid position."""
        self.row_num = new_row
        self.num_label.config(text=f"#{new_row}")
        for w in self._all_widgets:
            w.grid_configure(row=new_row)

    # ── controls ──────────────────────────────────────────────

    def toggle_running(self):
        if self.is_running:
            self.stop()
        else:
            self.start()

    def start(self):
        try:
            mins = float(self.interval_var.get())
            if mins <= 0:
                raise ValueError
            self.interval_seconds = mins * 60
        except ValueError:
            self.status_var.set("Bad interval!")
            return
        self.is_running = True
        self.start_stop_btn.config(text="Stop")
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()

    def stop(self):
        self.is_running = False
        self.start_stop_btn.config(text="Start")
        self.status_var.set("Stopped")

    # ── capture ───────────────────────────────────────────────

    def capture_window(self):
        self.capture_btn.config(state="disabled")
        self._capture_countdown(2)

    def _capture_countdown(self, n):
        if n > 0:
            self.window_var.set(f"Capturing in {n}...")
            self.app.root.after(1000, lambda: self._capture_countdown(n - 1))
        else:
            self._do_capture()

    def _do_capture(self):
        try:
            if os.environ.get("XDG_SESSION_TYPE") == "wayland":
                info = self.app.get_wayland_window_info()
                if info:
                    self.captured_window_id = info["id"]
                    self.captured_window_name = info["name"]
                    self.captured_window_class = info["class"]
                    self.captured_compositor = info.get("compositor", "unknown")
                    self._show_window_name()
                else:
                    self.window_var.set("Capture failed")
            else:
                wid = self.app.select_window_interactive()
                if wid:
                    self.captured_window_id = wid
                    try:
                        r = subprocess.run(["kdotool", "getwindowname", wid],
                                           capture_output=True, text=True, check=True)
                        self.captured_window_name = r.stdout.strip()
                    except Exception:
                        self.captured_window_name = f"Window {wid}"
                    self.captured_compositor = "x11"
                    self._show_window_name()
                else:
                    self.window_var.set("Cancelled")
        except Exception as e:
            self.window_var.set("Error")
            print(f"Capture error on dunker #{self.row_num}: {e}")
        finally:
            self.capture_btn.config(state="normal")

    def _show_window_name(self):
        name = self.captured_window_name or "(unknown)"
        if len(name) > 28:
            name = name[:25] + "..."
        self.window_var.set(name)

    # ── test ──────────────────────────────────────────────────

    def test_send(self):
        self.test_btn.config(state="disabled")
        threading.Thread(target=self._test_send_worker, daemon=True).start()

    def _test_send_worker(self):
        try:
            for i in range(2, 0, -1):
                self.app.root.after(0, lambda n=i: self.status_var.set(f"Test in {n}..."))
                time.sleep(1)

            with self.app.send_lock:
                self.app.root.after(0, lambda: self.status_var.set("Sending..."))
                ok = self._do_send()
                time.sleep(2)  # OS settle-down

            t = time.strftime("%H:%M:%S")
            if ok:
                self.app.root.after(0, lambda: self.status_var.set(f"Tested {t}"))
            else:
                self.app.root.after(0, lambda: self.status_var.set("Test failed"))
        except Exception as e:
            self.app.root.after(0, lambda: self.status_var.set("Test failed"))
            print(f"Test error dunker #{self.row_num}: {e}")
        finally:
            self.app.root.after(0, lambda: self.test_btn.config(state="normal"))

    # ── timer ─────────────────────────────────────────────────

    def _timer_loop(self):
        while self.is_running:
            # Re-read interval each cycle so changes take effect live
            try:
                mins = float(self.interval_var.get())
                total = max(1, int(mins * 60))
            except ValueError:
                total = int(self.interval_seconds)

            # Countdown
            for tick in range(total):
                if not self.is_running:
                    return
                rem = total - tick
                m, s = divmod(rem, 60)
                self.app.root.after(0,
                    lambda mm=m, ss=s: self.status_var.set(f"Next: {mm:02d}:{ss:02d}"))
                time.sleep(1)

            if not self.is_running:
                return

            # Acquire global send lock (may wait for other dunkers)
            self.app.root.after(0, lambda: self.status_var.set("Waiting..."))
            with self.app.send_lock:
                if not self.is_running:
                    return
                self.app.root.after(0, lambda: self.status_var.set("Sending..."))
                ok = self._do_send()
                time.sleep(2)  # OS settle-down

            if self.is_running:
                t = time.strftime("%H:%M:%S")
                if ok:
                    self.app.root.after(0, lambda tt=t: self.status_var.set(f"Sent {tt}"))
                else:
                    self.app.root.after(0, lambda: self.status_var.set("Send failed!"))
                time.sleep(1)  # brief pause so "Sent" is visible before countdown restarts

    # ── send ──────────────────────────────────────────────────

    def _do_send(self):
        """Send text to this dunker's target window. Caller must hold send_lock.
        Returns True on success, False on failure."""
        text = self.text_var.get().strip()
        if not text:
            return True  # nothing to send is not an error

        # Focus target window
        self.app.focus_window_for_dunker(
            self.captured_window_id,
            self.captured_window_name,
            self.captured_compositor,
        )

        # Send via ydotool with retries
        return self.app.send_text_ydotool(text)


class DunkingBirdApp:
    """Main application — manages multiple DunkerRow instances."""

    def __init__(self, root):
        self.root = root
        self.root.title("Dunking Bird")
        self.root.geometry("920x400")
        self.root.minsize(820, 250)
        self.root.resizable(True, True)

        self.dunkers: list[DunkerRow] = []
        self.send_lock = threading.Lock()

        self._setup_gui()
        self.root.after(500, self._runtime_checks)

    # ── GUI setup ─────────────────────────────────────────────

    def _setup_gui(self):
        main = ttk.Frame(self.root, padding="8")
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Top bar: title + add/remove buttons
        top = ttk.Frame(main)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        ttk.Label(top, text="Dunking Bird", font=("Arial", 14, "bold")).grid(
            row=0, column=0, sticky=tk.W)

        btns = ttk.Frame(top)
        btns.grid(row=0, column=1, sticky=tk.E)
        ttk.Button(btns, text="+ Add Dunk", command=self.add_dunker).grid(
            row=0, column=0, padx=4)
        ttk.Button(btns, text="- Remove Dunk", command=self.remove_dunker).grid(
            row=0, column=1, padx=4)

        ttk.Separator(main, orient="horizontal").grid(row=1, column=0, sticky="ew", pady=4)

        # Column headers
        hdr = ttk.Frame(main)
        hdr.grid(row=2, column=0, sticky="ew")
        for i, (txt, w) in enumerate([
            ("#", 3), ("Status", 22), ("Window", 24), ("Min", 5),
            ("Text", 15), ("", 7), ("", 5), ("", 6),
        ]):
            ttk.Label(hdr, text=txt, font=("Arial", 9, "bold"), width=w, anchor=tk.W).grid(
                row=0, column=i, padx=2)

        # Scrollable dunker area
        canvas_frame = ttk.Frame(main)
        canvas_frame.grid(row=3, column=0, sticky="nsew")
        main.rowconfigure(3, weight=1)
        main.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        vsb = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.dunkers_frame = ttk.Frame(self.canvas)

        self.dunkers_frame.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.dunkers_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=vsb.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        # Mouse wheel scrolling (Linux)
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        # Global status bar
        ttk.Separator(main, orient="horizontal").grid(row=4, column=0, sticky="ew", pady=4)
        self.global_status_var = tk.StringVar(value="")
        ttk.Label(main, textvariable=self.global_status_var, font=("Arial", 9)).grid(
            row=5, column=0, sticky=tk.W)

        # Start with one dunker
        self.add_dunker()

    # ── dunker management ─────────────────────────────────────

    def add_dunker(self):
        row_num = len(self.dunkers) + 1
        d = DunkerRow(self, self.dunkers_frame, row_num)
        self.dunkers.append(d)
        self._update_count()

    def remove_dunker(self):
        if not self.dunkers:
            return
        d = self.dunkers.pop()
        d.destroy()
        self._update_count()

    def _update_count(self):
        n = len(self.dunkers)
        running = sum(1 for d in self.dunkers if d.is_running)
        if running:
            self.global_status_var.set(
                f"✓ {n} dunker{'s' if n != 1 else ''} ({running} running)")
        else:
            self.global_status_var.set(f"✓ {n} dunker{'s' if n != 1 else ''}")

    # ── runtime checks ────────────────────────────────────────

    def _runtime_checks(self):
        try:
            if not self._check_ydotool_available():
                self.global_status_var.set("⚠️  ydotool not found – run ./setup.py")
            else:
                self._update_count()
        except Exception as e:
            self.global_status_var.set(f"Check error: {e}")

    # ── shared: ydotool helpers ───────────────────────────────

    def _check_ydotool_available(self):
        try:
            r = subprocess.run(["ydotool", "help"], capture_output=True, text=True, timeout=5)
            return "Usage:" in r.stderr or "Usage:" in r.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        except subprocess.CalledProcessError:
            return True

    def _get_ydotool_socket_path(self):
        env_socket = os.environ.get("YDOTOOL_SOCKET")
        if env_socket and os.path.exists(env_socket):
            return env_socket
        for path in [
            "/tmp/.ydotool_socket",
            f"/run/user/{os.getuid()}/ydotool_socket",
            os.path.expanduser("~/.ydotool_socket"),
            "/tmp/ydotool_socket",
        ]:
            if os.path.exists(path):
                return path
        try:
            r = subprocess.run(["pgrep", "-a", "ydotoold"],
                               capture_output=True, text=True, timeout=3)
            if r.stdout:
                for arg in r.stdout.split():
                    if "socket" in arg.lower() or arg.startswith("/"):
                        if os.path.exists(arg):
                            return arg
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
        return None

    def _ensure_ydotool_socket_permissions(self):
        socket_path = self._get_ydotool_socket_path()
        if not socket_path:
            print("No ydotool socket found – restarting daemon")
            return self._restart_ydotool_daemon()
        try:
            # Check if daemon is actually running (detect stale sockets)
            try:
                r = subprocess.run(["pgrep", "-x", "ydotoold"],
                                   capture_output=True, timeout=3)
                if r.returncode != 0:
                    print("ydotoold not running (stale socket), restarting...")
                    return self._restart_ydotool_daemon()
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass

            if os.access(socket_path, os.R_OK | os.W_OK):
                return True

            print(f"Socket {socket_path} not accessible, fixing permissions...")
            try:
                subprocess.run(["sudo", "chmod", "666", socket_path],
                               capture_output=True, timeout=5)
                if os.access(socket_path, os.R_OK | os.W_OK):
                    print(f"Fixed socket permissions on {socket_path}")
                    return True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass

            print("chmod failed, restarting ydotool daemon...")
            return self._restart_ydotool_daemon()
        except Exception as e:
            print(f"Socket permission error: {e}")
            return self._restart_ydotool_daemon()

    def _restart_ydotool_daemon(self):
        try:
            subprocess.run(["sudo", "pkill", "-9", "ydotoold"],
                           capture_output=True, timeout=3)
            time.sleep(0.5)
            subprocess.Popen(["sudo", "ydotoold"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            socket_path = self._get_ydotool_socket_path()
            if socket_path:
                try:
                    subprocess.run(["sudo", "chmod", "666", socket_path],
                                   capture_output=True, timeout=3)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    pass
                return os.access(socket_path, os.R_OK | os.W_OK)
            return False
        except Exception as e:
            print(f"Failed to restart ydotool daemon: {e}")
            return False

    # ── shared: send text via ydotool ─────────────────────────

    def send_text_ydotool(self, text):
        """Type *text* + Enter via ydotool with retries.
        Caller must hold send_lock. Returns True on success."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if not self._ensure_ydotool_socket_permissions():
                    print("Socket check failed, trying anyway...")

                if not self._check_ydotool_available():
                    print("ydotool not available")
                    return False

                time.sleep(0.5)
                subprocess.run(["ydotool", "type", "--delay", "50", text],
                               capture_output=True, text=True, check=True, timeout=30)
                time.sleep(1.0)
                subprocess.run(["ydotool", "type", "\n"],
                               capture_output=True, text=True, check=True, timeout=5)
                print(f"Successfully sent: {text}")
                return True

            except subprocess.TimeoutExpired:
                print(f"ydotool timeout (attempt {attempt + 1}/{max_retries})")
                self._ensure_ydotool_socket_permissions()
                time.sleep(1)
            except subprocess.CalledProcessError as e:
                print(f"ydotool error (attempt {attempt + 1}/{max_retries}): {e}")
                self._restart_ydotool_daemon()
            except Exception as e:
                print(f"Unexpected ydotool error (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(1)

        print("All ydotool retries exhausted")
        return False

    # ── shared: window focus ──────────────────────────────────

    def focus_window_for_dunker(self, window_id, window_name, compositor):
        """Focus a dunker's captured window. Noop if window_id is None."""
        if not window_id:
            return True

        try:
            print(f"Focusing: {window_name}")
            r = subprocess.run(["kdotool", "windowactivate", window_id],
                               capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                print(f"✅ Focused {window_name}")
                time.sleep(0.2)
                return True
            else:
                print(f"kdotool failed ({r.returncode}), Alt+Tab fallback")
                subprocess.run(["ydotool", "key", "alt+Tab"], timeout=1)
                time.sleep(0.2)
                return True
        except FileNotFoundError:
            try:
                subprocess.run(["ydotool", "key", "alt+Tab"], timeout=1)
                time.sleep(0.2)
                return True
            except Exception as e:
                print(f"Focus failed completely: {e}")
                return True
        except Exception as e:
            print(f"Focus error: {e}")
            return True

    # ── shared: window info ───────────────────────────────────

    def get_wayland_window_info(self):
        """Get info about the currently active window on Wayland."""
        # kdotool (KDE Wayland + X11)
        try:
            r = subprocess.run(["kdotool", "getactivewindow"],
                               capture_output=True, text=True, check=True)
            wid = r.stdout.strip()
            if wid:
                nr = subprocess.run(["kdotool", "getwindowname", wid],
                                    capture_output=True, text=True, check=True)
                cr = subprocess.run(["kdotool", "getwindowclassname", wid],
                                    capture_output=True, text=True, check=True)
                return {"id": wid, "name": nr.stdout.strip(),
                        "class": cr.stdout.strip(), "compositor": "kde"}
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        def cmd_exists(cmd):
            try:
                subprocess.run(["which", cmd], capture_output=True, check=True)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                return False

        # Sway
        if cmd_exists("swaymsg"):
            try:
                r = subprocess.run(["swaymsg", "-t", "get_tree"],
                                   capture_output=True, text=True, check=True)
                tree = json.loads(r.stdout)

                def find_focused(node):
                    if node.get("focused"):
                        return node
                    for ch in node.get("nodes", []) + node.get("floating_nodes", []):
                        found = find_focused(ch)
                        if found:
                            return found
                    return None

                focused = find_focused(tree)
                if focused:
                    return {"id": str(focused.get("id", "?")),
                            "name": focused.get("name", "?"),
                            "class": focused.get("app_id", "?"),
                            "compositor": "sway"}
            except Exception:
                pass

        # Hyprland
        if cmd_exists("hyprctl"):
            try:
                r = subprocess.run(["hyprctl", "activewindow", "-j"],
                                   capture_output=True, text=True, check=True)
                w = json.loads(r.stdout)
                if w and "address" in w:
                    return {"id": w["address"], "name": w.get("title", "?"),
                            "class": w.get("class", "?"), "compositor": "hyprland"}
            except Exception:
                pass

        # GNOME
        if cmd_exists("gdbus"):
            try:
                r = subprocess.run(
                    ["gdbus", "call", "--session", "--dest", "org.gnome.Shell",
                     "--object-path", "/org/gnome/Shell", "--method",
                     "org.gnome.Shell.Eval",
                     "global.display.focus_window.get_title()"],
                    capture_output=True, text=True, check=True)
                if r.stdout and "'" in r.stdout:
                    s = r.stdout.find("'") + 1
                    e = r.stdout.rfind("'")
                    if 0 < s < e:
                        return {"id": "gnome_active", "name": r.stdout[s:e],
                                "class": "unknown", "compositor": "gnome"}
            except Exception:
                pass

        # KDE fallback via qdbus
        for qdbus_cmd in ["qdbus6", "qdbus-qt5", "qdbus"]:
            if cmd_exists(qdbus_cmd):
                try:
                    r = subprocess.run(["kdotool", "getactivewindow"],
                                       capture_output=True, text=True, check=True)
                    wid = r.stdout.strip()
                    if wid:
                        nr = subprocess.run(["kdotool", "getwindowname", wid],
                                            capture_output=True, text=True, check=True)
                        return {"id": wid, "name": nr.stdout.strip(),
                                "class": "kde-window", "compositor": "kde"}
                except Exception:
                    pass
                break

        return {"id": "wayland_fallback", "name": "Active Window (Generic)",
                "class": "unknown", "compositor": "wayland_generic"}

    def select_window_interactive(self):
        """X11: let user click a window to select it."""
        try:
            r = subprocess.run(["xdotool", "selectwindow"],
                               capture_output=True, text=True, check=True, timeout=30)
            wid = r.stdout.strip()
            return wid if wid else None
        except Exception:
            return None


def main():
    root = tk.Tk()
    app = DunkingBirdApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
