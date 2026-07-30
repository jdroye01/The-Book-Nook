"""
Central configuration for the library system.
Edit these values to tune behavior without digging through the codebase.
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
DB_PATH = os.path.join(DATA_DIR, "library.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

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
APP_TITLE = "The Book Nook"
APP_MOTTO = "Where every book finds its reader"
