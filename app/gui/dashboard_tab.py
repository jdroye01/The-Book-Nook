import tkinter as tk
from tkinter import ttk
import ttkbootstrap as tb

from app.gui.widgets import MiniBarChart, Card, page_header


class StatCard(tb.Frame):
    """A colored stat tile. Optionally clickable -- pass on_click to make
    it navigate somewhere relevant (e.g. the Checked Out count jumps to
    the Check In/Out tab)."""

    def __init__(self, parent, title, style_name="secondary", on_click=None):
        super().__init__(parent, padding=16, bootstyle=style_name, width=190, height=104)
        self.pack_propagate(False)
        if on_click:
            self.configure(cursor="hand2")

        self.value_label = tb.Label(self, text="0", font=("Helvetica", 27, "bold"),
                                     bootstyle=f"inverse-{style_name}")
        self.value_label.pack(anchor="w", pady=(0, 2))
        self.title_label = tb.Label(self, text=title, font=("Helvetica", 10),
                                     bootstyle=f"inverse-{style_name}")
        self.title_label.pack(anchor="w")

        if on_click:
            hint = tb.Label(self, text="Click for details →", font=("Helvetica", 8),
                             bootstyle=f"inverse-{style_name}")
            hint.pack(anchor="w", pady=(6, 0))
            for widget in (self, self.value_label, self.title_label, hint):
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda e: on_click())

    def set_value(self, value):
        self.value_label.configure(text=str(value))


