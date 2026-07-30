import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ttkbootstrap as tb

from app import importer
from app.gui.widgets import Card, page_header


CANONICAL_FIELDS = [
    ("title", "Title", True),
    ("author", "Author", True),
    ("genre", "Genre", False),
    ("isbn", "ISBN", False),
    ("publisher", "Publisher", False),
    ("pub_year", "Year", False),
    ("shelf_location", "Shelf location", False),
    ("copies_total", "Copies", False),
    ("barcode", "Barcode (blank = auto-generate)", False),
    ("notes", "Notes", False),
]


class ImportTab(tb.Frame):
    def __init__(self, parent, db, status_bar, on_imported=None):
        super().__init__(parent, padding=24)
        self.db = db
        self.status_bar = status_bar
        self.on_imported = on_imported
        self.csv_path = None
        self.headers = []
        self.mapping_vars = {}
        self._build()

    def _build(self):
        page_header(self, "📥", "Import Books",
                    "Works with exports from spreadsheets, other catalog systems, or a "
                    "hand-typed CSV. Column names are auto-detected where possible.")

        file_card = Card(self, title="1. Choose a File", icon="📄")
        file_card.pack(fill="x", pady=(0, 14))
        file_row = file_card.body
        tb.Button(file_row, text="Choose CSV File...", command=self._choose_file,
                   bootstyle="primary").pack(side="left")
        self.file_label = tb.Label(file_row, text="No file selected.", foreground="#868e96")
        self.file_label.pack(side="left", padx=12)

        self.mapping_card = Card(self, title="2. Column Mapping", icon="🔗")
        self.mapping_card.pack(fill="x", pady=(0, 14))
        self.mapping_frame = self.mapping_card.body
        tb.Label(self.mapping_frame, text="Select a CSV file to configure column mapping.",
                 foreground="#868e96").pack(anchor="w")

        preview_card = Card(self, title="3. Preview (first rows)", icon="👁️")
        preview_card.pack(fill="both", expand=True, pady=(0, 14))
        preview_frame = preview_card.body
        self.preview_tree = tb.Treeview(preview_frame, show="headings", height=6)
        vsb = tb.Scrollbar(preview_frame, orient="vertical", command=self.preview_tree.yview)
        hsb = tb.Scrollbar(preview_frame, orient="horizontal", command=self.preview_tree.xview)
        self.preview_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.preview_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        preview_frame.grid_rowconfigure(0, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        bottom = tb.Frame(self)
        bottom.pack(fill="x")
        self.import_btn = tb.Button(bottom, text="Import Books", command=self._do_import,
                                      bootstyle="success", state="disabled")
        self.import_btn.pack(side="left")
        self.result_label = tb.Label(bottom, text="")
        self.result_label.pack(side="left", padx=12)

    def _choose_file(self):
        path = filedialog.askopenfilename(title="Select CSV file", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        self.csv_path = path
        self.file_label.configure(text=os.path.basename(path), foreground="#212529")
        try:
            self.headers, auto_mapping = importer.sniff_columns(path)
        except Exception as e:
            messagebox.showerror("Error reading file", str(e))
            return
        self._build_mapping_ui(auto_mapping)
        self._load_preview()
        self.import_btn.configure(state="normal")

    def _build_mapping_ui(self, auto_mapping):
        for w in self.mapping_frame.winfo_children():
            w.destroy()
        self.mapping_vars = {}

        tb.Label(self.mapping_frame, text="Field", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 20))
        tb.Label(self.mapping_frame, text="CSV Column", font=("Helvetica", 9, "bold")).grid(row=0, column=1, sticky="w")

        options = ["(none)"] + self.headers
        for i, (field, label, required) in enumerate(CANONICAL_FIELDS, start=1):
            text = label + (" *" if required else "")
            tb.Label(self.mapping_frame, text=text).grid(row=i, column=0, sticky="w", padx=(0, 20), pady=2)
            var = tk.StringVar(value=auto_mapping.get(field, "(none)"))
            combo = tb.Combobox(self.mapping_frame, textvariable=var, values=options, state="readonly", width=30)
            combo.grid(row=i, column=1, sticky="w", pady=2)
            self.mapping_vars[field] = var

    def _load_preview(self):
        rows = importer.preview_rows(self.csv_path, limit=8)
        self.preview_tree.delete(*self.preview_tree.get_children())
        self.preview_tree["columns"] = self.headers
        for h in self.headers:
            self.preview_tree.heading(h, text=h)
            self.preview_tree.column(h, width=120)
        for row in rows:
            self.preview_tree.insert("", "end", values=[row.get(h, "") for h in self.headers])

    def _do_import(self):
        mapping = {f: (var.get() if var.get() != "(none)" else None)
                   for f, var in self.mapping_vars.items()}
        if not mapping.get("title") or not mapping.get("author"):
            messagebox.showwarning("Mapping incomplete", "Title and Author columns must be mapped.")
            return

        total = importer.count_rows(self.csv_path)
        if total > 50 and not messagebox.askyesno(
                "Confirm import", f"Import {total} books into the catalog?"):
            return

        success, errors = importer.import_csv(self.db, self.csv_path, mapping)
        msg = f"Imported {success} of {total} book(s)."
        if errors:
            msg += f" {len(errors)} row(s) skipped."
            detail = "\n".join(f"Row {r}: {m}" for r, m in errors[:20])
            if len(errors) > 20:
                detail += f"\n...and {len(errors) - 20} more."
            messagebox.showwarning("Import finished with issues", msg + "\n\n" + detail)
        else:
            self.status_bar.show(msg, "success")
        self.result_label.configure(text=msg)
        if self.on_imported:
            self.on_imported()
