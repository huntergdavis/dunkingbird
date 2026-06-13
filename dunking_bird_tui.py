#!/usr/bin/env python3
"""
Dunking Bird TUI - terminal interface for automated text sending.
Supports multiple concurrent dunkers, window capture, test sends, custom text,
and live countdowns using the same ydotool/window-targeting behavior as the GUI.
"""

import curses
from curses import textpad
import json
import os
import shutil
import subprocess
import threading
import time

YDOTOOL_KEY_DELAY_MS = 2
YDOTOOL_PRE_TYPE_DELAY_S = 0.05
YDOTOOL_POST_TYPE_DELAY_S = 0.1
YDOTOOL_TIMEOUT_PADDING_S = 10


def clip(value, width):
    if width <= 0:
        return ""
    text = str(value)
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[:width - 3] + "..."


class DunkerTuiRow:
    """One dunking bird instance shown as one row in the terminal UI."""

    def __init__(self, app, row_num):
        self.app = app
        self.row_num = row_num
        self.is_running = False
        self.timer_thread = None
        self.interval_minutes = "10.0"
        self.interval_seconds = 600
        self.text_value = "continue"
        self.status = "Ready"

        self.captured_window_id = None
        self.captured_window_name = None
        self.captured_window_class = None
        self.captured_compositor = None
        self._lock = threading.Lock()

    def set_status(self, value):
        with self._lock:
            self.status = value

    def get_status(self):
        with self._lock:
            return self.status

    def window_label(self):
        return self.captured_window_name or "(no window)"

    def text_preview(self):
        return self.text_value.replace("\n", " ")

    def toggle_running(self):
        if self.is_running:
            self.stop()
        else:
            self.start()

    def start(self):
        try:
            mins = float(self.interval_minutes)
            if mins <= 0:
                raise ValueError
            self.interval_seconds = mins * 60
        except ValueError:
            self.set_status("Bad interval!")
            return

        if self.is_running:
            return
        self.is_running = True
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()
        self.app.update_count()

    def stop(self):
        self.is_running = False
        self.set_status("Stopped")
        self.app.update_count()

    def destroy(self):
        self.stop()

    def capture_window(self):
        threading.Thread(target=self._capture_worker, daemon=True).start()

    def _capture_worker(self):
        try:
            for i in range(2, 0, -1):
                self.set_status(f"Capture in {i}...")
                time.sleep(1)
            if os.environ.get("XDG_SESSION_TYPE") == "wayland":
                info = self.app.get_wayland_window_info()
                if info:
                    self.captured_window_id = info["id"]
                    self.captured_window_name = info["name"]
                    self.captured_window_class = info["class"]
                    self.captured_compositor = info.get("compositor", "unknown")
                    self.set_status("Captured")
                else:
                    self.set_status(self.app.get_wayland_capture_error())
            else:
                self.set_status("Click window...")
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
                    self.set_status("Captured")
                else:
                    self.set_status("Cancelled")
        except Exception as e:
            self.set_status("Capture error")
            print(f"Capture error on dunker #{self.row_num}: {e}")

    def test_send(self):
        threading.Thread(target=self._test_send_worker, daemon=True).start()

    def _test_send_worker(self):
        try:
            for i in range(2, 0, -1):
                self.set_status(f"Test in {i}...")
                time.sleep(1)
            with self.app.send_lock:
                self.set_status("Sending...")
                ok = self._do_send()
                self.app.suppress_typed_input()
                time.sleep(2)
            t = time.strftime("%H:%M:%S")
            self.set_status(f"Tested {t}" if ok else "Test failed")
        except Exception as e:
            self.set_status("Test failed")
            print(f"Test error dunker #{self.row_num}: {e}")

    def _timer_loop(self):
        while self.is_running:
            try:
                mins = float(self.interval_minutes)
                total = max(1, int(mins * 60))
            except ValueError:
                total = int(self.interval_seconds)

            for tick in range(total):
                if not self.is_running:
                    return
                rem = total - tick
                m, s = divmod(rem, 60)
                self.set_status(f"Next: {m:02d}:{s:02d}")
                time.sleep(1)

            if not self.is_running:
                return

            self.set_status("Waiting...")
            with self.app.send_lock:
                if not self.is_running:
                    return
                self.set_status("Sending...")
                ok = self._do_send()
                self.app.suppress_typed_input()
                time.sleep(2)

            if self.is_running:
                t = time.strftime("%H:%M:%S")
                self.set_status(f"Sent {t}" if ok else "Send failed!")
                time.sleep(1)

    def _do_send(self):
        text = self.text_value.strip()
        if not text:
            return True
        self.app.focus_window_for_dunker(
            self.captured_window_id,
            self.captured_window_name,
            self.captured_compositor,
        )
        return self.app.send_text_ydotool(text)


