"""
Persistent app settings that are user-editable at runtime (as opposed to
app/config.py, which holds developer-level defaults). Stored as JSON in
data/settings.json. Currently used for email/SMTP configuration, the
due-date reminder schedule, the label sheet layout, and reminder email
wording.
"""
import copy
import json
import os

from app import config
from app.email_utils import DEFAULT_EMAIL_TEMPLATES

SETTINGS_PATH = os.path.join(config.DATA_DIR, "settings.json")

DEFAULTS = {
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_security": "starttls",   # "starttls", "ssl", or "none"
    "smtp_username": "",
    "smtp_password": "",
    "from_email": "",
    "from_name": "Library",
    "reminders_enabled": False,
    # Days relative to the due date a reminder should fire:
    # negative = before due, 0 = on due date, positive = after due (overdue)
    "reminder_offsets": [-3, 0, 3, 7],
    "library_name": "Your Library",
    # Label sheet layout used by the barcode label PDF exporter. Defaults
    # match config.LABEL_SHEET (Avery 5160) until changed via a preset,
    # an uploaded template, or manual entry in the Barcodes tab.
    "label_sheet": dict(config.LABEL_SHEET),
    "label_sheet_name": "Avery 5160 (default)",
    # Which fields print on each label, in this fixed order. "barcode" is
    # the scannable code image itself (with its number printed beneath it).
    "label_fields": ["barcode", "title"],
    # Subject/body wording for each reminder scenario. Starts as a copy of
    # the built-in defaults so the template editor opens pre-filled with
    # real text rather than blank fields; edit any of the three freely.
    "email_templates": copy.deepcopy(DEFAULT_EMAIL_TEMPLATES),
}


class Settings:
    def __init__(self):
        self._data = dict(DEFAULTS)
        self.load()

    def load(self):
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except (json.JSONDecodeError, OSError):
                pass  # fall back to defaults rather than crash on a corrupt file

    def save(self):
        os.makedirs(config.DATA_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def update(self, **kwargs):
        self._data.update(kwargs)

    def as_dict(self):
        return dict(self._data)

    @property
    def smtp_configured(self):
        return bool(self.get("smtp_host") and self.get("from_email"))
