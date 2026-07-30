"""Small reusable GUI building blocks shared across tabs."""
import tkinter as tk
from tkinter import ttk
import ttkbootstrap as tb

# Palette pulled from the app's ttkbootstrap "flatly" theme, so the custom
# (non-ttk) sidebar below matches it exactly instead of guessing colors.
SIDEBAR_BG = "#2c3e50"        # theme's "primary" navy
SIDEBAR_HOVER_BG = "#34495e"  # one step lighter, used for hover + active row
SIDEBAR_TEXT = "#aab6c2"      # muted light gray-blue for inactive items
SIDEBAR_TEXT_ACTIVE = "#ffffff"
SIDEBAR_ACCENT = "#18bc9c"    # theme's "success" teal, used as the active accent bar
SIDEBAR_SUBTLE = "#6f8299"    # dim text (subtitle, footer)


CARD_BORDER = "#e2e6ea"
MUTED_TEXT = "#868e96"
ZEBRA_STRIPE = "#f8f9fb"

BADGE_COLORS = {
    "success": ("#d3f9d8", "#2b8a3e"),
    "warning": ("#fff3bf", "#e67700"),
    "danger": ("#ffe3e3", "#c92a2a"),
    "info": ("#d0ebff", "#1864ab"),
    "secondary": ("#f1f3f5", "#495057"),
}


class Card(tk.Frame):
    """
    A flat, bordered content panel replacing the old ttk Labelframe
    "groupbox" look. Optional icon + title header with a hairline divider;
    build the rest of the section inside `.body`.
    """

    def __init__(self, parent, title=None, icon=None, padding=16, **kwargs):
        super().__init__(parent, bg="#ffffff", highlightthickness=1,
                          highlightbackground=CARD_BORDER, highlightcolor=CARD_BORDER, **kwargs)
        if title:
            header = tb.Frame(self)
            header.pack(fill="x", padx=padding, pady=(padding, 8))
            text = f"{icon}  {title}" if icon else title
            tb.Label(header, text=text, font=("Helvetica", 11, "bold")).pack(side="left")
            tk.Frame(self, bg=CARD_BORDER, height=1).pack(fill="x")
            top_pad = 12
        else:
            top_pad = padding
        self.body = tb.Frame(self)
        self.body.pack(fill="both", expand=True, padx=padding, pady=(top_pad, padding))


def page_header(parent, icon, title, subtitle=None):
    """
    Consistent page title used at the top of every section. Returns the
    title row itself (not the outer header) -- pack an action button into
    it with side="right" to place it inline with the title.
    """
    header = tb.Frame(parent)
    header.pack(fill="x", pady=(0, 18))
    row = tb.Frame(header)
    row.pack(anchor="w", fill="x")
    tb.Label(row, text=f"{icon}  {title}", font=("Helvetica", 18, "bold")).pack(side="left")
    if subtitle:
        tb.Label(header, text=subtitle, font=("Helvetica", 10), foreground=MUTED_TEXT).pack(
            anchor="w", pady=(2, 0))
    return row


def badge(parent, text, kind="secondary"):
    """A small colored status chip (e.g. Available / Checked Out / Overdue)."""
    bg, fg = BADGE_COLORS.get(kind, BADGE_COLORS["secondary"])
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=("Helvetica", 8, "bold"),
                     padx=8, pady=2)


def style_modern_treeview(style):
    """Call once (from MainWindow) to give every Treeview in the app taller
    rows, calmer heading style, and a selection color matching the theme."""
    style.configure("Treeview", rowheight=30, font=("Helvetica", 10),
                     background="#ffffff", fieldbackground="#ffffff", borderwidth=0)
    style.configure("Treeview.Heading", font=("Helvetica", 9, "bold"),
                     background="#f8f9fa", foreground="#495057", relief="flat")
    style.map("Treeview.Heading", background=[("active", "#eef1f4")])
    style.map("Treeview", background=[("selected", "#d0ebff")],
              foreground=[("selected", "#1864ab")])


def apply_zebra_tags(tree):
    """Configure oddrow/evenrow tags once; call restripe() after populating."""
    tree.tag_configure("evenrow", background="#ffffff")
    tree.tag_configure("oddrow", background=ZEBRA_STRIPE)


