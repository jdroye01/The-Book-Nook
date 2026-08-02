import os
import threading
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from PIL import Image, ImageTk

from app import config, reminder_engine
from app.database import LibraryDB
from app.settings import Settings
from app.gui.widgets import StatusBar, Sidebar, style_modern_treeview
from app.gui.dashboard_tab import DashboardTab
from app.gui.catalog_tab import CatalogTab
from app.gui.checkout_tab import CheckoutTab
from app.gui.import_tab import ImportTab
from app.gui.barcode_tab import BarcodeTab
from app.gui.reminders_tab import RemindersTab

AUTO_CHECK_INTERVAL_MS = 60 * 60 * 1000  # re-check reminders about once an hour while open
STARTUP_CHECK_DELAY_MS = 10 * 1000       # wait a bit after launch before the first check

NAV_ITEMS = [
    ("dashboard", "📊", "Dashboard"),
    ("checkout", "🔄", "Check In / Out"),
    ("catalog", "📚", "Catalog"),
    ("import", "📥", "Import Books"),
    ("barcodes", "🏷️", "Barcodes"),
    ("reminders", "✉️", "Reminders"),
]


class MainWindow(tb.Window):
    def __init__(self):
        super().__init__(themename=config.THEME)
        self.title(config.APP_TITLE)
        self.geometry("1240x780")
        self.minsize(1040, 660)

        self.db = LibraryDB()
        self.settings = Settings()
        style_modern_treeview(self.style)
        self._set_app_icon()

        self._build_menu()

        # Overall layout: sidebar (left) + content area (right) + status bar (bottom)
        outer = tb.Frame(self)
        outer.pack(fill="both", expand=True)

        self.status_bar = StatusBar(self)
        self.status_bar.pack(side="bottom", fill="x")

        self.sidebar = Sidebar(outer, title=f"📚 {config.APP_TITLE}",
                                subtitle=config.APP_MOTTO, on_select=self._on_nav_select)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.set_footer(f"{config.APP_TITLE}")

        self.content = tb.Frame(outer)
        self.content.pack(side="left", fill="both", expand=True)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.dashboard_tab = DashboardTab(self.content, self.db, self.status_bar,
                                          navigate=self.navigate)
        self.checkout_tab = CheckoutTab(self.content, self.db, self.status_bar,
                                        on_activity=self._on_activity)
        self.catalog_tab = CatalogTab(self.content, self.db, self.status_bar)
        self.import_tab = ImportTab(self.content, self.db, self.status_bar,
                                     on_imported=self._on_catalog_changed)
        self.barcode_tab = BarcodeTab(self.content, self.db, self.settings, self.status_bar)
        self.reminders_tab = RemindersTab(self.content, self.db, self.settings, self.status_bar)

        self._frames = {
            "dashboard": self.dashboard_tab,
            "checkout": self.checkout_tab,
            "catalog": self.catalog_tab,
            "import": self.import_tab,
            "barcodes": self.barcode_tab,
            "reminders": self.reminders_tab,
        }
        for frame in self._frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

        for key, icon, label in NAV_ITEMS:
            self.sidebar.add_item(key, icon, label)

        self.after(STARTUP_CHECK_DELAY_MS, self._schedule_auto_reminder_checks)

    def _set_app_icon(self):
        """
        Sets the window icon from the bundled PNG assets. This matters most
        on macOS: when the app is launched via a wrapper script (as the
        .app bundle does), the running Python process can otherwise show
        Python's own generic icon in the Dock instead of this app's icon.
        Setting it here at the Tk level is the standard pure-Python fix
        that doesn't need any extra platform-specific dependencies.
        """
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
        try:
            images = []
            for name in ("icon_512.png", "icon_256.png"):
                path = os.path.join(assets_dir, name)
                if os.path.exists(path):
                    images.append(ImageTk.PhotoImage(Image.open(path)))
            if images:
                self.iconphoto(True, *images)
                self._icon_images = images  # keep a reference so Tk doesn't garbage-collect it
        except Exception:
            pass  # a missing/unreadable icon shouldn't ever prevent the app from starting

    def _build_menu(self):
        menubar = tk.Menu(self)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menubar)

    def _show_about(self):
        messagebox.showinfo(
            "About",
            f"{config.APP_TITLE}\n\n"
            "A book management system for small libraries.\n"
            "Search the catalog, check books in/out, bulk-import from CSV, "
            "generate/print barcode labels, and send due-date email reminders.\n\n"
            "Ready for a barcode scanner (acts as a keyboard - no setup needed) "
            "and a dedicated barcode label printer whenever you get one."
        )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def navigate(self, key, **kwargs):
        """
        Switch to a section, optionally with an action to perform once
        there -- used by the dashboard's quick actions and quick search.
        """
        self.sidebar.select(key)
        if key == "catalog":
            if kwargs.get("query"):
                self.catalog_tab.set_search_query(kwargs["query"])
            if kwargs.get("add_book"):
                self.after(150, self.catalog_tab.open_add_dialog)

    def _on_nav_select(self, key):
        frame = self._frames[key]
        frame.tkraise()
        if key == "dashboard":
            self.dashboard_tab.refresh()
        elif key == "catalog":
            self.catalog_tab.refresh()
        elif key == "checkout":
            self.checkout_tab.refresh_active_list()
        elif key == "barcodes":
            self.barcode_tab.refresh()
        elif key == "reminders":
            self.reminders_tab.refresh_log()

    def _on_activity(self):
        self.dashboard_tab.refresh()
        self.catalog_tab.refresh()

    def _on_catalog_changed(self):
        self.dashboard_tab.refresh()
        self.catalog_tab.refresh()
        self.barcode_tab.refresh()

    # ------------------------------------------------------------------
    # Background due-date reminder checks
    # ------------------------------------------------------------------
    def _schedule_auto_reminder_checks(self):
        self._run_reminder_check_background()
        self.after(AUTO_CHECK_INTERVAL_MS, self._schedule_auto_reminder_checks)

    def _run_reminder_check_background(self):
        if not self.settings.get("reminders_enabled"):
            return

        def worker():
            try:
                results = reminder_engine.run_reminder_check(self.db, self.settings)
            except Exception as e:
                results = []
                print("Reminder check failed:", e)
            self.after(0, lambda: self._on_reminder_check_done(results))

        threading.Thread(target=worker, daemon=True).start()

    def _on_reminder_check_done(self, results):
        sent = sum(1 for r in results if r["status"] == "sent")
        failed = sum(1 for r in results if r["status"] == "failed")
        if sent or failed:
            self.status_bar.show(
                f"Reminder check: {sent} sent" + (f", {failed} failed" if failed else "") + ".",
                "success" if not failed else "error",
            )
        self.reminders_tab.refresh_log()


def run():
    app = MainWindow()
    app.mainloop()