class DashboardTab(tb.Frame):
    def __init__(self, parent, db, status_bar, navigate=None):
        super().__init__(parent, padding=24)
        self.db = db
        self.status_bar = status_bar
        self.navigate = navigate or (lambda *a, **k: None)
        self._build()
        self.refresh()

    def _build(self):
        page_header(self, "📊", "Dashboard", "Here's what's happening in your library today.")

        # --- Quick actions ---
        actions = tb.Frame(self)
        actions.pack(fill="x", pady=(0, 20))
        tb.Button(actions, text="＋ Add Book", bootstyle="success",
                  command=lambda: self.navigate("catalog", add_book=True)).pack(side="left", padx=(0, 8))
        tb.Button(actions, text="🔄 Check In / Out", bootstyle="primary",
                  command=lambda: self.navigate("checkout")).pack(side="left", padx=(0, 8))
        tb.Button(actions, text="📥 Import Books", bootstyle="secondary-outline",
                  command=lambda: self.navigate("import")).pack(side="left", padx=(0, 8))

        search_frame = tb.Frame(actions)
        search_frame.pack(side="right")
        tb.Label(search_frame, text="Quick search:", font=("Helvetica", 9)).pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        entry = tb.Entry(search_frame, textvariable=self.search_var, width=22)
        entry.pack(side="left")
        entry.bind("<Return>", self._do_quick_search)
        tb.Button(search_frame, text="Go", bootstyle="secondary-outline",
                  command=self._do_quick_search).pack(side="left", padx=(6, 0))

        # --- Stat cards ---
        cards_frame = tb.Frame(self)
        cards_frame.pack(anchor="w", pady=(0, 20))
        self.card_titles = StatCard(cards_frame, "Titles in catalog", "info",
                                     on_click=lambda: self.navigate("catalog"))
        self.card_titles.pack(side="left", padx=(0, 12))
        self.card_copies = StatCard(cards_frame, "Total copies", "secondary",
                                     on_click=lambda: self.navigate("catalog"))
        self.card_copies.pack(side="left", padx=(0, 12))
        self.card_out = StatCard(cards_frame, "Checked out", "warning",
                                  on_click=lambda: self.navigate("checkout"))
        self.card_out.pack(side="left", padx=(0, 12))
        self.card_overdue = StatCard(cards_frame, "Overdue", "danger",
                                      on_click=lambda: self.navigate("checkout"))
        self.card_overdue.pack(side="left")

        # --- Middle row: this week + top borrowed ---
        mid = tb.Frame(self)
        mid.pack(fill="x", pady=(0, 20))
        mid.grid_columnconfigure(0, weight=1)
        mid.grid_columnconfigure(1, weight=1)

        week_card = Card(mid, title="This Week", icon="📅")
        week_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        week_box = week_card.body
        self.week_checkouts_label = tb.Label(week_box, text="0 checkouts", font=("Helvetica", 13, "bold"))
        self.week_checkouts_label.pack(anchor="w", pady=(0, 4))
        self.week_returns_label = tb.Label(week_box, text="0 returns", font=("Helvetica", 13, "bold"),
                                            bootstyle="success")
        self.week_returns_label.pack(anchor="w")
        tb.Label(week_box, text="Checkouts + returns over the last 7 days.",
                 font=("Helvetica", 8), foreground="#868e96").pack(anchor="w", pady=(6, 0))

        top_card = Card(mid, title="Most Borrowed Books (all time)", icon="🏆")
        top_card.grid(row=0, column=1, sticky="nsew")
        self.top_chart = MiniBarChart(top_card.body, bar_color="#3498db", label_width=24)
        self.top_chart.pack(fill="x")

        # --- Lower row: overdue + recent activity ---
        lists_frame = tb.Frame(self)
        lists_frame.pack(fill="both", expand=True)
        lists_frame.grid_columnconfigure(0, weight=1)
        lists_frame.grid_columnconfigure(1, weight=1)
        lists_frame.grid_rowconfigure(0, weight=1)

        overdue_card = Card(lists_frame, title="Overdue Books", icon="⚠️")
        overdue_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.overdue_list = tk.Listbox(overdue_card.body, height=8, activestyle="none", borderwidth=0,
                                        highlightthickness=0)
        self.overdue_list.pack(fill="both", expand=True)

        activity_card = Card(lists_frame, title="Recent Activity", icon="🕘")
        activity_card.grid(row=0, column=1, sticky="nsew")
        self.activity_list = tk.Listbox(activity_card.body, height=8, activestyle="none", borderwidth=0,
                                         highlightthickness=0)
        self.activity_list.pack(fill="both", expand=True)

        tb.Button(self, text="Refresh", command=self.refresh, bootstyle="secondary-outline").pack(anchor="e", pady=(14, 0))

    def _do_quick_search(self, event=None):
        query = self.search_var.get().strip()
        if query:
            self.navigate("catalog", query=query)

    def refresh(self):
        s = self.db.stats()
        self.card_titles.set_value(s["total_titles"])
        self.card_copies.set_value(s["total_copies"])
        self.card_out.set_value(s["checked_out"])
        self.card_overdue.set_value(s["overdue"])

        week = self.db.week_summary()
        self.week_checkouts_label.configure(text=f"{week['checkouts']} checkouts")
        self.week_returns_label.configure(text=f"{week['returns']} returns")

        top = self.db.top_borrowed_books(5)
        self.top_chart.set_data([(t["title"], t["times_borrowed"]) for t in top])

        self.overdue_list.delete(0, tk.END)
        overdue = self.db.overdue_checkouts()
        if not overdue:
            self.overdue_list.insert(tk.END, "  No overdue books. 🎉")
        for t in overdue:
            self.overdue_list.insert(
                tk.END, f"  {t['title']}  —  {t['patron_name_snapshot']}  (due {t['due_date']})"
            )

        self.activity_list.delete(0, tk.END)
        recent = self.db.recent_activity(20)
        if not recent:
            self.activity_list.insert(tk.END, "  Nothing yet -- check out a book to get started.")
        for t in recent:
            verb = "Checked out" if t["status"] == "checked_out" else "Returned"
            date = t["return_date"] if t["status"] == "returned" else t["checkout_date"]
            self.activity_list.insert(
                tk.END, f"  {date}  —  {verb}: {t['title']} ({t['patron_name_snapshot']})"
            )