def restripe(tree):
    """Re-applies alternating row colors after rows have been inserted --
    call this at the end of any refresh() that repopulates a Treeview.
    Preserves any other tags already set on each row (e.g. 'overdue')."""
    for i, iid in enumerate(tree.get_children("")):
        tags = [t for t in tree.item(iid, "tags") if t not in ("evenrow", "oddrow")]
        tags.append("evenrow" if i % 2 == 0 else "oddrow")
        tree.item(iid, tags=tuple(tags))


class NavItem(tk.Frame):
    """One clickable row in the sidebar: an accent bar + icon + label that
    highlights on hover and shows a persistent accent when active."""

    def __init__(self, parent, icon, label, command):
        super().__init__(parent, bg=SIDEBAR_BG, cursor="hand2")
        self.command = command
        self.active = False

        self.accent = tk.Frame(self, bg=SIDEBAR_BG, width=4)
        self.accent.pack(side="left", fill="y")

        inner = tk.Frame(self, bg=SIDEBAR_BG)
        inner.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=11)
        self.icon_label = tk.Label(inner, text=icon, font=("Helvetica", 13),
                                    bg=SIDEBAR_BG, fg=SIDEBAR_TEXT)
        self.icon_label.pack(side="left")
        self.text_label = tk.Label(inner, text=label, font=("Helvetica", 11),
                                    bg=SIDEBAR_BG, fg=SIDEBAR_TEXT)
        self.text_label.pack(side="left", padx=(10, 0))

        for widget in (self, self.accent, inner, self.icon_label, self.text_label):
            widget.bind("<Button-1>", lambda e: self.command())
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, event):
        if not self.active:
            self._paint(SIDEBAR_HOVER_BG, SIDEBAR_TEXT_ACTIVE)

    def _on_leave(self, event):
        if not self.active:
            self._paint(SIDEBAR_BG, SIDEBAR_TEXT)

    def _paint(self, bg, fg):
        for widget in (self, self.icon_label.master, self.icon_label, self.text_label):
            widget.configure(bg=bg)
        self.icon_label.configure(fg=fg)
        self.text_label.configure(fg=fg)

    def set_active(self, active):
        self.active = active
        if active:
            self._paint(SIDEBAR_HOVER_BG, SIDEBAR_TEXT_ACTIVE)
            self.accent.configure(bg=SIDEBAR_ACCENT)
            self.text_label.configure(font=("Helvetica", 11, "bold"))
        else:
            self._paint(SIDEBAR_BG, SIDEBAR_TEXT)
            self.accent.configure(bg=SIDEBAR_BG)
            self.text_label.configure(font=("Helvetica", 11))


class Sidebar(tk.Frame):
    """
    Left-hand navigation replacing the old top tab strip: an app header,
    one NavItem per section, and a footer. Call add_item() for each
    section in order, then select(key) to switch (also called internally
    when a nav item is clicked).
    """

    def __init__(self, parent, title, subtitle, on_select, width=220):
        super().__init__(parent, bg=SIDEBAR_BG, width=width)
        self.pack_propagate(False)
        self.on_select = on_select
        self._items = {}
        self._active_key = None

        header = tk.Frame(self, bg=SIDEBAR_BG)
        header.pack(fill="x", pady=(22, 18), padx=18)
        tk.Label(header, text=title, font=("Helvetica", 15, "bold"),
                 bg=SIDEBAR_BG, fg=SIDEBAR_TEXT_ACTIVE, anchor="w").pack(fill="x")
        if subtitle:
            tk.Label(header, text=subtitle, font=("Helvetica", 9),
                     bg=SIDEBAR_BG, fg=SIDEBAR_SUBTLE, anchor="w").pack(fill="x", pady=(2, 0))

        self.items_frame = tk.Frame(self, bg=SIDEBAR_BG)
        self.items_frame.pack(fill="x")

        self.footer = tk.Label(self, text="", font=("Helvetica", 8),
                                bg=SIDEBAR_BG, fg=SIDEBAR_SUBTLE)
        self.footer.pack(side="bottom", pady=14)

    def add_item(self, key, icon, label):
        item = NavItem(self.items_frame, icon, label, command=lambda k=key: self.select(k))
        item.pack(fill="x")
        self._items[key] = item
        if self._active_key is None:
            self.select(key)

    def select(self, key):
        if key == self._active_key:
            return
        if self._active_key is not None and self._active_key in self._items:
            self._items[self._active_key].set_active(False)
        self._items[key].set_active(True)
        self._active_key = key
        if self.on_select:
            self.on_select(key)

    def set_footer(self, text):
        self.footer.configure(text=text)


