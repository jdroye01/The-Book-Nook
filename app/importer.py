"""
Bulk book import from CSV.

Designed to be forgiving about column names so a librarian can import an
export from a spreadsheet, another catalog system, or a hand-typed CSV
without needing exact headers.
"""
import csv

# Canonical field -> list of header names we'll recognize (case-insensitive)
FIELD_ALIASES = {
    "title": ["title", "book title", "name"],
    "author": ["author", "authors", "writer"],
    "genre": ["genre", "genres", "category", "categories", "subject"],
    "isbn": ["isbn", "isbn13", "isbn-13", "isbn10", "isbn-10"],
    "publisher": ["publisher", "publishers"],
    "pub_year": ["pub_year", "year", "publication year", "published", "publish date"],
    "shelf_location": ["shelf_location", "shelf", "location", "call number"],
    "copies_total": ["copies_total", "copies", "quantity", "qty"],
    "notes": ["notes", "note", "comment", "comments"],
    "barcode": ["barcode", "barcode id", "code"],
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


def preview_rows(csv_path, limit=5):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for i, row in enumerate(reader):
            if i >= limit:
                break
            rows.append(row)
    return rows


def count_rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return sum(1 for _ in reader)


def import_csv(db, csv_path, column_mapping, progress_callback=None):
    """
    column_mapping: dict of canonical_field -> csv_header (or None/"" to skip).
    Returns (success_count, error_list) where error_list is [(row_num, message)].
    """
    errors = []
    success = 0

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

            title = get("title")
            author = get("author")
            if not title or not author:
                raise ValueError("missing title or author")

            copies_raw = get("copies_total", "1") or "1"
            try:
                copies_total = max(1, int(float(copies_raw)))
            except ValueError:
                copies_total = 1

            barcode = get("barcode") or None
            if barcode and db.barcode_exists(barcode):
                barcode = None  # avoid collision; auto-generate instead

            db.add_book(
                title=title,
                author=author,
                genre=get("genre"),
                isbn=get("isbn"),
                publisher=get("publisher"),
                pub_year=get("pub_year"),
                shelf_location=get("shelf_location"),
                copies_total=copies_total,
                notes=get("notes"),
                barcode=barcode,
            )
            success += 1
        except Exception as e:
            errors.append((i + 1, str(e)))  # +1 to account for header row
        if progress_callback:
            progress_callback(i, total)

    return success, errors
