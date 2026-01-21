#!/usr/bin/env python3
"""Install the research service as a system daemon."""

import argparse
import os
import pwd
import subprocess
import sys
from pathlib import Path


LAUNCHD_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ai-equity-research.scheduler</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{scheduler_path}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{working_dir}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
        <key>PYTHONPATH</key>
        <string>{working_dir}</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>{log_dir}/ai-research-stdout.log</string>

    <key>StandardErrorPath</key>
    <string>{log_dir}/ai-research-stderr.log</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</dict>
</plist>
"""


def get_python_path() -> str:
    """Get path to Python executable."""
    return sys.executable


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent.absolute()


def install_launchd(user_only: bool = True) -> bool:
    """Install launchd plist for macOS.

    Args:
        user_only: Install for current user only

    Returns:
        True if successful
    """
    project_root = get_project_root()
    python_path = get_python_path()
    scheduler_path = project_root / "scheduler" / "runner.py"

    if user_only:
        plist_dir = Path.home() / "Library" / "LaunchAgents"
        log_dir = Path.home() / "Library" / "Logs" / "ai-equity-research"
    else:
        plist_dir = Path("/Library/LaunchDaemons")
        log_dir = Path("/var/log/ai-equity-research")

    plist_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    plist_content = LAUNCHD_PLIST.format(
        python_path=python_path,
        scheduler_path=scheduler_path,
        working_dir=project_root,
        log_dir=log_dir,
    )

    plist_path = plist_dir / "com.ai-equity-research.scheduler.plist"

    try:
        with open(plist_path, "w") as f:
            f.write(plist_content)

        print(f"✓ Created plist: {plist_path}")

        # Load the service
        subprocess.run(["launchctl", "load", str(plist_path)], check=True)
        print("✓ Loaded service")

        return True

    except Exception as e:
        print(f"✗ Failed to install service: {e}")
        return False


def uninstall_launchd(user_only: bool = True) -> bool:
    """Uninstall launchd plist.

    Args:
        user_only: Uninstall from current user only

    Returns:
        True if successful
    """
    if user_only:
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.ai-equity-research.scheduler.plist"
    else:
        plist_path = Path("/Library/LaunchDaemons/com.ai-equity-research.scheduler.plist")

    if not plist_path.exists():
        print("Service not installed")
        return True

    try:
        # Unload the service
        subprocess.run(["launchctl", "unload", str(plist_path)], check=True)
        print("✓ Unloaded service")

        # Remove plist
        plist_path.unlink()
        print(f"✓ Removed plist: {plist_path}")

        return True

    except Exception as e:
        print(f"✗ Failed to uninstall service: {e}")
        return False


def check_status() -> None:
    """Check service status."""
    result = subprocess.run(
        ["launchctl", "list", "com.ai-equity-research.scheduler"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("Service is loaded")
        print(result.stdout)
    else:
        print("Service is not loaded")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Install/uninstall AI Equity Research as a service"
    )
    parser.add_argument(
        "action",
        choices=["install", "uninstall", "status"],
        help="Action to perform",
    )
    parser.add_argument(
        "--system",
        action="store_true",
        help="Install as system service (requires root)",
    )

    args = parser.parse_args()

    if args.system and os.geteuid() != 0:
        print("System-wide installation requires root. Please run with sudo.")
        sys.exit(1)

    if args.action == "install":
        success = install_launchd(user_only=not args.system)
        sys.exit(0 if success else 1)

    elif args.action == "uninstall":
        success = uninstall_launchd(user_only=not args.system)
        sys.exit(0 if success else 1)

    elif args.action == "status":
        check_status()


if __name__ == "__main__":
    main()