class MiniBarChart(tk.Frame):
    """
    A lightweight horizontal bar list (no charting library needed) --
    one labeled row per item with a proportionally-filled colored bar.
    Used on the dashboard for "top borrowed books" and similar rankings.
    """

    def __init__(self, parent, bar_color="#3498db", track_color="#eef1f4",
                 label_width=26, value_fmt=str):
        super().__init__(parent)
        self.bar_color = bar_color
        self.track_color = track_color
        self.label_width = label_width
        self.value_fmt = value_fmt

    def set_data(self, rows):
        """rows: list of (label, value) tuples, already sorted as desired."""
        for w in self.winfo_children():
            w.destroy()
        if not rows:
            tb.Label(self, text="No data yet.", font=("Helvetica", 9), foreground="#868e96").pack(anchor="w")
            return
        max_val = max((v for _, v in rows), default=1) or 1
        for label, value in rows:
            row = tb.Frame(self)
            row.pack(fill="x", pady=3)
            text = label if len(label) <= self.label_width else label[: self.label_width - 1] + "…"
            tb.Label(row, text=text, font=("Helvetica", 9), width=self.label_width, anchor="w").pack(side="left")
            track = tk.Frame(row, bg=self.track_color, height=14)
            track.pack(side="left", fill="x", expand=True, padx=(6, 8))
            track.pack_propagate(False)
            frac = max(value, 0) / max_val
            bar = tk.Frame(track, bg=self.bar_color)
            bar.place(relx=0, rely=0, relwidth=max(frac, 0.03), relheight=1)
            tb.Label(row, text=self.value_fmt(value), font=("Helvetica", 9, "bold"), width=4).pack(side="left")


BOOK_COLUMNS = [
    ("title", "Title", 240),
    ("author", "Author", 160),
    ("genre", "Genre", 130),
    ("barcode", "Barcode", 110),
    ("copies_available", "Available", 70),
    ("copies_total", "Total", 60),
    ("shelf_location", "Shelf", 90),
]


