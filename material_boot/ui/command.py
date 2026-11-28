"""`material-boot ui`: the editor in your browser. stdlib only."""

import sys

USAGE = """usage: material-boot ui [--port N] [--no-browser] [--idle SECONDS]

Opens the Material Boot editor in your browser: the look of the boot menu and of the boot splash, in one place, with a live preview. It listens on this
computer only (127.0.0.1), with a one-time key in the address, and stops by itself when the browser tab is closed.

  --port N         listen on port N (default: any free port)
  --no-browser     only print the address
  --idle SECONDS   stop after this long without a browser (default 120; 0 = never)

Saving asks for your password once (polkit); nothing is changed before that."""


def main(argv):
    port, idle, browser = 0, 120, True
    a = list(argv)
    try:
        while a:
            w = a.pop(0)
            if w in ("-h", "--help"):
                print(USAGE)
                return 0
            elif w == "--port":
                port = int(a.pop(0))
            elif w == "--idle":
                idle = int(a.pop(0))
            elif w == "--no-browser":
                browser = False
            else:
                raise ValueError(f"unknown option '{w}'")
    except (ValueError, IndexError) as e:
        print(f"material-boot ui: {e if str(e) else 'a value is missing'}\n\n{USAGE}", file=sys.stderr)
        return 2
    from . import server

    return server.serve(port=port, idle=idle, open_browser=browser)