class DunkingBirdTui:
    """Main terminal application."""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.dunkers = []
        self.selected = 0
        self.send_lock = threading.Lock()
        self.status_lock = threading.Lock()
        self.global_status = ""
        self.suppress_input_until = 0
        self.quit_requested = False

        curses.curs_set(0)
        self.stdscr.keypad(True)
        self.stdscr.timeout(200)
        self.add_dunker()
        self.runtime_checks()

    def run(self):
        while not self.quit_requested:
            self.draw()
            key = self.stdscr.getch()
            if key != -1:
                if time.time() < self.suppress_input_until:
                    continue
                self.handle_key(key)
        self.shutdown()

    def suppress_typed_input(self):
        self.suppress_input_until = time.time() + 1.0

    def add_dunker(self):
        self.dunkers.append(DunkerTuiRow(self, len(self.dunkers) + 1))
        self.selected = len(self.dunkers) - 1
        self.update_count()

    def remove_dunker(self):
        if not self.dunkers:
            return
        d = self.dunkers.pop(self.selected)
        d.destroy()
        for index, dunker in enumerate(self.dunkers, start=1):
            dunker.row_num = index
        self.selected = max(0, min(self.selected, len(self.dunkers) - 1))
        if not self.dunkers:
            self.add_dunker()
        self.update_count()

    def update_count(self):
        n = len(self.dunkers)
        running = sum(1 for d in self.dunkers if d.is_running)
        if running:
            self.set_global_status(f"{n} dunker{'s' if n != 1 else ''} ({running} running)")
        else:
            self.set_global_status(f"{n} dunker{'s' if n != 1 else ''}")

    def set_global_status(self, value):
        with self.status_lock:
            self.global_status = value

    def get_global_status(self):
        with self.status_lock:
            return self.global_status

    def runtime_checks(self):
        try:
            if not self._check_ydotool_available():
                self.set_global_status("ydotool not found - run ./setup.py")
            elif (os.environ.get("XDG_SESSION_TYPE") == "wayland"
                  and not self._has_wayland_capture_backend()):
                self.set_global_status("Wayland capture backend missing - install kdotool")
            else:
                self.update_count()
        except Exception as e:
            self.set_global_status(f"Check error: {e}")

    def handle_key(self, key):
        if key in (ord("q"), 27):
            self.quit_requested = True
        elif key in (curses.KEY_UP, ord("k")):
            self.selected = max(0, self.selected - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            self.selected = min(len(self.dunkers) - 1, self.selected + 1)
        elif key == ord("a"):
            self.add_dunker()
        elif key == ord("d"):
            self.remove_dunker()
        elif key in (ord(" "), ord("s")):
            self.current().toggle_running()
        elif key == ord("c"):
            self.current().capture_window()
        elif key == ord("t"):
            self.current().test_send()
        elif key == ord("i"):
            self.edit_interval()
        elif key == ord("e"):
            self.edit_text()

    def current(self):
        return self.dunkers[self.selected]

    def edit_interval(self):
        d = self.current()
        value = self.line_modal("Interval minutes", d.interval_minutes)
        if value is not None:
            value = value.strip() or d.interval_minutes
            try:
                if float(value) <= 0:
                    raise ValueError
            except ValueError:
                d.set_status("Bad interval!")
                return
            d.interval_minutes = value
            d.set_status("Interval set")

    def edit_text(self):
        d = self.current()
        new_text = self.text_modal(d.text_value)
        if new_text is not None:
            d.text_value = new_text.strip()
            d.set_status("Text set")

    def line_modal(self, label, default=""):
        h, w = self.stdscr.getmaxyx()
        box_w = min(max(48, len(label) + 18), max(20, w - 4))
        box_h = 7
        y = max(0, (h - box_h) // 2)
        x = max(0, (w - box_w) // 2)
        win = curses.newwin(box_h, box_w, y, x)
        win.keypad(True)
        win.box()
        self.safe_addstr(win, 1, 2, label, box_w - 4, curses.A_BOLD)
        self.safe_addstr(win, 2, 2, f"Current: {default}", box_w - 4)
        self.safe_addstr(win, 3, 2, "Enter keeps current, Esc cancels", box_w - 4)
        input_w = box_w - 4
        value = ""
        cursor = len(value)
        curses.curs_set(1)
        try:
            while True:
                self.safe_addstr(win, 5, 2, " " * input_w, input_w)
                visible = value[-input_w:] if len(value) > input_w else value
                self.safe_addstr(win, 5, 2, visible, input_w)
                win.move(5, 2 + min(cursor, input_w - 1))
                win.refresh()
                key = win.getch()
                if key in (10, 13, curses.KEY_ENTER):
                    return value or default
                if key in (27,):
                    return None
                if key in (curses.KEY_BACKSPACE, 127, 8):
                    if cursor > 0:
                        value = value[:cursor - 1] + value[cursor:]
                        cursor -= 1
                elif key == curses.KEY_DC:
                    if cursor < len(value):
                        value = value[:cursor] + value[cursor + 1:]
                elif key == curses.KEY_LEFT:
                    cursor = max(0, cursor - 1)
                elif key == curses.KEY_RIGHT:
                    cursor = min(len(value), cursor + 1)
                elif key == curses.KEY_HOME:
                    cursor = 0
                elif key == curses.KEY_END:
                    cursor = len(value)
                elif 32 <= key <= 126:
                    ch = chr(key)
                    value = value[:cursor] + ch + value[cursor:]
                    cursor += 1
        finally:
            curses.curs_set(0)

    def text_modal(self, initial_text):
        h, w = self.stdscr.getmaxyx()
        win = curses.newwin(h, w, 0, 0)
        win.keypad(True)
        text_h = max(1, h - 5)
        text_w = max(1, w - 4)
        edit = curses.newwin(text_h, text_w, 3, 2)
        edit.keypad(True)
        edit.scrollok(True)

        cancelled = False

        def validate(ch):
            nonlocal cancelled
            if ch == 27:
                cancelled = True
                return 7
            if ch in (9,):
                return ord(" ")
            return ch

        try:
            win.erase()
            win.box()
            self.safe_addstr(win, 1, 2, "Edit text to send", w - 4, curses.A_BOLD)
            self.safe_addstr(win, 2, 2, "Ctrl+G saves, Esc cancels", w - 4)
            for idx, line in enumerate(initial_text.splitlines() or [""]):
                if idx >= text_h:
                    break
                self.safe_addstr(edit, idx, 0, line, text_w)
            win.refresh()
            edit.refresh()
            curses.curs_set(1)
            box = textpad.Textbox(edit, insert_mode=True)
            text = box.edit(validate)
            if cancelled:
                return None
            return text.rstrip()
        finally:
            curses.curs_set(0)

    def draw(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        self.safe_addstr(self.stdscr, 0, 0, "Dunking Bird TUI", w - 1, curses.A_BOLD)
        help_text = "a add  d remove  c capture  t test  i interval  e text  space start/stop  q quit"
        self.safe_addstr(self.stdscr, 1, 0, help_text, w - 1)
        self.safe_hline(self.stdscr, 2, 0, w - 1)

        header = self.format_row("#", "Status", "Window", "Min", "Text", w)
        self.safe_addstr(self.stdscr, 3, 0, header, w - 1, curses.A_BOLD)

        visible_rows = max(0, h - 7)
        start = 0
        if self.selected >= visible_rows:
            start = self.selected - visible_rows + 1
        for screen_y, index in enumerate(range(start, min(len(self.dunkers), start + visible_rows)), start=4):
            d = self.dunkers[index]
            row = self.format_row(
                str(d.row_num),
                d.get_status(),
                d.window_label(),
                d.interval_minutes,
                d.text_preview(),
                w,
            )
            attr = curses.A_REVERSE if index == self.selected else curses.A_NORMAL
            self.safe_addstr(self.stdscr, screen_y, 0, row, w - 1, attr)

        self.safe_hline(self.stdscr, h - 3, 0, w - 1)
        self.safe_addstr(self.stdscr, h - 2, 0, self.get_global_status(), w - 1)
        self.stdscr.refresh()

    def format_row(self, num, status, window, minutes, text, width):
        columns = [
            clip(num, 4).ljust(4),
            clip(status, 18).ljust(18),
            clip(window, 28).ljust(28),
            clip(minutes, 7).rjust(7),
            clip(text, max(10, width - 62)),
        ]
        row = clip(" ".join(columns), width - 1)
        return row.ljust(max(0, width - 1))

    def safe_hline(self, win, y, x, width):
        if width <= 0:
            return
        try:
            win.hline(y, x, "-", width)
        except curses.error:
            pass

    def safe_addstr(self, win, y, x, value, width, attr=0):
        if width <= 0:
            return
        try:
            max_y, max_x = win.getmaxyx()
            if y < 0 or y >= max_y or x < 0 or x >= max_x:
                return
            usable = min(width, max_x - x - 1)
            if usable <= 0:
                return
            win.addstr(y, x, clip(value, usable).ljust(usable), attr)
        except curses.error:
            pass

    def shutdown(self):
        for dunker in self.dunkers:
            dunker.destroy()

    def _check_ydotool_available(self):
        try:
            r = subprocess.run(["ydotool", "help"], capture_output=True, text=True, timeout=5)
            return "Usage:" in r.stderr or "Usage:" in r.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        except subprocess.CalledProcessError:
            return True

    def _command_exists(self, cmd):
        return shutil.which(cmd) is not None

    def _has_wayland_capture_backend(self):
        return any(self._command_exists(cmd) for cmd in ["kdotool", "swaymsg", "hyprctl"])

    def get_wayland_capture_error(self):
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        session = os.environ.get("XDG_SESSION_DESKTOP", "").lower()
        if self._command_exists("kdotool"):
            try:
                tmp_free = shutil.disk_usage("/tmp").free
                if tmp_free < 10 * 1024 * 1024:
                    return "Capture failed: /tmp is full"
            except OSError:
                pass
            try:
                r = subprocess.run(["kdotool", "getactivewindow"],
                                   capture_output=True, text=True, timeout=3)
                err = (r.stderr or "").strip()
                if err:
                    return err.splitlines()[0]
            except Exception:
                pass
            return "No active window"
        if self._command_exists("swaymsg"):
            return "No focused Sway window"
        if self._command_exists("hyprctl"):
            return "No active Hyprland window"
        if "kde" in desktop or "plasma" in desktop or "kde" in session:
            return "Install kdotool"
        if "gnome" in desktop or "gnome" in session:
            return "GNOME Wayland unsupported"
        return "No Wayland capture tool"

    def _get_ydotool_socket_path(self):
        env_socket = os.environ.get("YDOTOOL_SOCKET")
        if env_socket and os.path.exists(env_socket):
            return env_socket
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
        for path in [
            os.path.join(runtime_dir, ".ydotool_socket"),
            os.path.join(runtime_dir, "ydotool_socket"),
            "/tmp/.ydotool_socket",
            "/tmp/ydotool_socket",
            os.path.expanduser("~/.ydotool_socket"),
        ]:
            if os.path.exists(path):
                os.environ["YDOTOOL_SOCKET"] = path
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
            self.set_global_status("No ydotool socket found - restarting daemon")
            return self._restart_ydotool_daemon()
        try:
            try:
                r = subprocess.run(["pgrep", "-x", "ydotoold"],
                                   capture_output=True, timeout=3)
                if r.returncode != 0:
                    self.set_global_status("ydotoold not running; restarting...")
                    return self._restart_ydotool_daemon()
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass

            if os.access(socket_path, os.R_OK | os.W_OK):
                return True

            self.set_global_status(f"Fixing ydotool socket permissions")
            try:
                subprocess.run(["sudo", "chmod", "666", socket_path],
                               capture_output=True, timeout=5)
                if os.access(socket_path, os.R_OK | os.W_OK):
                    self.set_global_status("Fixed ydotool socket permissions")
                    return True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass

            self.set_global_status("Restarting ydotool daemon")
            return self._restart_ydotool_daemon()
        except Exception as e:
            self.set_global_status(f"Socket permission error: {e}")
            return self._restart_ydotool_daemon()

    def _restart_ydotool_daemon(self):
        try:
            runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
            socket_path = os.environ.get("YDOTOOL_SOCKET") or os.path.join(
                runtime_dir, ".ydotool_socket")
            os.makedirs(os.path.dirname(socket_path), exist_ok=True)
            os.environ["YDOTOOL_SOCKET"] = socket_path

            subprocess.run(["sudo", "pkill", "-9", "ydotoold"],
                           capture_output=True, timeout=3)
            time.sleep(0.5)
            subprocess.Popen(["sudo", "ydotoold",
                              f"--socket-path={socket_path}",
                              f"--socket-own={os.getuid()}:{os.getgid()}"],
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
            self.set_global_status(f"Failed to restart ydotool daemon: {e}")
            return False

    def send_text_ydotool(self, text):
        max_retries = 3
        estimated_type_seconds = max(
            1.0,
            len(text) * ((YDOTOOL_KEY_DELAY_MS / 1000.0) + 0.005),
        )
        type_timeout = int(estimated_type_seconds * 3) + YDOTOOL_TIMEOUT_PADDING_S
        for attempt in range(max_retries):
            try:
                if not self._ensure_ydotool_socket_permissions():
                    self.set_global_status("Socket check failed, trying anyway")

                if not self._check_ydotool_available():
                    self.set_global_status("ydotool not available")
                    return False

                time.sleep(YDOTOOL_PRE_TYPE_DELAY_S)
                subprocess.run(["ydotool", "type", "--key-delay", str(YDOTOOL_KEY_DELAY_MS), text],
                               capture_output=True, text=True, check=True, timeout=type_timeout)
                time.sleep(YDOTOOL_POST_TYPE_DELAY_S)
                subprocess.run(["ydotool", "key", "28:1", "28:0"],
                               capture_output=True, text=True, check=True, timeout=5)
                self.set_global_status("Send completed")
                return True

            except subprocess.TimeoutExpired:
                self.set_global_status(
                    f"ydotool timeout (attempt {attempt + 1}/{max_retries})")
                return False
            except subprocess.CalledProcessError as e:
                self.set_global_status(f"ydotool error (attempt {attempt + 1}/{max_retries})")
                self._restart_ydotool_daemon()
            except Exception as e:
                self.set_global_status(f"Unexpected ydotool error: {e}")
                time.sleep(1)

        self.set_global_status("All ydotool retries exhausted")
        return False

    def focus_window_for_dunker(self, window_id, window_name, compositor):
        if not window_id:
            return True

        try:
            self.set_global_status(f"Focusing: {window_name}")
            r = subprocess.run(["kdotool", "windowactivate", window_id],
                               capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                self.set_global_status(f"Focused {window_name}")
                time.sleep(0.2)
                return True
            self.set_global_status("kdotool failed; using Alt+Tab fallback")
            subprocess.run(["ydotool", "key", "alt+Tab"], timeout=1)
            time.sleep(0.2)
            return True
        except FileNotFoundError:
            try:
                subprocess.run(["ydotool", "key", "alt+Tab"], timeout=1)
                time.sleep(0.2)
                return True
            except Exception as e:
                self.set_global_status(f"Focus failed: {e}")
                return True
        except Exception as e:
            self.set_global_status(f"Focus error: {e}")
            return True

    def get_wayland_window_info(self):
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

        if self._command_exists("swaymsg"):
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

        if self._command_exists("hyprctl"):
            try:
                r = subprocess.run(["hyprctl", "activewindow", "-j"],
                                   capture_output=True, text=True, check=True)
                w = json.loads(r.stdout)
                if w and "address" in w:
                    return {"id": w["address"], "name": w.get("title", "?"),
                            "class": w.get("class", "?"), "compositor": "hyprland"}
            except Exception:
                pass

        return None

    def select_window_interactive(self):
        try:
            r = subprocess.run(["xdotool", "selectwindow"],
                               capture_output=True, text=True, check=True, timeout=30)
            wid = r.stdout.strip()
            return wid if wid else None
        except Exception:
            return None


def main():
    curses.wrapper(lambda stdscr: DunkingBirdTui(stdscr).run())


if __name__ == "__main__":
    main()