class BookTable(tb.Frame):
    """
    A sortable, scrollable table of books used by multiple tabs.

    Click a column header to sort by it. Shift+click a different header to
    add it as an additional sort level without losing the first -- e.g.
    click "Author" then Shift+click "Title" to sort by author, then by
    title within each author, the way a library catalog would. Shift+click
    (or click) an already-active column again to flip its direction.
    """

    def __init__(self, parent, on_select=None, on_double_click=None):
        super().__init__(parent)
        self.on_select = on_select
        self.on_double_click = on_double_click
        self._books_by_iid = {}
        self._sort_keys = []  # list of (column_key, ascending) in priority order

        tb.Label(self, text="Click a column to sort. Shift+click another to sort by it too "
                            "(e.g. Author, then Title).",
                 font=("Helvetica", 8), foreground=MUTED_TEXT).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        cols = [c[0] for c in BOOK_COLUMNS]
        self.tree = tb.Treeview(self, columns=cols, show="headings", selectmode="browse")
        self._base_labels = {}
        for key, label, width in BOOK_COLUMNS:
            self._base_labels[key] = label
            self.tree.heading(key, text=label)
            anchor = "center" if key in ("copies_available", "copies_total", "barcode") else "w"
            self.tree.column(key, width=width, anchor=anchor)

        vsb = tb.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-1>", self._on_click, add="+")

        self.tree.tag_configure("out_of_stock", foreground="#b02a37")
        apply_zebra_tags(self.tree)

    def set_books(self, books):
        self.tree.delete(*self.tree.get_children())
        self._books_by_iid = {}
        for b in books:
            tags = ("out_of_stock",) if b["copies_available"] <= 0 else ()
            iid = str(b["id"])
            values = [b.get(c[0], "") for c in BOOK_COLUMNS]
            self.tree.insert("", "end", iid=iid, values=values, tags=tags)
            self._books_by_iid[iid] = b
        if self._sort_keys:
            self._apply_sort()
        else:
            restripe(self.tree)

    # ------------------------------------------------------------------
    # Multi-column sorting
    # ------------------------------------------------------------------
    def _on_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "heading":
            return
        col_id = self.tree.identify_column(event.x)  # e.g. "#2"
        try:
            idx = int(col_id.replace("#", "")) - 1
        except ValueError:
            return
        cols = [c[0] for c in BOOK_COLUMNS]
        if idx < 0 or idx >= len(cols):
            return
        key = cols[idx]
        shift_held = bool(event.state & 0x0001)
        self._update_sort(key, add_to_chain=shift_held)

    def _update_sort(self, key, add_to_chain):
        existing_idx = next((i for i, (k, _) in enumerate(self._sort_keys) if k == key), None)

        if not add_to_chain:
            if existing_idx == 0 and len(self._sort_keys) == 1:
                _, asc = self._sort_keys[0]
                self._sort_keys = [(key, not asc)]
            else:
                self._sort_keys = [(key, True)]
        else:
            if existing_idx is not None:
                k, asc = self._sort_keys[existing_idx]
                self._sort_keys[existing_idx] = (k, not asc)
            else:
                self._sort_keys.append((key, True))

        self._apply_sort()

    def _apply_sort(self):
        def sort_value(iid, key):
            val = self.tree.set(iid, key)
            try:
                return (0, float(val))
            except ValueError:
                return (1, str(val).lower())

        items = list(self.tree.get_children(""))
        for key, ascending in reversed(self._sort_keys):
            items.sort(key=lambda iid, k=key: sort_value(iid, k), reverse=not ascending)
        for index, iid in enumerate(items):
            self.tree.move(iid, "", index)

        self._update_headers()
        restripe(self.tree)

    def _update_headers(self):
        show_priority = len(self._sort_keys) > 1
        for key, label in self._base_labels.items():
            match = next(((i, asc) for i, (k, asc) in enumerate(self._sort_keys) if k == key), None)
            if match is None:
                self.tree.heading(key, text=label)
                continue
            i, asc = match
            arrow = "▲" if asc else "▼"
            suffix = f" {arrow}{i + 1}" if show_priority else f" {arrow}"
            self.tree.heading(key, text=f"{label}{suffix}")

    def selected_book(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self._books_by_iid.get(sel[0])

    def _on_select(self, event):
        if self.on_select:
            self.on_select(self.selected_book())

    def _on_double_click(self, event):
        if self.on_double_click:
            self.on_double_click(self.selected_book())


class StatusBar(tb.Frame):
    """A bottom status bar that shows transient success/error messages."""

    def __init__(self, parent):
        super().__init__(parent, padding=(10, 4))
        self.label = tb.Label(self, text="Ready", anchor="w")
        self.label.pack(side="left", fill="x", expand=True)
        self._after_id = None

    def show(self, message, kind="info", ms=5000):
        colors = {"info": "#495057", "success": "#2f9e44", "error": "#c92a2a"}
        self.label.configure(text=message, foreground=colors.get(kind, "#495057"))
        if self._after_id:
            self.after_cancel(self._after_id)
        self._after_id = self.after(ms, lambda: self.label.configure(text="Ready", foreground="#495057"))


def labeled_entry(parent, label_text, row, col=0, width=28, show=None, colspan=1):
    """Convenience: places a label + entry pair in a grid and returns the Entry widget."""
    tb.Label(parent, text=label_text).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=4)
    entry = tb.Entry(parent, width=width, show=show)
    entry.grid(row=row, column=col + 1, sticky="ew", pady=4, columnspan=colspan)
    return entry


def make_scrollable(parent):
    """Returns (outer_frame, inner_frame) where inner_frame scrolls vertically."""
    canvas = tk.Canvas(parent, highlightthickness=0)
    vsb = tb.Scrollbar(parent, orient="vertical", command=canvas.yview)
    inner = tb.Frame(canvas)

    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=vsb.set)

    canvas.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    parent.grid_rowconfigure(0, weight=1)
    parent.grid_columnconfigure(0, weight=1)
    return canvas, inner
