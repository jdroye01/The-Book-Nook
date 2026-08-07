import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
import datetime

from app import config
from app.gui.widgets import BookTable, labeled_entry, Card, page_header, badge, restripe, NameAutocomplete, make_scrollable


class CheckoutTab(tb.Frame):
    """
    Central circulation desk. The barcode entry field is where a future
    USB/Bluetooth barcode scanner will "type" scanned codes followed by
    Enter -- no code changes needed when that hardware arrives. Until then,
    staff can type the barcode manually or look the book up by title.
    """

    def __init__(self, parent, db, status_bar, on_activity=None):
        super().__init__(parent)
        self.db = db
        self.status_bar = status_bar
        self.on_activity = on_activity
        self.current_book = None
        self._row_transactions = {}
        self._build()
        self.refresh_active_list()

    def _build(self):
        # Scrollable so the active-loans list, the autocomplete dropdown,
        # and the "Currently Checked Out" table below can never push
        # something important (like the Check Out button) out of reach.
        canvas, inner = make_scrollable(self)
        inner.configure(padding=24)

        page_header(inner, "🔄", "Check In / Out",
                    "Scan a barcode, or search by title, to check a book in or out.")

        # --- Scan/search card ---
        scan_card = Card(inner, title="Scan or Enter Barcode", icon="🔍")
        scan_card.pack(fill="x", pady=(0, 16))
        scan_row = scan_card.body

        tb.Label(scan_row, text="Barcode / ISBN:").grid(row=0, column=0, sticky="w")
        self.barcode_var = tk.StringVar()
        self.barcode_entry = tb.Entry(scan_row, textvariable=self.barcode_var, width=30,
                                        font=("Helvetica", 12))
        self.barcode_entry.grid(row=0, column=1, padx=8)
        self.barcode_entry.bind("<Return>", lambda e: self._lookup())
        self.barcode_entry.focus_set()

        tb.Button(scan_row, text="Look Up", command=self._lookup, bootstyle="primary").grid(row=0, column=2, padx=4)
        tb.Button(scan_row, text="Can't scan? Search by title/author",
                   command=self._open_title_search, bootstyle="link").grid(row=0, column=3, padx=(12, 0))

        # --- Book status / action panel ---
        self.book_card = Card(inner, title="Book", icon="📖")
        self.book_card.pack(fill="x", pady=(0, 16))
        self.panel = self.book_card.body
        self._render_empty_panel()

        # --- Active checkouts table ---
        list_card = Card(inner, title="Currently Checked Out", icon="📋")
        list_card.pack(fill="both", expand=True)
        list_frame = list_card.body

        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        cols = ("title", "author", "patron", "contact", "checkout_date", "due_date", "status")
        self.tree = tb.Treeview(list_frame, columns=cols, show="headings", height=10)
        headers = {"title": "Title", "author": "Author", "patron": "Patron", "contact": "Contact",
                   "checkout_date": "Checked Out", "due_date": "Due", "status": "Status"}
        widths = {"title": 200, "author": 130, "patron": 130, "contact": 150,
                  "checkout_date": 95, "due_date": 90, "status": 90}
        for c in cols:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.tag_configure("overdue", foreground="#c92a2a")
        self.tree.tag_configure("no_contact", foreground="#999999")
        vsb = tb.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", self._on_row_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)

        action_row = tb.Frame(list_frame)
        action_row.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.checkin_selected_btn = tb.Button(
            action_row, text="Check In Selected", bootstyle="primary",
            command=self._checkin_selected_row, state="disabled")
        self.checkin_selected_btn.pack(side="left")
        self.edit_contact_selected_btn = tb.Button(
            action_row, text="Edit Contact Info...", bootstyle="secondary-outline",
            command=self._edit_contact_selected_row, state="disabled")
        self.edit_contact_selected_btn.pack(side="left", padx=(8, 0))
        tb.Label(action_row, text="Select a loan above, or double-click to view its book.",
                 font=("Helvetica", 8), foreground="#868e96").pack(side="left", padx=(12, 0))

    # ------------------------------------------------------------------
    # Empty / lookup
    # ------------------------------------------------------------------
    def _render_empty_panel(self):
        for w in self.panel.winfo_children():
            w.destroy()
        tb.Label(self.panel, text="Scan a barcode or search for a book to begin.",
                  font=("Helvetica", 10), foreground="#868e96").pack(anchor="w")

    def _lookup(self):
        code = self.barcode_var.get().strip()
        if not code:
            return
        book = self.db.get_book_by_barcode(code)
        if not book:
            messagebox.showwarning("Not found", f"No book matches barcode/ISBN '{code}'.")
            self.status_bar.show(f"No match for '{code}'.", "error")
            return
        self._show_book(book)
        self.barcode_var.set("")

    def _open_title_search(self):
        dlg = tk.Toplevel(self)
        dlg.title("Find a Book")
        dlg.geometry("640x420")
        dlg.transient(self)
        dlg.grab_set()

        top = tb.Frame(dlg, padding=10)
        top.pack(fill="x")
        tb.Label(top, text="Search:").pack(side="left")
        q = tk.StringVar()
        entry = tb.Entry(top, textvariable=q, width=40)
        entry.pack(side="left", padx=8)
        entry.focus_set()

        table_frame = tb.Frame(dlg, padding=(10, 0, 10, 10))
        table_frame.pack(fill="both", expand=True)

        def choose(book=None):
            book = book or table.selected_book()
            if book:
                self._show_book(book)
                dlg.destroy()

        table = BookTable(table_frame, on_double_click=choose)
        table.pack(fill="both", expand=True)

        def do_search(*a):
            books = self.db.search_books(q.get()) if q.get().strip() else self.db.all_books()
            table.set_books(books)

        q.trace_add("write", do_search)
        do_search()

        entry.bind("<Return>", lambda e: choose())
        btns = tb.Frame(dlg, padding=10)
        btns.pack(fill="x")
        tb.Label(btns, text="Double-click a book to select it.", font=("Helvetica", 8),
                 foreground="#868e96").pack(side="left")
        tb.Button(btns, text="Select", command=choose, bootstyle="primary").pack(side="right")

    # ------------------------------------------------------------------
    # Book panel: checkout form + active loans of this book
    # ------------------------------------------------------------------
    def _show_book(self, book):
        # Re-fetch so copy counts are current even if we got here from a stale reference.
        book = self.db.get_book(book["id"])
        self.current_book = book
        for w in self.panel.winfo_children():
            w.destroy()

        info = tb.Frame(self.panel)
        info.pack(fill="x")
        title_row = tb.Frame(info)
        title_row.pack(anchor="w", fill="x")
        tb.Label(title_row, text=book["title"], font=("Helvetica", 15, "bold")).pack(side="left")
        avail_kind = "success" if book["copies_available"] > 0 else "danger"
        avail_text = f"{book['copies_available']} of {book['copies_total']} available"
        badge(title_row, avail_text, avail_kind).pack(side="left", padx=(10, 0))

        tb.Label(info, text=f"by {book['author']}", font=("Helvetica", 10),
                 foreground="#868e96").pack(anchor="w", pady=(2, 0))
        tb.Label(info, text=f"Barcode: {book['barcode']}",
                 font=("Helvetica", 9), foreground="#868e96").pack(anchor="w", pady=(2, 10))

        if book["copies_available"] > 0:
            self._render_checkout_form(book)

        active_loans = self.db.active_checkouts_for_book(book["id"])
        if active_loans:
            self._render_active_loans_section(book, active_loans)

    def _render_checkout_form(self, book):
        form = tb.Frame(self.panel)
        form.pack(fill="x", pady=(0, 16) if self.db.active_checkouts_for_book(book["id"]) else 0)

        tb.Label(form, text="Patron name *").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.e_patron = NameAutocomplete(
            form, lookup_fn=lambda q: self.db.patrons_matching_name_prefix(q),
            on_select=self._on_patron_selected, width=30)
        self.e_patron.grid(row=0, column=1, sticky="ew", pady=4)
        # add="+" so this doesn't clobber the dropdown's own focus-out handling
        self.e_patron.entry.bind("<FocusOut>", lambda e: self._maybe_autofill_contact(), add="+")

        self.e_contact = labeled_entry(form, "Contact (phone/email)", 1, width=30)
        tb.Label(form, text="Enter an email here to enable due-date reminders.",
                 font=("Helvetica", 8), foreground="#868e96").grid(row=2, column=1, sticky="w")
        self.e_days = labeled_entry(form, "Loan days", 3, width=30)
        self.e_days.insert(0, str(config.DEFAULT_LOAN_DAYS))
        due_preview = (datetime.date.today() +
                       datetime.timedelta(days=config.DEFAULT_LOAN_DAYS)).isoformat()
        self.due_label = tb.Label(form, text=f"Due date: {due_preview}", font=("Helvetica", 9, "italic"),
                                   foreground="#495057")
        self.due_label.grid(row=4, column=1, sticky="w")

        def update_due(*a):
            try:
                d = int(self.e_days.get() or config.DEFAULT_LOAN_DAYS)
            except ValueError:
                d = config.DEFAULT_LOAN_DAYS
            due = (datetime.date.today() + datetime.timedelta(days=d)).isoformat()
            self.due_label.configure(text=f"Due date: {due}")

        self.e_days.bind("<KeyRelease>", update_due)

        tb.Button(form, text=f"Check Out '{book['title'][:24]}'", bootstyle="success",
                   command=lambda: self._do_checkout(book)).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        self.e_patron.focus_set()
        self.e_patron.bind_return(lambda: self._do_checkout(book))

    def _on_patron_selected(self, patron):
        """Fired by the name-autocomplete dropdown when an existing patron
        is picked -- preloads their saved contact info, if any."""
        if patron.get("contact"):
            self.e_contact.delete(0, tk.END)
            self.e_contact.insert(0, patron["contact"])
            self.status_bar.show(f"Loaded saved contact info for {patron['name']}.")

    def _maybe_autofill_contact(self):
        """Covers typing a known patron's full name without using the
        dropdown: if what's typed exactly matches exactly one existing
        patron and the contact field is still empty, fill it in."""
        name = self.e_patron.get().strip()
        if not name or self.e_contact.get().strip():
            return
        patron, ambiguous = self.db.find_patron_by_exact_name(name)
        if patron and patron.get("contact"):
            self.e_contact.delete(0, tk.END)
            self.e_contact.insert(0, patron["contact"])
            self.status_bar.show(f"Loaded saved contact info for {patron['name']}.")

    def _render_active_loans_section(self, book, active_loans):
        """
        Lists every copy of this book that's currently checked out, with a
        Check In / Edit Contact action per loan -- so a specific copy can be
        returned early even while other copies remain available, and a
        patron's contact info can be added or corrected after the fact.
        """
        tk.Frame(self.panel, bg="#eef1f4", height=1).pack(fill="x", pady=(4, 12))
        tb.Label(self.panel, text=f"Currently checked out ({len(active_loans)})",
                 font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(0, 8))

        today = datetime.date.today().isoformat()
        for t in active_loans:
            row = tb.Frame(self.panel)
            row.pack(fill="x", pady=4)

            overdue = t["due_date"] < today
            contact = t["patron_contact_snapshot"] or "(no contact on file)"

            tb.Label(row, text=t["patron_name_snapshot"], font=("Helvetica", 10, "bold")).pack(side="left")
            badge(row, "OVERDUE" if overdue else f"due {t['due_date']}",
                  "danger" if overdue else "secondary").pack(side="left", padx=(8, 0))
            tb.Label(row, text=contact, font=("Helvetica", 9),
                     foreground="#868e96").pack(side="left", padx=(10, 0))

            tb.Button(row, text="Check In", bootstyle="primary-outline",
                       command=lambda t=t: self._do_checkin_transaction(t)).pack(side="right", padx=(6, 0))
            tb.Button(row, text="Edit Contact", bootstyle="secondary-outline",
                       command=lambda t=t: self._edit_contact_dialog(t)).pack(side="right")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _do_checkout(self, book):
        patron = self.e_patron.get().strip()
        if not patron:
            messagebox.showwarning("Missing patron", "Enter the patron's name.")
            return
        try:
            days = int(self.e_days.get() or config.DEFAULT_LOAN_DAYS)
        except ValueError:
            days = config.DEFAULT_LOAN_DAYS
        try:
            result = self.db.checkout_book(book["barcode"], patron, self.e_contact.get().strip(), days)
            self.status_bar.show(
                f"Checked out '{book['title']}' to {patron} (due {result['due_date']}).", "success")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self._show_book(book)
        self.refresh_active_list()
        if self.on_activity:
            self.on_activity()

    def _do_checkin_transaction(self, transaction):
        """Check in one specific loan, identified by transaction id -- this
        is what makes an early return possible even when other copies of
        the same book are still checked out or available."""
        if not messagebox.askyesno(
                "Confirm check-in",
                f"Check in '{transaction['title']}' from {transaction['patron_name_snapshot']}?"):
            return
        try:
            self.db.checkin_transaction(transaction["id"])
            self.status_bar.show(
                f"Checked in '{transaction['title']}' from {transaction['patron_name_snapshot']}.", "success")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if self.current_book and self.current_book["id"] == transaction["book_id"]:
            self._show_book(self.current_book)
        self.refresh_active_list()
        if self.on_activity:
            self.on_activity()

    def _edit_contact_dialog(self, transaction):
        """Lets staff add or correct a patron's name/contact info on an
        already-checked-out loan -- e.g. add an email later so due-date
        reminders can reach them."""
        dlg = tk.Toplevel(self)
        dlg.title("Edit Loan Contact Info")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        frm = tb.Frame(dlg, padding=18)
        frm.pack()
        tb.Label(frm, text=transaction["title"], font=("Helvetica", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        e_name = labeled_entry(frm, "Patron name", 1, width=30)
        e_name.insert(0, transaction["patron_name_snapshot"] or "")
        e_contact = labeled_entry(frm, "Contact (phone/email)", 2, width=30)
        e_contact.insert(0, transaction["patron_contact_snapshot"] or "")
        tb.Label(frm, text="Adding a valid email here lets due-date reminders reach this patron.",
                 font=("Helvetica", 8), foreground="#868e96", wraplength=260, justify="left").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(0, 10))

        def save():
            name = e_name.get().strip()
            contact = e_contact.get().strip()
            if not name:
                messagebox.showerror("Missing name", "Patron name can't be blank.", parent=dlg)
                return
            self.db.update_transaction_contact(transaction["id"], patron_name=name, patron_contact=contact)
            self.status_bar.show(f"Updated contact info for {name}.", "success")
            dlg.destroy()
            if self.current_book and self.current_book["id"] == transaction["book_id"]:
                self._show_book(self.current_book)
            self.refresh_active_list()

        btn_row = tb.Frame(frm)
        btn_row.grid(row=4, column=0, columnspan=2, sticky="e", pady=(4, 0))
        tb.Button(btn_row, text="Cancel", command=dlg.destroy, bootstyle="secondary").pack(side="right", padx=(8, 0))
        tb.Button(btn_row, text="Save", command=save, bootstyle="success").pack(side="right")
        e_name.focus_set()

    # ------------------------------------------------------------------
    # Bottom table: select-a-row actions + double-click to open the book
    # ------------------------------------------------------------------
    def _on_row_select(self, event):
        has_selection = bool(self.tree.selection())
        state = "normal" if has_selection else "disabled"
        self.checkin_selected_btn.configure(state=state)
        self.edit_contact_selected_btn.configure(state=state)

    def _selected_transaction(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self._row_transactions.get(sel[0])

    def _checkin_selected_row(self):
        t = self._selected_transaction()
        if t:
            self._do_checkin_transaction(t)

    def _edit_contact_selected_row(self):
        t = self._selected_transaction()
        if t:
            self._edit_contact_dialog(t)

    def _on_row_double_click(self, event):
        t = self._selected_transaction()
        if t:
            book = self.db.get_book_by_barcode(t["barcode"])
            if book:
                self._show_book(book)

    def refresh_active_list(self):
        self.tree.delete(*self.tree.get_children())
        self._row_transactions = {}
        today = datetime.date.today().isoformat()
        for t in self.db.active_checkouts():
            overdue = t["due_date"] < today
            has_contact = bool(t["patron_contact_snapshot"])
            iid = str(t["id"])
            tags = []
            if overdue:
                tags.append("overdue")
            if not has_contact:
                tags.append("no_contact")
            self.tree.insert("", "end", iid=iid, values=(
                t["title"], t["author"], t["patron_name_snapshot"],
                t["patron_contact_snapshot"] or "—",
                t["checkout_date"], t["due_date"], "OVERDUE" if overdue else "Checked out"
            ), tags=tuple(tags))
            self._row_transactions[iid] = t
        restripe(self.tree)
        self._on_row_select(None)
