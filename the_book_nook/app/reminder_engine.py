"""
Orchestrates due-date reminder emails: for each configured offset (e.g.
3 days before due, on due date, 3/7 days overdue), finds active checkouts
that match and haven't already been processed for that offset, and sends
(or logs why it couldn't send) each one.
"""
from app import email_utils


def run_reminder_check(db, settings):
    """
    Runs one reminder pass. Returns a list of result dicts:
      {"title": ..., "patron": ..., "offset": ..., "status": "sent"/"failed"/"skipped_no_email", "error": ...}
    Safe to call repeatedly (e.g. every hour) -- already-processed
    (transaction, offset) pairs are skipped via reminders_log.
    """
    results = []
    if not settings.get("reminders_enabled"):
        return results

    offsets = settings.get("reminder_offsets") or []

    for offset in offsets:
        for txn in db.transactions_for_offset(offset):
            if db.reminder_already_processed(txn["id"], offset):
                continue

            email = (txn.get("patron_contact_snapshot") or "").strip()
            result = {"title": txn["title"], "patron": txn["patron_name_snapshot"],
                      "offset": offset, "due_date": txn["due_date"]}

            if not email_utils.looks_like_email(email):
                db.log_reminder(txn["id"], offset, email or None, "skipped_no_email")
                result.update(status="skipped_no_email", error=None)
                results.append(result)
                continue

            subject, body = email_utils.build_reminder_message(txn, txn, offset, settings)
            success, error = email_utils.send_email(settings, email, subject, body)
            status = "sent" if success else "failed"
            db.log_reminder(txn["id"], offset, email, status, error)
            result.update(status=status, error=error)
            results.append(result)

    return results
