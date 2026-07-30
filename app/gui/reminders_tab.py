import threading
import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb

from app import config, email_utils, reminder_engine
from app.gui.widgets import labeled_entry, Card, page_header, restripe


class EmailTemplateDialog(tk.Toplevel):
    """
    Lets the librarian customize the subject/body wording sent for each
    reminder scenario (before due / due today / overdue), using
    {placeholders} that get filled in per patron/book at send time.
    """

    SAMPLE_OFFSETS = {"before_due": -3, "due_today": 0, "overdue": 5}
    SAMPLE_BOOK = {"title": "The Sample Book", "author": "Jane Author"}
    SAMPLE_TXN = {"patron_name_snapshot": "Sam Patron", "due_date": "2026-08-01"}

    def __init__(self, parent, settings, status_bar):
        super().__init__(parent)
        self.settings = settings
        self.status_bar = status_bar
        self.title("Customize Email Templates")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.tab_widgets = {}
        self._build()

    def _build(self):
        frm = tb.Frame(self, padding=22)
        frm.pack(fill="both", expand=True)

        tb.Label(frm, text="✏️  Customize Email Templates", font=("Helvetica", 14, "bold")).pack(
            anchor="w", pady=(0, 4))
        tb.Label(frm, text="Edit the subject and body sent for each situation. Use Preview to see "
                          "exactly what a patron would receive before saving.",
                  font=("Helvetica", 9), foreground="#868e96", wraplength=560, justify="left").pack(
            anchor="w", pady=(0, 12))

        ph_card = tb.Labelframe(frm, text="Available placeholders", padding=10)
        ph_card.pack(fill="x", pady=(0, 14))
        for ph, desc in email_utils.PLACEHOLDER_HELP:
            row = tb.Frame(ph_card)
            row.pack(fill="x", pady=1)
            tb.Label(row, text=ph, font=("Courier", 9, "bold"), width=16, anchor="w").pack(side="left")
            tb.Label(row, text=desc, font=("Helvetica", 9), foreground="#495057").pack(side="left")

        notebook = tb.Notebook(frm)
        notebook.pack(fill="both", expand=True)

        templates = self.settings.get("email_templates") or {}
        for scenario in ("before_due", "due_today", "overdue"):
            tab = tb.Frame(notebook, padding=14)
            notebook.add(tab, text=email_utils.SCENARIO_LABELS[scenario])
            self._build_scenario_tab(tab, scenario, templates.get(scenario) or {})

        btn_row = tb.Frame(frm)
        btn_row.pack(fill="x", pady=(16, 0))
        tb.Button(btn_row, text="Cancel", command=self.destroy, bootstyle="secondary").pack(side="right", padx=(8, 0))
        tb.Button(btn_row, text="Save All", command=self._save, bootstyle="success").pack(side="right")

    def _build_scenario_tab(self, tab, scenario, current):
        default = email_utils.DEFAULT_EMAIL_TEMPLATES[scenario]

        tb.Label(tab, text="Subject:").pack(anchor="w")
        subject_var = tk.StringVar(value=current.get("subject") or default["subject"])
        tb.Entry(tab, textvariable=subject_var, width=70).pack(fill="x", pady=(2, 10))

        tb.Label(tab, text="Body:").pack(anchor="w")
        body_text = tk.Text(tab, height=10, width=70, wrap="word", font=("Helvetica", 10))
        body_text.pack(fill="both", expand=True, pady=(2, 10))
        body_text.insert("1.0", current.get("body") or default["body"])

        preview_box = tk.Text(tab, height=8, width=70, wrap="word", font=("Helvetica", 9),
                              bg="#f8f9fa", fg="#495057", state="disabled")

        def do_preview():
            offset = self.SAMPLE_OFFSETS[scenario]
            values = email_utils.build_placeholder_values(
                self.SAMPLE_BOOK, self.SAMPLE_TXN, offset,
                self.settings.get("library_name") or "Your Library")
            rendered_subject = email_utils.render_template(subject_var.get(), values)
            rendered_body = email_utils.render_template(body_text.get("1.0", "end-1c"), values)
            preview_box.configure(state="normal")
            preview_box.delete("1.0", "end")
            preview_box.insert("1.0", f"Subject: {rendered_subject}\n\n{rendered_body}")
            preview_box.configure(state="disabled")

        def do_reset():
            subject_var.set(default["subject"])
            body_text.delete("1.0", "end")
            body_text.insert("1.0", default["body"])

        btn_row = tb.Frame(tab)
        btn_row.pack(fill="x", pady=(0, 8))
        tb.Button(btn_row, text="👁  Preview", command=do_preview, bootstyle="primary-outline").pack(side="left")
        tb.Button(btn_row, text="Reset to Default", command=do_reset, bootstyle="secondary-outline").pack(
            side="left", padx=(8, 0))

        tb.Label(tab, text="Preview (sample data):", font=("Helvetica", 9, "bold")).pack(anchor="w")
        preview_box.pack(fill="both", expand=True, pady=(2, 0))

        self.tab_widgets[scenario] = {"subject_var": subject_var, "body_text": body_text}

    def _save(self):
        templates = {}
        for scenario, widgets in self.tab_widgets.items():
            subject = widgets["subject_var"].get().strip()
            body = widgets["body_text"].get("1.0", "end-1c")
            default = email_utils.DEFAULT_EMAIL_TEMPLATES[scenario]
            templates[scenario] = {
                "subject": subject or default["subject"],
                "body": body if body.strip() else default["body"],
            }
        self.settings.update(email_templates=templates)
        self.settings.save()
        self.status_bar.show("Email templates saved.", "success")
        self.destroy()


