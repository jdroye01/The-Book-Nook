#!/bin/bash
# Double-click this file in Finder to launch The Book Nook.
# (First time only: right-click -> Open, since it's not from an
# identified developer -- macOS will ask for confirmation once.)

# Move to this script's own folder, regardless of where it was double-clicked from.
cd "$(dirname "$0")"

# Make sure dependencies are installed. This is a no-op (instant) once
# they're already present, so it's safe to leave in for every launch.
# The fallback with --break-system-packages covers Python installs (e.g.
# Homebrew) that block plain pip installs by default.
python3 -m pip install -r requirements.txt --quiet --disable-pip-version-check 2>/dev/null \
    || python3 -m pip install -r requirements.txt --quiet --disable-pip-version-check --break-system-packages 2>/dev/null

python3 main.py

# Keep the window open if something went wrong, so the error is readable.
if [ $? -ne 0 ]; then
    echo ""
    echo "The Book Nook closed with an error (see above). Press Enter to close this window."
    read
fi
