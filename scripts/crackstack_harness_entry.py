from __future__ import annotations

import sys

from harness.cli import main


if __name__ == "__main__":
    if len(sys.argv) == 1:
        from harness.gui import main as gui_main

        raise SystemExit(gui_main())
    raise SystemExit(main())
