"""
The Book Nook - Windows no-console launcher.

Double-click this file in File Explorer. Windows normally associates .pyw
files with pythonw.exe (installed automatically alongside Python), which
runs this with no visible console window -- the closest Windows equivalent
to a native double-click app, no extra setup required.

Dependencies must already be installed once (see README) -- this file
skips the automatic pip-install step that "Launch The Book Nook.bat"
does, since a no-console window can't show install progress or errors.
If something goes wrong here with no visible message, run
"Launch The Book Nook.bat" once instead to see what happened.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.gui.main_window import run

if __name__ == "__main__":
    run()
