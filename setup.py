#!/usr/bin/env python3
"""
Dunking Bird Setup and Diagnostic Tool
Handles installation, configuration, and troubleshooting
"""

import subprocess
import os
import stat
import time
import sys
import argparse
import getpass
from pathlib import Path

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

class DunkingBirdSetup:
    def __init__(self):
        self.script_dir = Path(__file__).parent.absolute()
        self.issues = []
        self.warnings = []

    def log(self, message, color=Colors.NC):
        print(f"{color}{message}{Colors.NC}")

    def success(self, message):
        self.log(f"✅ {message}", Colors.GREEN)

    def error(self, message):
        self.log(f"❌ {message}", Colors.RED)

    def warning(self, message):
        self.log(f"⚠️ {message}", Colors.YELLOW)

    def info(self, message):
        self.log(f"ℹ️ {message}", Colors.BLUE)

    def check_kdotool_available(self):
        """Check if kdotool command is available"""
        try:
            result = subprocess.run(['kdotool', '--version'],
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        except subprocess.CalledProcessError:
            return True  # Command exists but version flag may not work

    def check_ydotool_available(self):
        """Check if ydotool command is available using a better method"""
        try:
            # Use 'help' command - ydotool outputs to stderr but that's normal
            result = subprocess.run(['ydotool', 'help'],
                                  capture_output=True, text=True, timeout=5)
            # ydotool help may return non-zero but still show help text in stderr
            if 'Usage:' in result.stderr or 'Usage:' in result.stdout:
                return True
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        except subprocess.CalledProcessError:
            # ydotool may return error code but still be functional
            return True

    def check_ydotool_daemon(self):
        """Check ydotool daemon status and socket"""
        # Check if daemon process is running
        try:
            result = subprocess.run(['pgrep', '-f', 'ydotoold'],
                                  capture_output=True, text=True)
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
            socket_stat = os.stat(socket_path)
            if not (socket_stat.st_mode & stat.S_IWUSR or
                   socket_stat.st_mode & stat.S_IWGRP or
                   socket_stat.st_mode & stat.S_IWOTH):
                return "permission_denied"

            # Try a simple test
            result = subprocess.run(['timeout', '2', 'ydotool', 'type', '--delay', '100', ''],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode != 0:
                return "permission_denied"

        except (OSError, subprocess.CalledProcessError):
            return "permission_denied"

        return "ok"

    def check_user_permissions(self):
        """Check if user has appropriate permissions"""
        try:
            result = subprocess.run(['groups'], capture_output=True, text=True, check=True)
            groups = result.stdout.strip()
            return 'input' in groups.split()
        except subprocess.CalledProcessError:
            return False

    def check_python_dependencies(self):
        """Check Python dependencies"""
        try:
            import tkinter
            import threading
            import pynput
            return True
        except ImportError as e:
            return False

    def perform_comprehensive_check(self):
        """Perform comprehensive system check"""
        self.info("Performing comprehensive system check...")
        self.issues = []
        self.warnings = []

        # Check ydotool availability
        if not self.check_ydotool_available():
            self.issues.append("ydotool command not found or not working")
        else:
            self.success("ydotool command available")

        # Check kdotool availability (for KDE Wayland)
        if not self.check_kdotool_available():
            self.issues.append("kdotool command not found or not working")
        else:
            self.success("kdotool command available")

        # Check ydotool daemon
        daemon_status = self.check_ydotool_daemon()
        if daemon_status == "not_running":
            self.issues.append("ydotool daemon not running")
        elif daemon_status == "no_socket":
            self.issues.append("ydotool socket not found")
        elif daemon_status == "permission_denied":
            self.warnings.append("ydotool socket permission issues")
        else:
            self.success("ydotool daemon running and accessible")

        # Check user permissions
        if not self.check_user_permissions():
            self.warnings.append("User may not be in input group")
        else:
            self.success("User has input group permissions")

        # Check Python dependencies
        if not self.check_python_dependencies():
            self.issues.append("Python dependencies missing")
        else:
            self.success("Python dependencies available")

        # Check display server
        if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            self.warnings.append("No display server detected")
        else:
            self.success("Display server available")

        return len(self.issues) == 0

    def attempt_fixes(self, auto_yes=False):
        """Attempt to automatically fix issues"""
        if not self.issues and not self.warnings:
            self.success("No issues to fix!")
            return True

        self.info("Attempting to fix detected issues...")
        fix_results = []
        needs_restart = False

        # Install missing packages
        if any("ydotool command not found" in issue for issue in self.issues):
            self.info("Installing ydotool...")
            try:
                subprocess.run(['sudo', 'apt', 'update'], check=False)
                subprocess.run(['sudo', 'apt', 'install', '-y', 'ydotool', 'ydotoold'],
                              check=False)
                fix_results.append("✅ Installed ydotool packages")
            except Exception as e:
                fix_results.append(f"❌ Failed to install ydotool: {e}")

        # Install kdotool if missing (for KDE Wayland)
        if any("kdotool command not found" in issue for issue in self.issues):
            self.info("Installing kdotool...")
            try:
                subprocess.run(['sudo', 'apt', 'update'], check=False)
                subprocess.run(['sudo', 'apt', 'install', '-y', 'kdotool'],
                              check=False)
                fix_results.append("✅ Installed kdotool package")
            except Exception as e:
                fix_results.append(f"❌ Failed to install kdotool: {e}")

        # Start ydotool daemon
        if any("daemon not running" in issue for issue in self.issues):
            self.info("Starting ydotool daemon...")
            try:
                # Kill any existing daemon first
                subprocess.run(['sudo', 'pkill', 'ydotoold'],
                              capture_output=True, check=False)
                time.sleep(1)

                # Start daemon
                subprocess.run(['sudo', 'ydotoold'],
                              capture_output=True, check=False)
                time.sleep(2)

                if self.check_ydotool_daemon() != "not_running":
                    fix_results.append("✅ Started ydotool daemon")
                else:
                    fix_results.append("❌ Failed to start ydotool daemon")
            except Exception as e:
                fix_results.append(f"❌ Error starting daemon: {e}")

        # Fix socket permissions
        if any("permission" in issue or "permission" in warning
               for issue in self.issues for warning in self.warnings):
            self.info("Fixing socket permissions...")
            try:
                subprocess.run(['sudo', 'chmod', '666', '/tmp/.ydotool_socket'],
                              check=False)
                fix_results.append("✅ Fixed socket permissions")
            except Exception as e:
                fix_results.append(f"❌ Error fixing permissions: {e}")

        # Add user to input group
        if any("input group" in warning for warning in self.warnings):
            self.info("Adding user to input group...")
            try:
                username = getpass.getuser()
                subprocess.run(['sudo', 'usermod', '-a', '-G', 'input', username],
                              check=False)
                fix_results.append(f"✅ Added {username} to input group")
                needs_restart = True
            except Exception as e:
                fix_results.append(f"❌ Error adding to input group: {e}")

        # Install Python dependencies
        if any("Python dependencies" in issue for issue in self.issues):
            self.info("Installing Python dependencies...")
            try:
                subprocess.run(['sudo', 'apt', 'install', '-y',
                              'python3-tk', 'python3-pip'], check=False)
                subprocess.run(['pip3', 'install', '--user', 'pynput'],
                              check=False)
                fix_results.append("✅ Installed Python dependencies")
            except Exception as e:
                fix_results.append(f"❌ Failed to install Python deps: {e}")

        # Show results
        print("\nFix Results:")
        for result in fix_results:
            print(f"  {result}")

        if needs_restart:
            self.warning("You may need to log out and back in for group changes to take effect")

        return True

    def show_manual_instructions(self):
        """Show manual fix instructions"""
        print(f"\n{Colors.CYAN}Manual Fix Instructions:{Colors.NC}")
        print("=" * 50)

        if any("ydotool command not found" in issue for issue in self.issues):
            print("1. Install ydotool:")
            print("   sudo apt update")
            print("   sudo apt install ydotool ydotoold")
            print()

        if any("daemon not running" in issue for issue in self.issues):
            print("2. Start ydotool daemon:")
            print("   sudo ydotoold &")
            print()

        if any("socket" in issue for issue in self.issues):
            print("3. Fix socket permissions:")
            print("   sudo chmod 666 /tmp/.ydotool_socket")
            print()

        if any("input group" in warning for warning in self.warnings):
            print("4. Add user to input group:")
            print(f"   sudo usermod -a -G input {getpass.getuser()}")
            print("   (logout/login required)")
            print()

        if any("Python dependencies" in issue for issue in self.issues):
            print("5. Install Python dependencies:")
            print("   sudo apt install python3-tk python3-pip")
            print("   pip3 install --user pynput")
            print()

        print("6. Or run the install script:")
        print("   ./install.sh")

    def interactive_setup(self):
        """Interactive setup mode"""
        print(f"{Colors.CYAN}🦆 Dunking Bird Setup Tool{Colors.NC}")
        print("=" * 40)

        # Perform check
        all_good = self.perform_comprehensive_check()

        if all_good:
            self.success("All systems ready! No setup needed.")
            return True

        # Show issues
        if self.issues:
            print(f"\n{Colors.RED}Critical Issues:{Colors.NC}")
            for issue in self.issues:
                print(f"  ❌ {issue}")

        if self.warnings:
            print(f"\n{Colors.YELLOW}Warnings:{Colors.NC}")
            for warning in self.warnings:
                print(f"  ⚠️ {warning}")

        print()
        choice = input("Would you like to attempt automatic fixes? (y/n): ").lower()

        if choice in ['y', 'yes']:
            self.attempt_fixes()
            # Re-check after fixes
            print(f"\n{Colors.BLUE}Re-checking after fixes...{Colors.NC}")
            self.perform_comprehensive_check()
        else:
            self.show_manual_instructions()

        return len(self.issues) == 0

def main():
    parser = argparse.ArgumentParser(description="Dunking Bird Setup and Diagnostic Tool")
    parser.add_argument('--check', action='store_true',
                       help='Check system status only')
    parser.add_argument('--fix', action='store_true',
                       help='Attempt to fix issues automatically')
    parser.add_argument('--manual', action='store_true',
                       help='Show manual fix instructions')
    parser.add_argument('--quiet', action='store_true',
                       help='Quiet mode - minimal output')

    args = parser.parse_args()
    setup = DunkingBirdSetup()

    if args.check:
        all_good = setup.perform_comprehensive_check()
        if not args.quiet:
            if all_good:
                setup.success("All systems ready!")
            else:
                setup.error("Issues detected. Run with --fix or --manual for help.")
        sys.exit(0 if all_good else 1)

    elif args.fix:
        setup.perform_comprehensive_check()
        setup.attempt_fixes(auto_yes=True)
        # Re-check after fixes
        all_good = setup.perform_comprehensive_check()
        sys.exit(0 if all_good else 1)

    elif args.manual:
        setup.perform_comprehensive_check()
        setup.show_manual_instructions()

    else:
        # Interactive mode
        setup.interactive_setup()

if __name__ == "__main__":
    main()