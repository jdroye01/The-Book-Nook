import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ttkbootstrap as tb

from app import patron_importer
from app.gui.widgets import Card, page_header, labeled_entry, make_scrollable, apply_zebra_tags, restripe


PATRON_IMPORT_FIELDS = [
    ("name", "Name", True),
    ("contact", "Contact / Email", False),
]


class PatronFormDialog(tk.Toplevel):
    """Modal form for adding or editing a patron."""

    def __init__(self, parent, db, status_bar, on_saved, patron=None):
        super().__init__(parent)
        self.db = db
        self.status_bar = status_bar
        self.on_saved = on_saved
        self.patron = patron
        self.title("Edit Patron" if patron else "Add New Patron")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._build()
        if patron:
            self.e_name.insert(0, patron["name"])
            self.e_contact.insert(0, patron.get("contact") or "")

    def _build(self):
        frm = tb.Frame(self, padding=22)
        frm.pack(fill="both", expand=True)
        icon = "✏️" if self.patron else "👤"
        header_text = "Edit Patron" if self.patron else "Add New Patron"
        tb.Label(frm, text=f"{icon}  {header_text}", font=("Helvetica", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        self.e_name = labeled_entry(frm, "Name *", 1, width=34)
        self.e_contact = labeled_entry(frm, "Contact (phone/email)", 2, width=34)
        tb.Label(frm, text="An email here lets due-date reminders reach this patron.",
                 font=("Helvetica", 8), foreground="#868e96", wraplength=280, justify="left").grid(
            row=3, column=1, sticky="w")

        btn_row = tb.Frame(frm)
        btn_row.grid(row=4, column=0, columnspan=2, sticky="e", pady=(18, 0))
        tb.Button(btn_row, text="Cancel", command=self.destroy, bootstyle="secondary").pack(side="right", padx=(8, 0))
        tb.Button(btn_row, text="Save", command=self._save, bootstyle="success").pack(side="right")
        self.e_name.focus_set()

    def _save(self):
        name = self.e_name.get().strip()
        contact = self.e_contact.get().strip()
        if not name:
            messagebox.showerror("Missing name", "Patron name is required.", parent=self)
            return
        try:
            if self.patron:
                self.db.update_patron(self.patron["id"], name=name, contact=contact)
                self.status_bar.show(f"Updated '{name}'.", "success")
            else:
                self.db.add_patron(name, contact)
                self.status_bar.show(f"Added '{name}' to patrons.", "success")
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
            return
        self.on_saved()
        self.destroy()


class PatronsTab(tb.Frame):
    def __init__(self, parent, db, status_bar):
        super().__init__(parent)
        self.db = db
        self.status_bar = status_bar
        self.csv_path = None
        self.headers = []
        self.mapping_vars = {}
        self._build()
        self.refresh()

    def _build(self):
        canvas, inner = make_scrollable(self)
        inner.configure(padding=24)

        page_header(inner, "👤", "Patrons",
                    "Everyone who's ever checked out a book is remembered here automatically. "
                    "Add people ahead of time, or bulk-import a patron list from CSV.")

        # --- Import card ---
        import_card = Card(inner, title="Import Patrons from CSV", icon="📥")
        import_card.pack(fill="x", pady=(0, 14))
        ibody = import_card.body

        file_row = tb.Frame(ibody)
        file_row.pack(fill="x")
        tb.Button(file_row, text="Choose CSV File...", command=self._choose_file,
                   bootstyle="primary").pack(side="left")
        self.file_label = tb.Label(file_row, text="No file selected.", foreground="#868e96")
        self.file_label.pack(side="left", padx=12)

        self.mapping_frame = tb.Frame(ibody)
        self.mapping_frame.pack(fill="x", pady=(12, 0))
        tb.Label(self.mapping_frame, text="Select a CSV file to configure column mapping.",
                 foreground="#868e96").pack(anchor="w")

        import_btn_row = tb.Frame(ibody)
        import_btn_row.pack(fill="x", pady=(12, 0))
        self.import_btn = tb.Button(import_btn_row, text="Import Patrons", command=self._do_import,
                                     bootstyle="success", state="disabled")
        self.import_btn.pack(side="left")
        self.import_result_label = tb.Label(import_btn_row, text="")
        self.import_result_label.pack(side="left", padx=12)
        tb.Label(ibody, text="Existing patrons (matched by exact name) get their contact info "
                             "updated rather than duplicated; new names are added as new patrons.",
                  font=("Helvetica", 8), foreground="#868e96", wraplength=700, justify="left").pack(
            anchor="w", pady=(8, 0))

        # --- Patron list card ---
        list_card = Card(inner, title="All Patrons", icon="📋")
        list_card.pack(fill="both", expand=True)
        lbody = list_card.body

        top = tb.Frame(lbody)
        top.pack(fill="x", pady=(0, 10))
        tb.Label(top, text="Search:").pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        entry = tb.Entry(top, textvariable=self.search_var, width=32)
        entry.pack(side="left")
        self.search_var.trace_add("write", lambda *a: self.refresh())

        tb.Button(top, text="＋ Add Patron", command=self._add_patron, bootstyle="success").pack(side="right")
        tb.Button(top, text="Delete", command=self._delete_patron, bootstyle="danger-outline").pack(
            side="right", padx=(0, 6))
        tb.Button(top, text="Edit", command=self._edit_patron, bootstyle="secondary-outline").pack(
            side="right", padx=(0, 6))

        self.count_label = tb.Label(lbody, text="", font=("Helvetica", 9), foreground="#868e96")
        self.count_label.pack(anchor="w", pady=(0, 6))

        cols = ("name", "contact", "since", "active")
        headers = {"name": "Name", "contact": "Contact", "since": "Patron Since", "active": "Checked Out Now"}
        widths = {"name": 220, "contact": 240, "since": 130, "active": 130}
        self.tree = tb.Treeview(lbody, columns=cols, show="headings", height=12)
        for c in cols:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=widths[c], anchor="center" if c == "active" else "w")
        apply_zebra_tags(self.tree)
        vsb = tb.Scrollbar(lbody, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._edit_patron())

        self._patrons_by_iid = {}

    # ------------------------------------------------------------------
    # Patron list
    # ------------------------------------------------------------------
    def refresh(self):
        query = self.search_var.get().strip()
        patrons = self.db.search_patrons(query) if query else self.db.all_patrons()
        self.tree.delete(*self.tree.get_children())
        self._patrons_by_iid = {}
        for p in patrons:
            iid = str(p["id"])
            active_count = self.db.patron_active_checkout_count(p["id"])
            self.tree.insert("", "end", iid=iid, values=(
                p["name"], p.get("contact") or "—", (p.get("date_added") or "")[:10],
                active_count if active_count else ""
            ))
            self._patrons_by_iid[iid] = p
        restripe(self.tree)
        self.count_label.configure(text=f"{len(patrons)} patron(s)")

    def _selected_patron(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self._patrons_by_iid.get(sel[0])

    def _add_patron(self):
        PatronFormDialog(self, self.db, self.status_bar, on_saved=self.refresh)

    def _edit_patron(self):
        patron = self._selected_patron()
        if not patron:
            messagebox.showinfo("No selection", "Select a patron to edit first.")
            return
        PatronFormDialog(self, self.db, self.status_bar, on_saved=self.refresh, patron=patron)

    def _delete_patron(self):
        patron = self._selected_patron()
        if not patron:
            messagebox.showinfo("No selection", "Select a patron to delete first.")
            return
        if not messagebox.askyesno("Confirm delete", f"Delete '{patron['name']}'? This cannot be undone."):
            return
        try:
            self.db.delete_patron(patron["id"])
            self.status_bar.show(f"Deleted '{patron['name']}'.", "success")
        except Exception as e:
            messagebox.showerror("Cannot delete", str(e))
        self.refresh()

    # ------------------------------------------------------------------
    # CSV import
    # ------------------------------------------------------------------
    def _choose_file(self):
        path = filedialog.askopenfilename(title="Select CSV file",
                                           filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        self.csv_path = path
        self.file_label.configure(text=os.path.basename(path), foreground="#212529")
        try:
            self.headers, auto_mapping = patron_importer.sniff_columns(path)
        except Exception as e:
            messagebox.showerror("Error reading file", str(e))
            return
        self._build_mapping_ui(auto_mapping)
        self.import_btn.configure(state="normal")

    def _build_mapping_ui(self, auto_mapping):
        for w in self.mapping_frame.winfo_children():
            w.destroy()
        self.mapping_vars = {}
        tb.Label(self.mapping_frame, text="Field", font=("Helvetica", 9, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 20))
        tb.Label(self.mapping_frame, text="CSV Column", font=("Helvetica", 9, "bold")).grid(
            row=0, column=1, sticky="w")
        options = ["(none)"] + self.headers
        for i, (field, label, required) in enumerate(PATRON_IMPORT_FIELDS, start=1):
            text = label + (" *" if required else "")
            tb.Label(self.mapping_frame, text=text).grid(row=i, column=0, sticky="w", padx=(0, 20), pady=2)
            var = tk.StringVar(value=auto_mapping.get(field, "(none)"))
            combo = tb.Combobox(self.mapping_frame, textvariable=var, values=options, state="readonly", width=30)
            combo.grid(row=i, column=1, sticky="w", pady=2)
            self.mapping_vars[field] = var

    def _do_import(self):
        mapping = {f: (var.get() if var.get() != "(none)" else None) for f, var in self.mapping_vars.items()}
        if not mapping.get("name"):
            messagebox.showwarning("Mapping incomplete", "The Name column must be mapped.")
            return

        counts, errors = patron_importer.import_csv(self.db, self.csv_path, mapping)
        parts = []
        if counts["created"]:
            parts.append(f"{counts['created']} added")
        if counts["updated"]:
            parts.append(f"{counts['updated']} updated")
        if counts["unchanged"]:
            parts.append(f"{counts['unchanged']} unchanged")
        if counts["skipped_ambiguous"]:
            parts.append(f"{counts['skipped_ambiguous']} skipped (ambiguous name)")
        msg = ", ".join(parts) if parts else "No rows processed."
        if errors:
            detail = "\n".join(f"Row {r}: {m}" for r, m in errors[:20])
            if len(errors) > 20:
                detail += f"\n...and {len(errors) - 20} more."
            messagebox.showwarning("Import finished with issues", msg + f"\n\n{len(errors)} row(s) skipped:\n" + detail)
        else:
            self.status_bar.show(f"Patron import: {msg}.", "success")
        self.import_result_label.configure(text=msg)
        self.refresh()
