"""
Central configuration for the library system.
Edit these values to tune behavior without digging through the codebase.
"""
import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_TITLE = "The Book Nook"
APP_MOTTO = "Where every book finds its reader"


def _default_data_root():
    """
    Where the database, settings, and exports live -- the OS-standard
    per-user data location, not a folder next to the app itself. This
    matters for a real installed .app: /Applications isn't meant to be
    writable, and reinstalling/updating the app shouldn't touch user data.
    """
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_TITLE)
    elif sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_TITLE)
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        return os.path.join(base, APP_TITLE)


DATA_ROOT = _default_data_root()
DATA_DIR = os.path.join(DATA_ROOT, "data")
EXPORTS_DIR = os.path.join(DATA_ROOT, "exports")
DB_PATH = os.path.join(DATA_DIR, "library.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

# One-time migration: earlier versions stored data in a "data" folder right
# next to main.py. If that exists and nothing has been created yet at the
# new location, copy it over automatically so existing catalogs aren't lost.
_legacy_data_dir = os.path.join(BASE_DIR, "data")
_legacy_db = os.path.join(_legacy_data_dir, "library.db")
_new_db = os.path.join(DATA_DIR, "library.db")
if os.path.exists(_legacy_db) and not os.path.exists(_new_db):
    for _fname in ("library.db", "settings.json"):
        _src = os.path.join(_legacy_data_dir, _fname)
        if os.path.exists(_src):
            shutil.copy2(_src, os.path.join(DATA_DIR, _fname))

# --- Circulation rules ---
DEFAULT_LOAN_DAYS = 14          # default checkout period
OVERDUE_GRACE_DAYS = 0          # days after due date before flagged overdue

# --- Barcode settings ---
BARCODE_SYMBOLOGY = "code128"   # supports letters+numbers, works with any cheap scanner
BARCODE_PREFIX = "LIB"          # internal barcodes look like LIB000001

# Label sheet layout (used by the batch label-sheet PDF generator).
# Defaults are for Avery 5160-style address labels (30/sheet, 3 cols x 10 rows)
# since that's the easiest to buy at any office store before a dedicated
# barcode label printer is purchased. Change these once you know your printer's
# label stock, or use "single" mode to print one barcode per page.
LABEL_SHEET = {
    "page_width_in": 8.5,
    "page_height_in": 11,
    "cols": 3,
    "rows": 10,
    "label_width_in": 2.63,
    "label_height_in": 1.0,
    "margin_left_in": 0.19,
    "margin_top_in": 0.5,
    "col_gap_in": 0.12,
    "row_gap_in": 0.0,
}

# --- Appearance ---
THEME = "flatly"   # ttkbootstrap theme name; try "journal", "cosmo", "darkly" etc.
