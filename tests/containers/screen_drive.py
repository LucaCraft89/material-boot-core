"""Drives the installer screen of /bundle/install.sh on a real pty (keys in, screens out), as a person would: untick nothing, choose the list style, switch the
countdown bar off, type a timeout of 7 seconds, confirm. Prints 'SCREEN OK' when the install finished; exits 1 with what it saw otherwise.   usage: screen_drive.py"""

import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time

ROWS, COLS = 40, 120
DOWN, ENTER = "\x1bOB", "\r"
m, s = pty.openpty()
fcntl.ioctl(s, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
env = dict(
    os.environ, TERM="xterm-256color", LINES=str(ROWS), COLUMNS=str(COLS), MATERIAL_BOOT_TUI_REPAINT="1"
)  # a full repaint each frame: curses would send only what changed
proc = subprocess.Popen(["sh", "/bundle/install.sh"], stdin=s, stdout=s, stderr=s, env=env, close_fds=True)
os.close(s)
seen = b""
pos = 0


def pump(t):
    global seen
    end = time.time() + t
    while time.time() < end:
        r, _, _ = select.select([m], [], [], 0.2)
        if r:
            try:
                d = os.read(m, 65536)
            except OSError:
                return False
            if not d:
                return False
            seen += d
    return True


def wait(text, timeout=900):
    """Wait for `text` to appear in what was printed AFTER the last thing we waited for."""
    global pos
    end = time.time() + timeout
    while time.time() < end:
        i = seen.find(text.encode(), pos)
        if i >= 0:
            pos = i + len(text)
            time.sleep(0.3)
            return
        if not pump(0.5) and seen.find(text.encode(), pos) < 0:
            break
    print(f"never saw {text!r}; the end of the output:\n" + seen.decode(errors="replace")[-2500:])
    proc.kill()
    sys.exit(1)


def send(keys):
    os.write(m, keys.encode())
    time.sleep(0.3)


wait("What to install")
send(ENTER)  # Material GRUB is ticked (the default part)
wait("Full screen with a left rail")
send(DOWN + DOWN + ENTER)  # list
wait("Colour scheme")
send(ENTER)  # dark
wait("Every entry its own colour")
send(ENTER)  # multi
wait("Cookie and firmware logo")
send(ENTER)
wait("Key hints")
send(ENTER)
wait("Screen resolution")
send(ENTER)  # detected automatically
wait("Raw entry name line")
send(ENTER)
wait("Countdown bar")
send(DOWN + ENTER)  # No
wait("Timeout in seconds")
send(ENTER)  # start typing
send("7")
send(ENTER)
wait("Graphical editor")
send(ENTER)  # No
wait("Ready to install")
send(ENTER)  # Install
wait("Installed: core, grub")
pump(2)
proc.wait(timeout=60)
print("SCREEN OK" if proc.returncode == 0 else f"exit status {proc.returncode}")
sys.exit(proc.returncode)
