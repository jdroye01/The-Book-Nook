import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb

from app.gui.widgets import BookTable, labeled_entry, Card, page_header


class BookFormDialog(tk.Toplevel):
    """Modal form for adding or editing a book."""

    def __init__(self, parent, db, status_bar, on_saved, book=None):
        super().__init__(parent)
        self.db = db
        self.status_bar = status_bar
        self.on_saved = on_saved
        self.book = book
        self.title("Edit Book" if book else "Add New Book")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._build()
        if book:
            self._populate(book)

    def _build(self):
        frm = tb.Frame(self, padding=22)
        frm.pack(fill="both", expand=True)
        frm.grid_columnconfigure(1, weight=1)

        icon = "✏️" if self.book else "📖"
        header_text = "Edit Book" if self.book else "Add New Book"
        tb.Label(frm, text=f"{icon}  {header_text}", font=("Helvetica", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        self.e_title = labeled_entry(frm, "Title *", 1, width=40)
        self.e_author = labeled_entry(frm, "Author *", 2, width=40)
        self.e_genre = labeled_entry(frm, "Genre(s)", 3, width=40)
        tb.Label(frm, text="(comma-separated if multiple)", font=("Helvetica", 8),
                 foreground="#868e96").grid(row=4, column=1, sticky="w", padx=(0, 0))
        self.e_isbn = labeled_entry(frm, "ISBN", 5, width=40)
        self.e_publisher = labeled_entry(frm, "Publisher", 6, width=40)
        self.e_year = labeled_entry(frm, "Year", 7, width=40)
        self.e_shelf = labeled_entry(frm, "Shelf location", 8, width=40)
        self.e_copies = labeled_entry(frm, "Total copies", 9, width=40)
        self.e_copies.insert(0, "1")
        self.e_notes = labeled_entry(frm, "Notes", 10, width=40)

        if self.book:
            tb.Label(frm, text="Barcode").grid(row=11, column=0, sticky="w", pady=4)
            tb.Label(frm, text=self.book["barcode"], font=("Helvetica", 10, "bold")).grid(
                row=11, column=1, sticky="w", pady=4)

        btn_frame = tb.Frame(frm)
        btn_frame.grid(row=12, column=0, columnspan=2, sticky="e", pady=(18, 0))
        tb.Button(btn_frame, text="Cancel", command=self.destroy, bootstyle="secondary").pack(side="right", padx=(8, 0))
        tb.Button(btn_frame, text="Save", command=self._save, bootstyle="success").pack(side="right")

    def _populate(self, b):
        self.e_title.insert(0, b["title"])
        self.e_author.insert(0, b["author"])
        self.e_genre.insert(0, b.get("genre") or "")
        self.e_isbn.insert(0, b.get("isbn") or "")
        self.e_publisher.insert(0, b.get("publisher") or "")
        self.e_year.insert(0, b.get("pub_year") or "")
        self.e_shelf.insert(0, b.get("shelf_location") or "")
        self.e_copies.delete(0, tk.END)
        self.e_copies.insert(0, str(b.get("copies_total") or 1))
        self.e_notes.insert(0, b.get("notes") or "")

    def _save(self):
        title = self.e_title.get().strip()
        author = self.e_author.get().strip()
        if not title or not author:
            messagebox.showerror("Missing info", "Title and Author are required.", parent=self)
            return
        try:
            copies = int(self.e_copies.get().strip() or "1")
        except ValueError:
            messagebox.showerror("Invalid copies", "Total copies must be a number.", parent=self)
            return

        try:
            if self.book:
                # copies_available shifts by the same delta as copies_total
                delta = copies - self.book["copies_total"]
                self.db.update_book(
                    self.book["id"],
                    title=title, author=author, genre=self.e_genre.get().strip(),
                    isbn=self.e_isbn.get().strip(), publisher=self.e_publisher.get().strip(),
                    pub_year=self.e_year.get().strip(), shelf_location=self.e_shelf.get().strip(),
                    copies_total=copies, notes=self.e_notes.get().strip(),
                )
                if delta != 0:
                    new_avail = self.book["copies_available"] + delta
                    self.db.set_copies_available(self.book["id"], new_avail)
                self.status_bar.show(f"Updated '{title}'.", "success")
            else:
                self.db.add_book(
                    title=title, author=author, genre=self.e_genre.get().strip(),
                    isbn=self.e_isbn.get().strip(), publisher=self.e_publisher.get().strip(),
                    pub_year=self.e_year.get().strip(), shelf_location=self.e_shelf.get().strip(),
                    copies_total=copies, notes=self.e_notes.get().strip(),
                )
                self.status_bar.show(f"Added '{title}' to the catalog.", "success")
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
            return

        self.on_saved()
        self.destroy()


class CatalogTab(tb.Frame):
    def __init__(self, parent, db, status_bar):
        super().__init__(parent, padding=24)
        self.db = db
        self.status_bar = status_bar
        self._build()
        self.refresh()

    def _build(self):
        header = page_header(self, "📚", "Catalog", None)
        # Add Book lives next to the page title -- the primary action for this page.
        tb.Button(header, text="＋ Add Book", command=self._add_book, bootstyle="success").pack(side="right")

        card = Card(self, padding=16)
        card.pack(fill="both", expand=True)
        body = card.body

        top = tb.Frame(body)
        top.pack(fill="x", pady=(0, 12))

        tb.Label(top, text="Search:").pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        entry = tb.Entry(top, textvariable=self.search_var, width=36)
        entry.pack(side="left", padx=(0, 8))
        entry.bind("<Return>", lambda e: self.refresh())
        self.search_var.trace_add("write", lambda *a: self.refresh())

        self.field_var = tk.StringVar(value="All")
        field_combo = tb.Combobox(top, textvariable=self.field_var, state="readonly", width=14,
                                    values=["All", "Title", "Author", "Genre", "Barcode/ISBN"])
        field_combo.pack(side="left", padx=(0, 12))
        field_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        tb.Button(top, text="Delete", command=self._delete_book, bootstyle="danger-outline").pack(side="right")
        tb.Button(top, text="Edit", command=self._edit_book, bootstyle="secondary-outline").pack(side="right", padx=(0, 6))

        self.count_label = tb.Label(body, text="", font=("Helvetica", 9), foreground="#868e96")
        self.count_label.pack(anchor="w", pady=(0, 8))

        self.table = BookTable(body, on_double_click=lambda b: self._edit_book())
        self.table.pack(fill="both", expand=True)

    def set_search_query(self, query):
        """Used by the dashboard's quick search box to jump here with a
        query already filled in and applied."""
        self.search_var.set(query)
        self.refresh()

    def refresh(self):
        query = self.search_var.get()
        field = self.field_var.get()
        books = self.db.search_books(query, field) if query else self.db.all_books()
        self.table.set_books(books)
        self.count_label.configure(text=f"{len(books)} book(s)")

    def open_add_dialog(self):
        """Public entry point for other tabs (e.g. the dashboard's
        '+ Add Book' quick action) to open the add-book dialog."""
        self._add_book()

    def _add_book(self):
        BookFormDialog(self, self.db, self.status_bar, on_saved=self.refresh)

    def _edit_book(self):
        book = self.table.selected_book()
        if not book:
            messagebox.showinfo("No selection", "Select a book to edit first.")
            return
        BookFormDialog(self, self.db, self.status_bar, on_saved=self.refresh, book=book)

    def _delete_book(self):
        book = self.table.selected_book()
        if not book:
            messagebox.showinfo("No selection", "Select a book to delete first.")
            return
        if not messagebox.askyesno("Confirm delete", f"Delete '{book['title']}'? This cannot be undone."):
            return
        try:
            self.db.delete_book(book["id"])
            self.status_bar.show(f"Deleted '{book['title']}'.", "success")
        except Exception as e:
            messagebox.showerror("Cannot delete", str(e))
        self.refresh()
