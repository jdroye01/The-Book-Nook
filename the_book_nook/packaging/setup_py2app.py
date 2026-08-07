"""
Optional: builds a standalone Library Manager.app using py2app.

This must be run ON A MAC (py2app builds macOS-native app bundles and can't
be cross-built from another OS). It was written and documented here but
could not be built or tested in the environment this project was developed
in, since that environment isn't macOS -- so treat it as a documented
starting point rather than a guaranteed one-shot build. If it gives you
trouble, the Automator method in the README's "Desktop app (macOS)" section
is simpler and doesn't need py2app at all.

Usage (from the project root, in Terminal, on your Mac):
    pip install py2app --break-system-packages
    python3 packaging/setup_py2app.py py2app

The finished app will be in dist/Library Manager.app -- drag that to your
Applications folder or Dock.
"""
from setuptools import setup

APP = ["main.py"]
DATA_FILES = [
    ("sample_data", ["sample_data/sample_books.csv"]),
]
OPTIONS = {
    "argv_emulation": False,
    "packages": ["ttkbootstrap", "barcode", "PIL", "reportlab", "certifi", "app"],
    "includes": ["tkinter"],
    "plist": {
        "CFBundleName": "Library Manager",
        "CFBundleDisplayName": "Library Manager",
        "CFBundleGetInfoString": "Library book management system",
        "CFBundleIdentifier": "com.library.manager",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
    },
}

setup(
    app=APP,
    name="Library Manager",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
