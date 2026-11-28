"""`material-boot ui`: the editor in your browser. stdlib only."""

import sys

from .. import help


def main(argv):
    port, idle, browser = 0, 120, True
    a = list(argv)
    try:
        while a:
            w = a.pop(0)
            if w in ("-h", "--help"):
                print(help.command_text("ui"))
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
        msg = str(e) or "a value is missing"
        print(f"material-boot ui: {msg}\n\n{help.command_text('ui')}", file=sys.stderr)
        return 2
    from . import server

    return server.serve(port=port, idle=idle, open_browser=browser)
