import os
import io
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ttkbootstrap as tb

from PIL import Image, ImageTk

from app import barcodes, config, label_template
from app.gui.widgets import BookTable, Card, page_header, labeled_entry


SHEET_GEOMETRY_FIELDS = [
    ("page_width_in", "Page width (in)"),
    ("page_height_in", "Page height (in)"),
    ("cols", "Columns"),
    ("rows", "Rows"),
    ("label_width_in", "Label width (in)"),
    ("label_height_in", "Label height (in)"),
    ("margin_left_in", "Left margin (in)"),
    ("margin_top_in", "Top margin (in)"),
    ("col_gap_in", "Gap between columns (in)"),
    ("row_gap_in", "Gap between rows (in)"),
]


class LabelSheetDialog(tk.Toplevel):
    """
    Lets the librarian set the label sheet layout three ways: pick a
    common Avery product from a list (most reliable), upload an Avery
    template file to auto-detect the layout (.docx is quite reliable
    since Avery's Word templates are literal tables; .pdf is best-effort
    and will say so plainly if it can't confidently read one), or just
    type the numbers in by hand. All three end up editing the same
    fields, so whichever route gets you close, you can still fine-tune
    before saving.
    """

    def __init__(self, parent, settings, status_bar, on_saved):
        super().__init__(parent)
        self.settings = settings
        self.status_bar = status_bar
        self.on_saved = on_saved
        self.title("Label Sheet Settings")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.entries = {}
        self._build()

    def _build(self):
        frm = tb.Frame(self, padding=22)
        frm.pack(fill="both", expand=True)

        tb.Label(frm, text="🏷️  Label Sheet Settings", font=("Helvetica", 14, "bold")).pack(anchor="w", pady=(0, 4))
        tb.Label(frm, text="Used when printing barcode label sheets on a regular printer.",
                 font=("Helvetica", 9), foreground="#868e96").pack(anchor="w", pady=(0, 14))

        # --- Option 1: preset ---
        preset_row = tb.Frame(frm)
        preset_row.pack(fill="x", pady=(0, 10))
        tb.Label(preset_row, text="Choose a common Avery product:").pack(side="left")
        self.preset_var = tk.StringVar()
        preset_names = list(label_template.AVERY_PRESETS.keys())
        combo = tb.Combobox(preset_row, textvariable=self.preset_var, state="readonly",
                             values=preset_names, width=44)
        combo.pack(side="left", padx=(8, 0))
        combo.bind("<<ComboboxSelected>>", self._apply_preset)

        # --- Option 2: upload template ---
        upload_row = tb.Frame(frm)
        upload_row.pack(fill="x", pady=(0, 10))
        tb.Button(upload_row, text="📄  Upload an Avery Template (.docx or .pdf)...",
                   command=self._upload_template, bootstyle="primary").pack(side="left")
        self.upload_status = tb.Label(upload_row, text="", font=("Helvetica", 9), foreground="#868e96")
        self.upload_status.pack(side="left", padx=(10, 0))

        tk.Frame(frm, bg="#eef1f4", height=1).pack(fill="x", pady=14)

        # --- Option 3: manual fields (also reflects preset/upload choices) ---
        tb.Label(frm, text="Layout details (edit directly if needed):",
                 font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 8))
        grid = tb.Frame(frm)
        grid.pack(fill="x")
        current = self.settings.get("label_sheet", config.LABEL_SHEET)
        for i, (key, label) in enumerate(SHEET_GEOMETRY_FIELDS):
            row, col = divmod(i, 2)
            entry = labeled_entry(grid, label, row, col=col * 2, width=12)
            entry.insert(0, str(current.get(key, "")))
            self.entries[key] = entry

        tb.Label(frm, text="Tip: print a test sheet on plain paper first and hold it up to a "
                          "real label sheet before printing on actual labels.",
                  font=("Helvetica", 8), foreground="#868e96", wraplength=440, justify="left").pack(
            anchor="w", pady=(12, 0))

        tk.Frame(frm, bg="#eef1f4", height=1).pack(fill="x", pady=14)

        # --- What actually prints on each label ---
        tb.Label(frm, text="What to print on each label:",
                 font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 8))
        current_fields = set(self.settings.get("label_fields", barcodes.DEFAULT_LABEL_FIELDS))
        self.field_vars = {}
        field_row = tb.Frame(frm)
        field_row.pack(fill="x")
        for i, key in enumerate(barcodes.LABEL_FIELD_ORDER):
            var = tk.BooleanVar(value=key in current_fields)
            self.field_vars[key] = var
            tb.Checkbutton(field_row, text=barcodes.LABEL_FIELD_INFO[key]["label"],
                           variable=var, bootstyle="round-toggle").grid(
                row=i // 3, column=i % 3, sticky="w", padx=(0, 20), pady=4)
        tb.Label(frm, text="Barcode is the scannable code image; everything else prints as text "
                          "beneath it, in the order listed above.",
                  font=("Helvetica", 8), foreground="#868e96", wraplength=440, justify="left").pack(
            anchor="w", pady=(6, 0))

        btn_row = tb.Frame(frm)
        btn_row.pack(fill="x", pady=(16, 0))
        tb.Button(btn_row, text="Cancel", command=self.destroy, bootstyle="secondary").pack(side="right", padx=(8, 0))
        tb.Button(btn_row, text="Save", command=self._save, bootstyle="success").pack(side="right")

    def _fill_fields(self, values, source_label):
        for key, _ in SHEET_GEOMETRY_FIELDS:
            entry = self.entries[key]
            entry.delete(0, tk.END)
            entry.insert(0, str(values.get(key, "")))
        self.upload_status.configure(text=source_label, foreground="#2f9e44")

    def _apply_preset(self, event=None):
        name = self.preset_var.get()
        preset = label_template.AVERY_PRESETS.get(name)
        if preset:
            self._fill_fields(preset, f"Loaded preset: {name}")

    def _upload_template(self):
        path = filedialog.askopenfilename(
            title="Select an Avery template file",
            filetypes=[("Avery templates", "*.docx *.pdf"), ("Word document", "*.docx"),
                       ("PDF file", "*.pdf"), ("All files", "*.*")])
        if not path:
            return
        try:
            detected = label_template.parse_template_file(path)
        except label_template.TemplateParseError as e:
            messagebox.showwarning("Couldn't auto-detect layout", str(e), parent=self)
            return
        except Exception as e:
            messagebox.showerror("Error reading file", str(e), parent=self)
            return
        self._fill_fields(detected, f"Detected from: {os.path.basename(path)}")
        messagebox.showinfo(
            "Layout detected",
            "Filled in the layout below from this file. Double-check the numbers "
            "against your label packaging before printing, then click Save.",
            parent=self)

    def _save(self):
        values = {}
        try:
            for key, label in SHEET_GEOMETRY_FIELDS:
                raw = self.entries[key].get().strip()
                if key in ("cols", "rows"):
                    values[key] = int(raw)
                else:
                    values[key] = float(raw)
        except ValueError:
            messagebox.showerror("Invalid value", "All fields must be numbers.", parent=self)
            return

        if values["cols"] < 1 or values["rows"] < 1:
            messagebox.showerror("Invalid layout", "Columns and rows must be at least 1.", parent=self)
            return

        selected_fields = [key for key in barcodes.LABEL_FIELD_ORDER if self.field_vars[key].get()]
        if not selected_fields:
            messagebox.showerror("Nothing selected",
                                  "Check at least one item to print on each label.", parent=self)
            return

        name = self.upload_status.cget("text") or self.preset_var.get() or "Custom layout"
        self.settings.update(label_sheet=values, label_sheet_name=name, label_fields=selected_fields)
        self.settings.save()
        self.status_bar.show("Label sheet settings saved.", "success")
        self.on_saved()
        self.destroy()


class BarcodeTab(tb.Frame):
    def __init__(self, parent, db, settings, status_bar):
        super().__init__(parent, padding=24)
        self.db = db
        self.settings = settings
        self.status_bar = status_bar
        self._preview_img = None
        self._build()
        self.refresh()

    def _build(self):
        page_header(self, "🏷️", "Barcodes",
                    "Every book gets a unique barcode automatically when added or imported. "
                    "Print labels now on regular adhesive label sheets, or feed these same "
                    "codes to a dedicated barcode label printer once you buy one.")

        body = tb.Frame(self)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left_card = Card(body, title="Books", icon="📚")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        left = left_card.body
        search_row = tb.Frame(left)
        search_row.pack(fill="x", pady=(0, 8))
        tb.Label(search_row, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        entry = tb.Entry(search_row, textvariable=self.search_var, width=30)
        entry.pack(side="left", padx=8)
        self.search_var.trace_add("write", lambda *a: self.refresh())

        self.table = BookTable(left, on_select=self._on_select)
        self.table.pack(fill="both", expand=True)

        right_card = Card(body, title="Selected Book", icon="🔖")
        right_card.grid(row=0, column=1, sticky="nsew")
        right = right_card.body

        self.preview_label = tb.Label(right, text="Select a book to preview its barcode.",
                                       foreground="#868e96")
        self.preview_label.pack(pady=(0, 10))

        self.info_label = tb.Label(right, text="", justify="left")
        self.info_label.pack(anchor="w", pady=(0, 10))

        tb.Button(right, text="Save This Barcode as PNG", command=self._save_single,
                   bootstyle="secondary-outline").pack(fill="x", pady=2)

        tk.Frame(right, bg="#eef1f4", height=1).pack(fill="x", pady=14)
        tb.Label(right, text="Batch Export", font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 8))
        tb.Button(right, text="🖨️  Label Sheet PDF — All Books", command=lambda: self._batch_export(all_books=True),
                   bootstyle="primary").pack(fill="x", pady=(0, 4))
        tb.Button(right, text="🖼️  Individual PNGs — All Books", command=lambda: self._batch_export_png(all_books=True),
                   bootstyle="secondary-outline").pack(fill="x", pady=2)

        tk.Frame(right, bg="#eef1f4", height=1).pack(fill="x", pady=14)
        tb.Label(right, text="Label Sheet Layout", font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 6))
        self.layout_label = tb.Label(right, text="", font=("Helvetica", 8), foreground="#868e96",
                                      wraplength=220, justify="left")
        self.layout_label.pack(anchor="w", pady=(0, 8))
        tb.Button(right, text="⚙️  Change Label Sheet Settings...", command=self._open_label_settings,
                   bootstyle="secondary-outline").pack(fill="x")

        self._update_layout_label()

    def _update_layout_label(self):
        cfg = self.settings.get("label_sheet", config.LABEL_SHEET)
        name = self.settings.get("label_sheet_name", "Avery 5160 (default)")
        fields = self.settings.get("label_fields", barcodes.DEFAULT_LABEL_FIELDS)
        field_names = ", ".join(barcodes.LABEL_FIELD_INFO[f]["label"] for f in fields if f in barcodes.LABEL_FIELD_INFO)
        self.layout_label.configure(
            text=f"{name}\n{cfg['label_width_in']}\" x {cfg['label_height_in']}\" "
                 f"({cfg['cols']}x{cfg['rows']} = {cfg['cols']*cfg['rows']}/sheet)\n"
                 f"Prints: {field_names or '(nothing selected)'}")

    def _open_label_settings(self):
        LabelSheetDialog(self, self.settings, self.status_bar, on_saved=self._update_layout_label)

    def refresh(self):
        query = self.search_var.get()
        books = self.db.search_books(query) if query else self.db.all_books()
        self.table.set_books(books)
        self._update_layout_label()

    def _on_select(self, book):
        if not book:
            return
        self.current_book = book
        img_bytes = barcodes.generate_barcode_bytes(book["barcode"])
        img = Image.open(io.BytesIO(img_bytes))
        img.thumbnail((280, 140))
        self._preview_img = ImageTk.PhotoImage(img)
        self.preview_label.configure(image=self._preview_img, text="")
        self.info_label.configure(
            text=f"{book['title']}\nby {book['author']}\nBarcode: {book['barcode']}")

    def _save_single(self):
        if not getattr(self, "current_book", None):
            messagebox.showinfo("No selection", "Select a book first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png", initialfile=f"{self.current_book['barcode']}.png",
            filetypes=[("PNG image", "*.png")])
        if not path:
            return
        barcodes.generate_barcode_image(self.current_book["barcode"], out_path=path)
        self.status_bar.show(f"Saved barcode to {path}", "success")

    def _batch_export(self, all_books=True):
        books = self.db.all_books()
        if not books:
            messagebox.showinfo("No books", "Add some books to the catalog first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", initialfile="barcode_labels.pdf",
            filetypes=[("PDF file", "*.pdf")])
        if not path:
            return
        try:
            barcodes.generate_label_sheet_pdf(
                books, path,
                fields=self.settings.get("label_fields"),
                label_sheet=self.settings.get("label_sheet"),
            )
        except Exception as e:
            messagebox.showerror("Export failed", str(e))
            return
        self.status_bar.show(f"Saved label sheet PDF for {len(books)} book(s) to {path}", "success")

    def _batch_export_png(self, all_books=True):
        books = self.db.all_books()
        if not books:
            messagebox.showinfo("No books", "Add some books to the catalog first.")
            return
        out_dir = filedialog.askdirectory(title="Choose folder for barcode images")
        if not out_dir:
            return
        paths = barcodes.export_barcode_images(books, out_dir)
        self.status_bar.show(f"Saved {len(paths)} barcode image(s) to {out_dir}", "success")