class RemindersTab(tb.Frame):
    """
    Lets the librarian configure an outgoing email account (SMTP) and a
    schedule of reminders (e.g. 3 days before due, on due date, 3/7 days
    overdue). Reminders are checked automatically while the app is open
    (see MainWindow's periodic scheduler) and can also be triggered here
    on demand. A patron only gets a reminder if a valid-looking email was
    entered in the Contact field at checkout time.
    """

    def __init__(self, parent, db, settings, status_bar):
        super().__init__(parent, padding=24)
        self.db = db
        self.settings = settings
        self.status_bar = status_bar
        self._build()
        self.refresh_log()

    def _build(self):
        page_header(self, "✉️", "Reminders",
                    "Sends an email to a patron's Contact address (entered at checkout) when a "
                    "book is approaching, at, or past its due date. The app must be running for "
                    "scheduled reminders to go out -- it checks automatically about once an hour "
                    "while open, or you can check on demand below.")

        body = tb.Frame(self)
        body.pack(fill="x", pady=(0, 14))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        # --- Left: SMTP settings ---
        smtp_card = Card(body, title="Outgoing Email (SMTP) Settings", icon="📧")
        smtp_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        smtp_box = smtp_card.body

        s = self.settings
        self.e_host = labeled_entry(smtp_box, "SMTP server", 0, width=28)
        self.e_host.insert(0, s.get("smtp_host", ""))
        self.e_port = labeled_entry(smtp_box, "Port", 1, width=28)
        self.e_port.insert(0, str(s.get("smtp_port", 587)))

        tb.Label(smtp_box, text="Security").grid(row=2, column=0, sticky="w", pady=4)
        self.security_var = tk.StringVar(value=s.get("smtp_security", "starttls"))
        tb.Combobox(smtp_box, textvariable=self.security_var, state="readonly", width=25,
                     values=["starttls", "ssl", "none"]).grid(row=2, column=1, sticky="ew", pady=4)

        self.e_user = labeled_entry(smtp_box, "Username", 3, width=28)
        self.e_user.insert(0, s.get("smtp_username", ""))
        self.e_pass = labeled_entry(smtp_box, "Password", 4, width=28, show="*")
        self.e_pass.insert(0, s.get("smtp_password", ""))
        self.e_from_email = labeled_entry(smtp_box, "From address", 5, width=28)
        self.e_from_email.insert(0, s.get("from_email", ""))
        self.e_from_name = labeled_entry(smtp_box, "From name", 6, width=28)
        self.e_from_name.insert(0, s.get("from_name", "Library"))
        self.e_library_name = labeled_entry(smtp_box, "Library name (in emails)", 7, width=28)
        self.e_library_name.insert(0, s.get("library_name", "Your Library"))

        tb.Label(smtp_box, text="Gmail/Outlook usually require an app password, not your "
                                 "normal login password.", font=("Helvetica", 8), foreground="#868e96",
                  wraplength=280, justify="left").grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

        btn_row = tb.Frame(smtp_box)
        btn_row.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        tb.Button(btn_row, text="Save Settings", command=self._save_settings,
                   bootstyle="success").pack(side="left")
        tb.Button(btn_row, text="Send Test Email...", command=self._send_test_email,
                   bootstyle="secondary-outline").pack(side="left", padx=(8, 0))

        # --- Right: schedule + manual check ---
        sched_card = Card(body, title="Reminder Schedule", icon="⏰")
        sched_card.grid(row=0, column=1, sticky="nsew")
        sched_box = sched_card.body

        self.enabled_var = tk.BooleanVar(value=s.get("reminders_enabled", False))
        tb.Checkbutton(sched_box, text="Automatically send reminders while the app is open",
                        variable=self.enabled_var, bootstyle="round-toggle").pack(anchor="w", pady=(0, 12))

        tb.Label(sched_box, text="Send at these points relative to the due date:").pack(anchor="w")
        tb.Label(sched_box, text="(e.g. -3, 0, 3, 7  =  3 days before, on the day, "
                                  "3 days after, 7 days after)",
                  font=("Helvetica", 8), foreground="#868e96").pack(anchor="w", pady=(0, 6))
        self.offsets_var = tk.StringVar(
            value=", ".join(str(o) for o in s.get("reminder_offsets", [-3, 0, 3, 7])))
        tb.Entry(sched_box, textvariable=self.offsets_var, width=30).pack(anchor="w", fill="x")

        tk.Frame(sched_box, bg="#eef1f4", height=1).pack(fill="x", pady=16)
        tb.Button(sched_box, text="🔎  Check & Send Reminders Now", command=self._check_now,
                   bootstyle="primary").pack(anchor="w")
        tb.Button(sched_box, text="✏️  Customize Email Templates...", command=self._open_template_editor,
                   bootstyle="secondary-outline").pack(anchor="w", pady=(8, 0))
        self.last_check_label = tb.Label(sched_box, text="", font=("Helvetica", 9), foreground="#495057")
        self.last_check_label.pack(anchor="w", pady=(10, 0))

        # --- Log ---
        log_card = Card(self, title="Reminder Log", icon="📜")
        log_card.pack(fill="both", expand=True)
        log_box = log_card.body
        cols = ("sent_at", "title", "patron", "due_date", "offset", "status", "to_email", "error")
        headers = {"sent_at": "When", "title": "Book", "patron": "Patron", "due_date": "Due Date",
                   "offset": "Offset", "status": "Status", "to_email": "Sent To", "error": "Error"}
        widths = {"sent_at": 130, "title": 160, "patron": 120, "due_date": 90, "offset": 60,
                  "status": 110, "to_email": 160, "error": 160}
        self.log_tree = tb.Treeview(log_box, columns=cols, show="headings", height=8)
        for c in cols:
            self.log_tree.heading(c, text=headers[c])
            self.log_tree.column(c, width=widths[c], anchor="w")
        self.log_tree.tag_configure("failed", foreground="#c92a2a")
        self.log_tree.tag_configure("skipped_no_email", foreground="#e67700")
        vsb = tb.Scrollbar(log_box, orient="vertical", command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=vsb.set)
        self.log_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

    # ------------------------------------------------------------------
    def _parse_offsets(self):
        raw = self.offsets_var.get().strip()
        offsets = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                offsets.append(int(part))
            except ValueError:
                raise ValueError(f"'{part}' is not a whole number.")
        return offsets

    def _collect_settings_from_form(self):
        try:
            port = int(self.e_port.get().strip() or 587)
        except ValueError:
            raise ValueError("Port must be a number.")
        offsets = self._parse_offsets()
        return dict(
            smtp_host=self.e_host.get().strip(),
            smtp_port=port,
            smtp_security=self.security_var.get(),
            smtp_username=self.e_user.get().strip(),
            smtp_password=self.e_pass.get(),
            from_email=self.e_from_email.get().strip(),
            from_name=self.e_from_name.get().strip() or "Library",
            library_name=self.e_library_name.get().strip() or "Your Library",
            reminders_enabled=self.enabled_var.get(),
            reminder_offsets=offsets,
        )

    def _save_settings(self):
        try:
            values = self._collect_settings_from_form()
        except ValueError as e:
            messagebox.showerror("Invalid schedule", str(e))
            return
        self.settings.update(**values)
        self.settings.save()
        self.status_bar.show("Reminder settings saved.", "success")

    def _send_test_email(self):
        try:
            values = self._collect_settings_from_form()
        except ValueError as e:
            messagebox.showerror("Invalid schedule", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title("Send Test Email")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        frm = tb.Frame(dlg, padding=16)
        frm.pack()
        addr = labeled_entry(frm, "Send test to:", 0, width=32)
        result_label = tb.Label(frm, text="")
        result_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        def do_send():
            self.settings.update(**values)  # use current form values, without requiring Save first
            success, error = email_utils.send_email(
                self.settings, addr.get().strip(),
                f"Test email from {config.APP_TITLE}",
                "If you're reading this, your SMTP settings are working correctly.",
            )
            if success:
                result_label.configure(text="Sent successfully!", foreground="#2f9e44")
            else:
                result_label.configure(text=f"Failed: {error}", foreground="#c92a2a")

        tb.Button(frm, text="Send", command=do_send, bootstyle="primary").grid(
            row=2, column=0, columnspan=2, pady=(10, 0), sticky="ew")

    def _check_now(self):
        try:
            values = self._collect_settings_from_form()
        except ValueError as e:
            messagebox.showerror("Invalid schedule", str(e))
            return
        self.settings.update(**values)
        self.settings.save()

        if not self.settings.smtp_configured:
            messagebox.showwarning("Not configured", "Enter and save your SMTP server and from-address first.")
            return

        # Force this run regardless of the enabled toggle, since the user explicitly asked.
        forced = dict(self.settings.as_dict())
        forced["reminders_enabled"] = True

        class _Shim:
            def get(self, key, default=None):
                return forced.get(key, default)

        results = reminder_engine.run_reminder_check(self.db, _Shim())
        sent = sum(1 for r in results if r["status"] == "sent")
        failed = sum(1 for r in results if r["status"] == "failed")
        skipped = sum(1 for r in results if r["status"] == "skipped_no_email")
        msg = f"Checked. {sent} sent, {failed} failed, {skipped} skipped (no email)."
        self.last_check_label.configure(text=msg)
        self.status_bar.show(msg, "success" if failed == 0 else "error")
        self.refresh_log()

    def _open_template_editor(self):
        EmailTemplateDialog(self, self.settings, self.status_bar)

    def refresh_log(self):
        self.log_tree.delete(*self.log_tree.get_children())
        for r in self.db.recent_reminders(100):
            tags = (r["status"],) if r["status"] in ("failed", "skipped_no_email") else ()
            self.log_tree.insert("", "end", values=(
                r["sent_at"], r["title"], r["patron_name_snapshot"], r["due_date"],
                r["offset_days"], r["status"], r["to_email"] or "", r["error"] or ""
            ), tags=tags)
        restripe(self.log_tree)
