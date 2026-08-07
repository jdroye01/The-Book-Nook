"""
Database layer for the library system.
Everything the rest of the app needs to know about SQLite lives here -
the GUI code never writes raw SQL itself.
"""
import sqlite3
import datetime
from contextlib import contextmanager

from app import config


SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode         TEXT UNIQUE NOT NULL,
    isbn            TEXT,
    title           TEXT NOT NULL,
    author          TEXT NOT NULL,
    genre           TEXT,
    publisher       TEXT,
    pub_year        TEXT,
    shelf_location  TEXT,
    copies_total    INTEGER NOT NULL DEFAULT 1,
    copies_available INTEGER NOT NULL DEFAULT 1,
    date_added      TEXT NOT NULL,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS patrons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    contact     TEXT,
    date_added  TEXT NOT NULL,
    UNIQUE(name, contact)
);

CREATE TABLE IF NOT EXISTS transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id             INTEGER NOT NULL REFERENCES books(id),
    patron_id           INTEGER REFERENCES patrons(id),
    patron_name_snapshot TEXT NOT NULL,
    patron_contact_snapshot TEXT,
    checkout_date       TEXT NOT NULL,
    due_date            TEXT NOT NULL,
    return_date         TEXT,
    status              TEXT NOT NULL DEFAULT 'checked_out'
);

CREATE TABLE IF NOT EXISTS reminders_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  INTEGER NOT NULL REFERENCES transactions(id),
    offset_days     INTEGER NOT NULL,
    to_email        TEXT,
    status          TEXT NOT NULL,   -- 'sent', 'failed', 'skipped_no_email'
    error           TEXT,
    sent_at         TEXT NOT NULL,
    UNIQUE(transaction_id, offset_days)
);

CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
CREATE INDEX IF NOT EXISTS idx_books_author ON books(author);
CREATE INDEX IF NOT EXISTS idx_books_barcode ON books(barcode);
CREATE INDEX IF NOT EXISTS idx_txn_book ON transactions(book_id);
CREATE INDEX IF NOT EXISTS idx_txn_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_reminders_txn ON reminders_log(transaction_id);
"""


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str():
    return datetime.date.today().isoformat()


class LibraryDB:
    def __init__(self, path=None):
        self.path = path or config.DB_PATH
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    # ------------------------------------------------------------------
    # Barcode helpers
    # ------------------------------------------------------------------
    def next_barcode(self):
        """Generate the next sequential internal barcode, e.g. LIB000042."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT barcode FROM books WHERE barcode LIKE ? ORDER BY id DESC LIMIT 1",
                (f"{config.BARCODE_PREFIX}%",),
            ).fetchone()
        if row is None:
            n = 1
        else:
            try:
                n = int(row["barcode"].replace(config.BARCODE_PREFIX, "")) + 1
            except ValueError:
                n = 1
        return f"{config.BARCODE_PREFIX}{n:06d}"

    def barcode_exists(self, barcode):
        with self._conn() as conn:
            row = conn.execute("SELECT 1 FROM books WHERE barcode = ?", (barcode,)).fetchone()
        return row is not None

    # ------------------------------------------------------------------
    # Books: CRUD
    # ------------------------------------------------------------------
    def add_book(self, title, author, genre="", isbn="", publisher="", pub_year="",
                 shelf_location="", copies_total=1, notes="", barcode=None):
        title = title.strip()
        author = author.strip()
        if not title or not author:
            raise ValueError("Title and author are required.")
        copies_total = max(1, int(copies_total))
        barcode = barcode or self.next_barcode()
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO books
                   (barcode, isbn, title, author, genre, publisher, pub_year,
                    shelf_location, copies_total, copies_available, date_added, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (barcode, isbn.strip(), title, author, genre.strip(), publisher.strip(),
                 str(pub_year).strip(), shelf_location.strip(), copies_total, copies_total,
                 now_str(), notes.strip()),
            )
            return cur.lastrowid

    def update_book(self, book_id, **fields):
        if not fields:
            return
        allowed = {"isbn", "title", "author", "genre", "publisher", "pub_year",
                   "shelf_location", "copies_total", "notes", "barcode"}
        sets, values = [], []
        for k, v in fields.items():
            if k in allowed:
                sets.append(f"{k} = ?")
                values.append(v)
        if not sets:
            return
        values.append(book_id)
        with self._conn() as conn:
            conn.execute(f"UPDATE books SET {', '.join(sets)} WHERE id = ?", values)

    def set_copies_available(self, book_id, copies_available):
        with self._conn() as conn:
            conn.execute("UPDATE books SET copies_available = ? WHERE id = ?",
                         (max(0, copies_available), book_id))

    def delete_book(self, book_id):
        with self._conn() as conn:
            active = conn.execute(
                "SELECT COUNT(*) c FROM transactions WHERE book_id=? AND status='checked_out'",
                (book_id,),
            ).fetchone()["c"]
            if active:
                raise ValueError("Cannot delete a book that is currently checked out.")
            conn.execute("DELETE FROM transactions WHERE book_id = ?", (book_id,))
            conn.execute("DELETE FROM books WHERE id = ?", (book_id,))

    def get_book(self, book_id):
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        return dict(row) if row else None

    def get_book_by_barcode(self, barcode):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM books WHERE barcode = ? OR isbn = ?", (barcode, barcode)
            ).fetchone()
        return dict(row) if row else None

    def all_books(self):
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM books ORDER BY title").fetchall()
        return [dict(r) for r in rows]

    def search_books(self, query="", field="All"):
        """Search across title/author/genre/barcode/isbn, or a single field."""
        query = f"%{query.strip()}%"
        clauses = {
            "Title": "title LIKE ?",
            "Author": "author LIKE ?",
            "Genre": "genre LIKE ?",
            "Barcode/ISBN": "(barcode LIKE ? OR isbn LIKE ?)",
        }
        with self._conn() as conn:
            if field == "All" or not field:
                sql = ("SELECT * FROM books WHERE title LIKE ? OR author LIKE ? "
                       "OR genre LIKE ? OR barcode LIKE ? OR isbn LIKE ? ORDER BY title")
                params = (query, query, query, query, query)
            elif field == "Barcode/ISBN":
                sql = f"SELECT * FROM books WHERE {clauses[field]} ORDER BY title"
                params = (query, query)
            else:
                sql = f"SELECT * FROM books WHERE {clauses.get(field, 'title LIKE ?')} ORDER BY title"
                params = (query,)
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def distinct_genres(self):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT genre FROM books WHERE genre IS NOT NULL AND genre != ''"
            ).fetchall()
        genres = set()
        for r in rows:
            for g in r["genre"].split(","):
                g = g.strip()
                if g:
                    genres.add(g)
        return sorted(genres)

    # ------------------------------------------------------------------
    # Patrons
    # ------------------------------------------------------------------
    def get_or_create_patron(self, name, contact=""):
        name = name.strip()
        contact = contact.strip()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM patrons WHERE name = ? AND contact = ?", (name, contact)
            ).fetchone()
            if row:
                return dict(row)
            cur = conn.execute(
                "INSERT INTO patrons (name, contact, date_added) VALUES (?, ?, ?)",
                (name, contact, now_str()),
            )
            return {"id": cur.lastrowid, "name": name, "contact": contact}

    def search_patrons(self, query):
        query = f"%{query.strip()}%"
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM patrons WHERE name LIKE ? OR contact LIKE ? ORDER BY name",
                (query, query),
            ).fetchall()
        return [dict(r) for r in rows]

    def patrons_matching_name_prefix(self, prefix, limit=8):
        """Used for the checkout form's name autocomplete -- patrons whose
        name starts with what's been typed so far, best match first."""
        prefix = prefix.strip()
        if not prefix:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM patrons WHERE name LIKE ? ORDER BY name LIMIT ?",
                (f"{prefix}%", limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def find_patron_by_exact_name(self, name):
        """Returns (patron_dict_or_None, is_ambiguous). is_ambiguous is True
        if more than one patron shares this exact name (case-insensitive) --
        callers should treat that as "needs a human to sort out" rather
        than silently picking one."""
        name = name.strip()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM patrons WHERE name = ? COLLATE NOCASE", (name,)
            ).fetchall()
        if len(rows) == 1:
            return dict(rows[0]), False
        if len(rows) > 1:
            return None, True
        return None, False

    def all_patrons(self):
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM patrons ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    def get_patron(self, patron_id):
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM patrons WHERE id = ?", (patron_id,)).fetchone()
        return dict(row) if row else None

    def add_patron(self, name, contact=""):
        name = name.strip()
        contact = contact.strip()
        if not name:
            raise ValueError("Patron name is required.")
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO patrons (name, contact, date_added) VALUES (?, ?, ?)",
                (name, contact, now_str()),
            )
            return cur.lastrowid

    def update_patron(self, patron_id, name=None, contact=None):
        sets, values = [], []
        if name is not None:
            sets.append("name = ?")
            values.append(name.strip())
        if contact is not None:
            sets.append("contact = ?")
            values.append(contact.strip())
        if not sets:
            return
        values.append(patron_id)
        with self._conn() as conn:
            conn.execute(f"UPDATE patrons SET {', '.join(sets)} WHERE id = ?", values)

    def delete_patron(self, patron_id):
        with self._conn() as conn:
            active = conn.execute(
                "SELECT COUNT(*) c FROM transactions WHERE patron_id=? AND status='checked_out'",
                (patron_id,),
            ).fetchone()["c"]
            if active:
                raise ValueError("Cannot delete a patron with a book currently checked out.")
            conn.execute("UPDATE transactions SET patron_id = NULL WHERE patron_id = ?", (patron_id,))
            conn.execute("DELETE FROM patrons WHERE id = ?", (patron_id,))

    def import_or_update_patron(self, name, contact=""):
        """
        Used by the patron CSV importer: finds an existing patron by exact
        (case-insensitive) name and updates their contact if a new one was
        given, rather than creating a duplicate row for the same person.
        Returns a status string: "created", "updated", "unchanged", or
        "skipped_ambiguous" (more than one existing patron shares this name
        -- left alone rather than guessing which one to update).
        """
        name = name.strip()
        contact = contact.strip()
        if not name:
            raise ValueError("Patron name is required.")

        existing, ambiguous = self.find_patron_by_exact_name(name)
        if ambiguous:
            return "skipped_ambiguous"
        if existing:
            if contact and contact != (existing.get("contact") or ""):
                self.update_patron(existing["id"], contact=contact)
                return "updated"
            return "unchanged"
        self.add_patron(name, contact)
        return "created"

    def patron_history(self, patron_id):
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT t.*, b.title, b.author FROM transactions t
                   JOIN books b ON b.id = t.book_id
                   WHERE t.patron_id = ? ORDER BY t.checkout_date DESC""",
                (patron_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def patron_active_checkout_count(self, patron_id):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) c FROM transactions WHERE patron_id=? AND status='checked_out'",
                (patron_id,),
            ).fetchone()
        return row["c"]

    # ------------------------------------------------------------------
    # Checkout / check-in
    # ------------------------------------------------------------------
    def checkout_book(self, barcode, patron_name, patron_contact="", loan_days=None):
        loan_days = loan_days if loan_days is not None else config.DEFAULT_LOAN_DAYS
        book = self.get_book_by_barcode(barcode)
        if not book:
            raise ValueError(f"No book found for barcode/ISBN '{barcode}'.")
        if book["copies_available"] <= 0:
            raise ValueError(f"All copies of '{book['title']}' are already checked out.")

        patron = self.get_or_create_patron(patron_name, patron_contact)
        due = (datetime.date.today() + datetime.timedelta(days=loan_days)).isoformat()

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO transactions
                   (book_id, patron_id, patron_name_snapshot, patron_contact_snapshot,
                    checkout_date, due_date, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'checked_out')""",
                (book["id"], patron["id"], patron["name"], patron["contact"],
                 today_str(), due),
            )
            conn.execute(
                "UPDATE books SET copies_available = copies_available - 1 WHERE id = ?",
                (book["id"],),
            )
        return {"book": book, "patron": patron, "due_date": due}

    def checkin_book(self, barcode):
        book = self.get_book_by_barcode(barcode)
        if not book:
            raise ValueError(f"No book found for barcode/ISBN '{barcode}'.")
        with self._conn() as conn:
            row = conn.execute(
                """SELECT * FROM transactions WHERE book_id = ? AND status = 'checked_out'
                   ORDER BY checkout_date LIMIT 1""",
                (book["id"],),
            ).fetchone()
            if not row:
                raise ValueError(f"'{book['title']}' is not currently checked out.")
            conn.execute(
                "UPDATE transactions SET return_date = ?, status = 'returned' WHERE id = ?",
                (today_str(), row["id"]),
            )
            conn.execute(
                "UPDATE books SET copies_available = copies_available + 1 WHERE id = ?",
                (book["id"],),
            )
        return {"book": book, "transaction": dict(row)}

    def active_checkouts(self):
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT t.*, b.title, b.author, b.barcode FROM transactions t
                   JOIN books b ON b.id = t.book_id
                   WHERE t.status = 'checked_out' ORDER BY t.due_date"""
            ).fetchall()
        return [dict(r) for r in rows]

    def active_checkouts_for_book(self, book_id):
        """All currently-checked-out loans of a specific book (there can be
        several at once if it has multiple copies)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT t.*, b.title, b.author, b.barcode FROM transactions t
                   JOIN books b ON b.id = t.book_id
                   WHERE t.book_id = ? AND t.status = 'checked_out'
                   ORDER BY t.due_date""",
                (book_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_transaction(self, transaction_id):
        with self._conn() as conn:
            row = conn.execute(
                """SELECT t.*, b.title, b.author, b.barcode FROM transactions t
                   JOIN books b ON b.id = t.book_id WHERE t.id = ?""",
                (transaction_id,),
            ).fetchone()
        return dict(row) if row else None

    def checkin_transaction(self, transaction_id):
        """Check in one specific loan by its transaction id -- lets staff
        return a particular copy early even if other copies of the same
        book are still out or available."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM transactions WHERE id = ? AND status = 'checked_out'",
                (transaction_id,),
            ).fetchone()
            if not row:
                raise ValueError("That loan is not currently checked out (it may already be returned).")
            conn.execute(
                "UPDATE transactions SET return_date = ?, status = 'returned' WHERE id = ?",
                (today_str(), transaction_id),
            )
            conn.execute(
                "UPDATE books SET copies_available = copies_available + 1 WHERE id = ?",
                (row["book_id"],),
            )
        return dict(row)

    def update_transaction_contact(self, transaction_id, patron_name=None, patron_contact=None):
        """
        Update the patron name/contact recorded on an active (or past) loan --
        e.g. to add an email after checkout so due-date reminders can reach
        them. Also updates the linked patron record, if any, so future
        checkouts remember it too.
        """
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
            if not row:
                raise ValueError("Loan not found.")

            sets, values = [], []
            if patron_name is not None:
                sets.append("patron_name_snapshot = ?")
                values.append(patron_name)
            if patron_contact is not None:
                sets.append("patron_contact_snapshot = ?")
                values.append(patron_contact)
            if sets:
                values.append(transaction_id)
                conn.execute(f"UPDATE transactions SET {', '.join(sets)} WHERE id = ?", values)

            if row["patron_id"]:
                p_sets, p_values = [], []
                if patron_name is not None:
                    p_sets.append("name = ?")
                    p_values.append(patron_name)
                if patron_contact is not None:
                    p_sets.append("contact = ?")
                    p_values.append(patron_contact)
                if p_sets:
                    p_values.append(row["patron_id"])
                    conn.execute(f"UPDATE patrons SET {', '.join(p_sets)} WHERE id = ?", p_values)

        # If a usable email was just added, let already-skipped reminders retry.
        from app import email_utils
        if patron_contact is not None and email_utils.looks_like_email(patron_contact):
            with self._conn() as conn:
                conn.execute(
                    "DELETE FROM reminders_log WHERE transaction_id = ? AND status = 'skipped_no_email'",
                    (transaction_id,),
                )

    def overdue_checkouts(self):
        today = today_str()
        return [t for t in self.active_checkouts() if t["due_date"] < today]

    def recent_activity(self, limit=25):
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT t.*, b.title, b.author FROM transactions t
                   JOIN books b ON b.id = t.book_id
                   ORDER BY t.id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Due-date reminders
    # ------------------------------------------------------------------
    def transactions_for_offset(self, offset_days):
        """
        Active checkouts whose due date is exactly `offset_days` away from
        today (negative = before due, 0 = due today, positive = overdue by
        that many days).
        """
        target_due = (datetime.date.today() - datetime.timedelta(days=offset_days)).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT t.*, b.title, b.author, b.barcode FROM transactions t
                   JOIN books b ON b.id = t.book_id
                   WHERE t.status = 'checked_out' AND t.due_date = ?""",
                (target_due,),
            ).fetchall()
        return [dict(r) for r in rows]

    def reminder_already_processed(self, transaction_id, offset_days):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM reminders_log WHERE transaction_id = ? AND offset_days = ?",
                (transaction_id, offset_days),
            ).fetchone()
        return row is not None

    def log_reminder(self, transaction_id, offset_days, to_email, status, error=None):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO reminders_log (transaction_id, offset_days, to_email, status, error, sent_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(transaction_id, offset_days) DO UPDATE SET
                       to_email=excluded.to_email, status=excluded.status,
                       error=excluded.error, sent_at=excluded.sent_at""",
                (transaction_id, offset_days, to_email, status, error, now_str()),
            )

    def clear_reminder_log_entry(self, transaction_id, offset_days):
        """Remove a log entry so that offset will be retried on the next check."""
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM reminders_log WHERE transaction_id = ? AND offset_days = ?",
                (transaction_id, offset_days),
            )

    def recent_reminders(self, limit=50):
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT r.*, t.patron_name_snapshot, t.due_date, b.title FROM reminders_log r
                   JOIN transactions t ON t.id = r.transaction_id
                   JOIN books b ON b.id = t.book_id
                   ORDER BY r.id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    def stats(self):
        with self._conn() as conn:
            total_titles = conn.execute("SELECT COUNT(*) c FROM books").fetchone()["c"]
            total_copies = conn.execute(
                "SELECT COALESCE(SUM(copies_total),0) c FROM books"
            ).fetchone()["c"]
            checked_out = conn.execute(
                "SELECT COUNT(*) c FROM transactions WHERE status='checked_out'"
            ).fetchone()["c"]
        return {
            "total_titles": total_titles,
            "total_copies": total_copies,
            "checked_out": checked_out,
            "overdue": len(self.overdue_checkouts()),
        }

    # ------------------------------------------------------------------
    # Dashboard analytics
    # ------------------------------------------------------------------
    def top_borrowed_books(self, limit=5):
        """Most-borrowed titles of all time, by number of checkouts."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT b.id, b.title, b.author, COUNT(t.id) AS times_borrowed
                   FROM transactions t JOIN books b ON b.id = t.book_id
                   GROUP BY b.id ORDER BY times_borrowed DESC, b.title LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def activity_last_n_days(self, n=7):
        """Per-day checkout/return counts for the last n days (oldest first)."""
        today = datetime.date.today()
        days = [(today - datetime.timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]
        start = days[0]
        with self._conn() as conn:
            co_rows = conn.execute(
                "SELECT checkout_date AS d, COUNT(*) c FROM transactions "
                "WHERE checkout_date >= ? GROUP BY checkout_date", (start,),
            ).fetchall()
            rt_rows = conn.execute(
                "SELECT return_date AS d, COUNT(*) c FROM transactions "
                "WHERE return_date >= ? GROUP BY return_date", (start,),
            ).fetchall()
        co_map = {r["d"]: r["c"] for r in co_rows}
        rt_map = {r["d"]: r["c"] for r in rt_rows}
        return [{"date": d, "checkouts": co_map.get(d, 0), "returns": rt_map.get(d, 0)} for d in days]

    def week_summary(self):
        activity = self.activity_last_n_days(7)
        return {
            "checkouts": sum(a["checkouts"] for a in activity),
            "returns": sum(a["returns"] for a in activity),
        }
