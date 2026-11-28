"""Drives the installer screen of /bundle/install.sh on a machine that is SET UP ALREADY (an update), on a real pty, as a person would: the screen says what is
installed and what was left over from an older version, asks "keep my current look and settings, or edit them now?", and installs what changed.
usage: screen_update_drive.py keep | edit      keep: take the default (keep); edit: choose to edit, then accept every prefilled answer.
Prints 'SCREEN UPDATE OK' when the install finished; exits 1 with what it saw otherwise."""

import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time

MODE = sys.argv[1] if len(sys.argv) > 1 else "keep"
ROWS, COLS = 40, 120
DOWN, ENTER = "\x1bOB", "\r"
m, s = pty.openpty()
fcntl.ioctl(s, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
env = dict(os.environ, TERM="xterm-256color", LINES=str(ROWS), COLUMNS=str(COLS), MATERIAL_BOOT_TUI_REPAINT="1")
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


def fail(msg):
    print(msg + "; the end of the output:\n" + seen.decode(errors="replace")[-3000:], flush=True)
    proc.kill()
    sys.exit(1)


def wait(text, timeout=240):
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
    fail(f"never saw {text!r}")


def send(keys):
    os.write(m, keys.encode())
    time.sleep(0.3)


wait("What to install", 120)
pump(1.5)
for text in ("On this system", "Left from an older version", "remove /usr/local/bin/material-grub"):
    if text.encode() not in seen:
        fail(f"the first screen does not say {text!r}")
print("the first screen lists what is installed and the leftovers")
send(ENTER)  # the parts: what is installed stays ticked
wait("Your current look and settings", 120)
if MODE == "edit":
    send(DOWN + ENTER)  # Edit them now
    for _ in range(
        40
    ):  # every question starts from the current answer: Enter accepts it (a text question takes two: start typing, accept)
        pump(0.8)
        if b"Ready to install" in seen[pos:]:
            break
        send(ENTER)
    else:
        fail("never reached the summary")
    wait("Ready to install", 60)
else:
    send(ENTER)  # Keep
    wait("Ready to install", 120)
send(ENTER)  # Install
wait("material-boot", 900)
t_end, last, size = time.time() + 900, time.time(), len(seen)
asked = 0
while proc.poll() is None and time.time() < t_end:
    pump(1)
    if (
        b"[Y/n]" in seen[pos:]
    ):  # a part asks something in the middle of its work (Plymouth: may it edit the kernel command line?): the question must be readable
        question = seen[pos:].decode(errors="replace")
        pos = len(seen)
        if "kernel command line" not in question:
            fail("a question appeared that is not the one expected")
        asked += 1
        print("a part asked, in the middle of the install:", question.strip().splitlines()[-1][:100], flush=True)
        send("n\r")  # not now
    if len(seen) != size:
        last, size = time.time(), len(seen)
    elif time.time() - last > 100:  # a step that prints nothing for 100 s is waiting for something: show what it says
        fail("the install is waiting (nothing on the screen for 100 s)")
if proc.poll() is None:
    fail("the install did not finish")
out = seen.decode(errors="replace")
print(f"questions asked during the install: {asked}")
print("SCREEN UPDATE OK" if proc.returncode == 0 else f"exit status {proc.returncode}\n" + out[-2500:])
sys.exit(proc.returncode)
