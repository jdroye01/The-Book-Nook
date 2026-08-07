"""
Bulk patron import from CSV: Name + Email/Contact.

Existing patrons (matched by exact name) get their contact info updated
rather than duplicated; new names create a new patron. If more than one
existing patron already shares that exact name, the row is skipped as
ambiguous rather than guessing which one to update -- see
LibraryDB.import_or_update_patron for details.
"""
import csv

from app.importer import preview_rows, count_rows  # generic CSV helpers, reused as-is

FIELD_ALIASES = {
    "name": ["name", "patron name", "full name", "patron"],
    "contact": ["contact", "email", "e-mail", "email address", "phone", "phone number"],
}


def sniff_columns(csv_path):
    """Read the header row and return (headers, auto_mapping dict)."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = next(reader, [])
    headers = [h.strip() for h in headers]

    mapping = {}
    lower_headers = {h.lower(): h for h in headers}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in lower_headers:
                mapping[field] = lower_headers[alias]
                break
    return headers, mapping


def import_csv(db, csv_path, column_mapping, progress_callback=None):
    """
    column_mapping: dict of canonical_field ("name"/"contact") -> csv_header.
    Returns a dict of counts: created, updated, unchanged, skipped_ambiguous,
    and errors (a list of (row_num, message) for rows that couldn't be
    processed at all, e.g. a missing name).
    """
    counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped_ambiguous": 0}
    errors = []

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    for i, row in enumerate(rows, start=1):
        try:
            def get(field, default=""):
                header = column_mapping.get(field)
                if not header:
                    return default
                return (row.get(header) or "").strip()

            name = get("name")
            contact = get("contact")
            if not name:
                raise ValueError("missing name")

            status = db.import_or_update_patron(name, contact)
            counts[status] += 1
        except Exception as e:
            errors.append((i + 1, str(e)))  # +1 to account for header row
        if progress_callback:
            progress_callback(i, total)

    return counts, errors
