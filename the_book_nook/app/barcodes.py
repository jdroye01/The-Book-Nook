"""
Barcode generation.

Today: prints barcode label sheets on a regular office printer + adhesive
label paper (e.g. Avery 5160), or single barcode images you can view/print.

Later, once a dedicated barcode label printer is bought: the same barcode
values (book['barcode']) are what you'd feed to that printer's own software,
or you can keep using generate_label_sheet_pdf() with LABEL_SHEET in
config.py adjusted to that printer's label size.

Scanning requires no code changes at all: USB/Bluetooth barcode scanners act
as keyboards, typing the barcode digits followed by Enter. Any text entry
box in this app (search boxes, the checkout barcode field) already accepts
scanner input as-is.
"""
import io
import os
import barcode as barcode_lib
from barcode.writer import ImageWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as pdf_canvas
from PIL import Image

from app import config

# Every field a label can show, in the fixed order they're stacked when
# selected. "barcode" is the scannable code image (with its number printed
# beneath it by the barcode library itself) -- everything else is plain text
# drawn below it.
LABEL_FIELD_ORDER = ["barcode", "title", "author", "genre", "shelf_location", "isbn"]

LABEL_FIELD_INFO = {
    "barcode": {"label": "Barcode", "text_fn": None},
    "title": {"label": "Title", "text_fn": lambda b: b.get("title") or ""},
    "author": {"label": "Author", "text_fn": lambda b: f"by {b['author']}" if b.get("author") else ""},
    "genre": {"label": "Genre", "text_fn": lambda b: b.get("genre") or ""},
    "shelf_location": {"label": "Shelf Location", "text_fn": lambda b: b.get("shelf_location") or ""},
    "isbn": {"label": "ISBN", "text_fn": lambda b: f"ISBN {b['isbn']}" if b.get("isbn") else ""},
}

DEFAULT_LABEL_FIELDS = ["barcode", "title"]


def generate_barcode_image(value, out_path=None):
    """Generate a Code128 barcode PNG for `value`. Returns the PIL Image."""
    writer = ImageWriter()
    writer.set_options({
        "module_height": 10.0,
        "font_size": 9,
        "text_distance": 3.0,
        "quiet_zone": 2.0,
        "write_text": True,
    })
    code = barcode_lib.get(config.BARCODE_SYMBOLOGY, value, writer=writer)
    buf = io.BytesIO()
    code.write(buf)
    buf.seek(0)
    img = Image.open(buf).convert("RGB")
    if out_path:
        img.save(out_path)
    return img


def generate_barcode_bytes(value):
    """Return PNG bytes for a barcode, for showing in the Tk GUI."""
    buf = io.BytesIO()
    img = generate_barcode_image(value)
    img.save(buf, format="PNG")
    return buf.getvalue()


def export_barcode_images(books, out_dir):
    """Save one PNG per book (named by barcode) into out_dir. Returns list of paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for b in books:
        path = os.path.join(out_dir, f"{b['barcode']}.png")
        generate_barcode_image(b["barcode"], out_path=path)
        paths.append(path)
    return paths


def generate_label_sheet_pdf(books, out_path, fields=None, label_sheet=None):
    """
    Lay out one label per book on standard label sheets (default: Avery
    5160, 30/sheet) and save as a PDF ready to print.

    fields: ordered list from LABEL_FIELD_ORDER controlling what prints on
    each label (e.g. ["barcode", "title", "shelf_location"]). Defaults to
    DEFAULT_LABEL_FIELDS (barcode + title) if not given.

    label_sheet: a dict shaped like config.LABEL_SHEET to use a different
    page/label layout -- e.g. one detected from an uploaded Avery template
    or chosen from a preset -- without touching config.py.
    """
    if fields is None:
        fields = DEFAULT_LABEL_FIELDS
    fields = [f for f in fields if f in LABEL_FIELD_INFO]
    include_barcode = "barcode" in fields
    text_fields = [f for f in fields if f != "barcode"]

    cfg = label_sheet or config.LABEL_SHEET
    page_w = cfg["page_width_in"] * inch
    page_h = cfg["page_height_in"] * inch
    label_w = cfg["label_width_in"] * inch
    label_h = cfg["label_height_in"] * inch
    margin_left = cfg["margin_left_in"] * inch
    margin_top = cfg["margin_top_in"] * inch
    col_gap = cfg["col_gap_in"] * inch
    row_gap = cfg["row_gap_in"] * inch
    cols, rows = cfg["cols"], cfg["rows"]
    per_page = cols * rows

    # Rough chars-per-line budget so text doesn't overrun the label edges.
    max_chars = max(10, int((label_w / inch) * 12))

    c = pdf_canvas.Canvas(out_path, pagesize=(page_w, page_h))

    for idx, book in enumerate(books):
        pos_in_page = idx % per_page
        if idx > 0 and pos_in_page == 0:
            c.showPage()
        col = pos_in_page % cols
        row = pos_in_page // cols

        x = margin_left + col * (label_w + col_gap)
        y = page_h - margin_top - (row + 1) * label_h - row * row_gap

        pad = 4
        line_height = 9
        text_block_h = len(text_fields) * line_height

        cursor_y = y + label_h - pad  # drawing downward from the top of the label

        if include_barcode:
            img = generate_barcode_image(book["barcode"])
            img_path = os.path.join(config.EXPORTS_DIR, f"_tmp_{book['barcode']}.png")
            img.save(img_path)
            aspect = img.width / img.height
            img_h = max(14, label_h - 2 * pad - text_block_h)
            img_w = min(label_w - 2 * pad, img_h * aspect)
            img_x = x + (label_w - img_w) / 2
            img_y = cursor_y - img_h
            c.drawImage(img_path, img_x, img_y, width=img_w, height=img_h,
                        preserveAspectRatio=True, anchor='c')
            os.remove(img_path)
            cursor_y = img_y
        elif text_fields:
            # No barcode -- center the text block vertically in the label.
            cursor_y = y + (label_h + text_block_h) / 2

        for field in text_fields:
            text = LABEL_FIELD_INFO[field]["text_fn"](book)
            if not text:
                continue
            if len(text) > max_chars:
                text = text[: max_chars - 3] + "..."
            font_name = "Helvetica-Bold" if field == "title" else "Helvetica"
            font_size = 7 if field == "title" else 6
            cursor_y -= line_height
            c.setFont(font_name, font_size)
            c.drawCentredString(x + label_w / 2, cursor_y + 1, text)

    c.save()
    return out_path
