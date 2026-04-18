# ============================================================
# src/utils/pid.py — PID File Management
# ============================================================
# Prevents multiple bot instances from running simultaneously.
# Creates a .pid file on startup and cleans it up on exit.
# ============================================================

import os
import sys
import signal
import atexit

PID_FILE = "bot.pid"


def is_process_running(pid: int) -> bool:
    """Check whether a process with the given PID is still alive."""
    try:
        if os.name == "nt":
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def remove_pid_file() -> None:
    """Delete the PID file if it exists."""
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass


def create_pid_file() -> None:
    """
    Write the current PID to bot.pid.
    If a previous PID file exists and that process is still alive,
    exit immediately to avoid a duplicate bot instance.
    """
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                existing_pid = int(f.read().strip() or 0)
        except Exception:
            existing_pid = None

        if existing_pid and is_process_running(existing_pid):
            if existing_pid == os.getpid():
                # The PID file points to this process; continue normally.
                pass
            else:
                print(f"[PID] Bot already running (PID {existing_pid}). Exiting.")
                sys.exit(1)
        else:
            remove_pid_file()

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Ensure the file is cleaned up no matter how the process exits
    atexit.register(remove_pid_file)

    try:
        signal.signal(signal.SIGINT,  lambda *_: sys.exit(0))
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    except Exception:
        pass
