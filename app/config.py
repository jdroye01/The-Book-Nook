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


def _shared_data_root():
    """
    The machine-wide, all-users data location -- so whoever logs into this
    computer (any OS account) sees the same catalog and checkouts, rather
    than each login getting its own empty library. This is the preferred
    location; _per_user_data_root() below is only a fallback for machines
    where this isn't writable (e.g. a locked-down account without admin
    rights).
    """
    if sys.platform == "darwin":
        return os.path.join("/Library/Application Support", APP_TITLE)
    elif sys.platform.startswith("win"):
        base = os.environ.get("ProgramData") or "C:\\ProgramData"
        return os.path.join(base, APP_TITLE)
    else:
        return os.path.join("/var/lib", APP_TITLE)


def _per_user_data_root():
    """The OS-standard per-user data location -- used as a fallback when
    the shared location can't be written to, and as a migration source
    for anyone who used an earlier per-user-only version of this app."""
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_TITLE)
    elif sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_TITLE)
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        return os.path.join(base, APP_TITLE)


def _can_write(directory):
    """Actually verifies write access, not just that makedirs didn't
    raise -- an existing directory owned by someone else can pass
    makedirs(exist_ok=True) but still refuse real writes."""
    try:
        os.makedirs(directory, exist_ok=True)
        probe = os.path.join(directory, ".write_test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def _resolve_data_root():
    """Prefer the shared, all-users location; fall back to a personal one
    if that's not writable on this machine. Returns (path, is_shared)."""
    shared = _shared_data_root()
    if _can_write(shared):
        return shared, True
    per_user = _per_user_data_root()
    os.makedirs(per_user, exist_ok=True)
    return per_user, False


DATA_ROOT, USING_SHARED_STORAGE = _resolve_data_root()
DATA_DIR = os.path.join(DATA_ROOT, "data")
EXPORTS_DIR = os.path.join(DATA_ROOT, "exports")
DB_PATH = os.path.join(DATA_DIR, "library.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)


def _migrate_if_needed():
    """
    One-time migration so upgrading never silently loses a catalog.
    Checks, in order: (1) the old "data" folder that used to sit right
    next to main.py, and (2) this same account's previous per-user data
    location (from before storage became shared). Only copies in if the
    resolved location doesn't already have a database.

    Note: this can only carry over the current OS account's own old data.
    If several people on this machine each already had their own separate
    per-user copy from before, only whichever one launches the updated app
    first gets auto-migrated -- the others' old data stays put at its old
    per-user location rather than being silently merged or discarded; see
    the README for how to consolidate those manually if that applies here.
    """
    new_db = os.path.join(DATA_DIR, "library.db")
    if os.path.exists(new_db):
        return

    candidates = [os.path.join(BASE_DIR, "data")]
    per_user = _per_user_data_root()
    if os.path.join(per_user, "data") not in candidates:
        candidates.append(os.path.join(per_user, "data"))

    for legacy_data_dir in candidates:
        legacy_db = os.path.join(legacy_data_dir, "library.db")
        if os.path.exists(legacy_db):
            for fname in ("library.db", "settings.json"):
                src = os.path.join(legacy_data_dir, fname)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(DATA_DIR, fname))
            return


_migrate_if_needed()


def widen_shared_permissions():
    """
    On POSIX systems (macOS/Linux), a directory or file's permissions are
    set from whichever user's process created it, combined with that
    process's umask -- so even after successfully creating the shared
    folder, it could easily end up unwritable by every *other* account on
    the machine, quietly defeating the whole point of shared storage.
    Called here at startup (after migration) and again by LibraryDB right
    after it creates/opens the database file -- the file doesn't exist yet
    at the point this module first runs on a fresh install, so a single
    early call isn't enough to catch it. Cheap and idempotent either way.
    Windows' ProgramData already grants the Users group write access by
    default in typical configurations, so this step is skipped there.
    """
    if not USING_SHARED_STORAGE or sys.platform.startswith("win"):
        return
    for directory in (DATA_ROOT, DATA_DIR, EXPORTS_DIR):
        try:
            os.chmod(directory, 0o777)
        except OSError:
            pass
    for fname in os.listdir(DATA_DIR):
        try:
            os.chmod(os.path.join(DATA_DIR, fname), 0o666)
        except OSError:
            pass


widen_shared_permissions()

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
