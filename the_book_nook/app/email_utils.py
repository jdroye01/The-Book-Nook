"""
Sends due-date reminder emails over SMTP using whatever email account the
library has (Gmail, Outlook, a hosting provider's SMTP, etc.) Nothing is
sent through a third-party service -- it's a direct SMTP connection using
credentials the librarian enters in the Reminders tab.

Email wording is customizable per reminder scenario (before due / due
today / overdue) via Settings -> "email_templates". See
DEFAULT_EMAIL_TEMPLATES below for the fallback wording and available
{placeholders}.
"""
import re
import smtplib
import ssl
from email.message import EmailMessage

import certifi

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# One editable template per reminder scenario. offset_days convention used
# throughout the app: negative = before due, 0 = due today, positive = overdue.
DEFAULT_EMAIL_TEMPLATES = {
    "before_due": {
        "subject": "Reminder: '{title}' is due in {days_phrase}",
        "body": (
            "Hi {patron_name},\n\n"
            "This is a friendly reminder that your book is due back in {days_phrase}.\n\n"
            "    Title:     {title}\n"
            "    Author:    {author}\n"
            "    Due date:  {due_date}\n\n"
            "Please return or renew it at your earliest convenience.\n\n"
            "Thank you,\n{library_name}\n"
        ),
    },
    "due_today": {
        "subject": "'{title}' is due today",
        "body": (
            "Hi {patron_name},\n\n"
            "This is a reminder that your book is due back today.\n\n"
            "    Title:     {title}\n"
            "    Author:    {author}\n"
            "    Due date:  {due_date}\n\n"
            "Please return or renew it at your earliest convenience.\n\n"
            "Thank you,\n{library_name}\n"
        ),
    },
    "overdue": {
        "subject": "Overdue: '{title}' was due {days_phrase} ago",
        "body": (
            "Hi {patron_name},\n\n"
            "Our records show this book is now {days_phrase} overdue.\n\n"
            "    Title:     {title}\n"
            "    Author:    {author}\n"
            "    Due date:  {due_date}\n\n"
            "Please return or renew it at your earliest convenience.\n\n"
            "Thank you,\n{library_name}\n"
        ),
    },
}

# Shown to the librarian in the template editor so they know what's available.
PLACEHOLDER_HELP = [
    ("{patron_name}", "The patron's name"),
    ("{title}", "Book title"),
    ("{author}", "Book author"),
    ("{due_date}", "Due date (YYYY-MM-DD)"),
    ("{library_name}", "Your library's name (set below)"),
    ("{days_phrase}", 'A friendly phrase, e.g. "3 days" or "1 day"'),
    ("{days}", "Just the number, e.g. 3"),
]

SCENARIO_LABELS = {
    "before_due": "Before Due",
    "due_today": "Due Today",
    "overdue": "Overdue",
}


class _SafeDict(dict):
    """Lets str.format_map leave unrecognized {placeholders} in the text
    as-is instead of raising -- so a librarian's typo shows up visibly in
    a preview/sent email rather than crashing the whole reminder run."""
    def __missing__(self, key):
        return "{" + key + "}"


def scenario_for_offset(offset_days):
    if offset_days < 0:
        return "before_due"
    elif offset_days == 0:
        return "due_today"
    else:
        return "overdue"


def render_template(template_str, values):
    return (template_str or "").format_map(_SafeDict(values))


def build_placeholder_values(book, transaction, offset_days, library_name):
    days = abs(offset_days)
    days_phrase = f"{days} day" + ("s" if days != 1 else "")
    return {
        "patron_name": transaction.get("patron_name_snapshot", ""),
        "title": book.get("title", ""),
        "author": book.get("author", ""),
        "due_date": transaction.get("due_date", ""),
        "library_name": library_name,
        "days": days,
        "days_phrase": days_phrase,
    }


def build_reminder_message(book, transaction, offset_days, settings):
    """
    Returns (subject, body) for a reminder email, using the librarian's
    customized templates (Settings -> "email_templates") if set, falling
    back to DEFAULT_EMAIL_TEMPLATES for anything not customized.
    """
    library_name = settings.get("library_name") or "Your Library"
    templates = settings.get("email_templates") or {}
    scenario = scenario_for_offset(offset_days)
    default_tmpl = DEFAULT_EMAIL_TEMPLATES[scenario]
    tmpl = templates.get(scenario) or {}

    values = build_placeholder_values(book, transaction, offset_days, library_name)
    subject = render_template(tmpl.get("subject") or default_tmpl["subject"], values)
    body = render_template(tmpl.get("body") or default_tmpl["body"], values)
    return subject, body


def looks_like_email(value):
    return bool(value and EMAIL_RE.match(value.strip()))


def _ssl_context():
    """
    A default SSL context can fail with CERTIFICATE_VERIFY_FAILED on macOS
    when Python was installed from python.org, because that build ships its
    own OpenSSL that doesn't see the system's trusted certificates. Loading
    certifi's CA bundle explicitly sidesteps that regardless of how Python
    was installed or which OS this runs on.
    """
    return ssl.create_default_context(cafile=certifi.where())


def send_email(settings, to_email, subject, body):
    """
    Send a single email using the given Settings object.
    Returns (success: bool, error_message: str or None).
    """
    host = settings.get("smtp_host")
    port = int(settings.get("smtp_port") or 587)
    security = settings.get("smtp_security", "starttls")
    username = settings.get("smtp_username")
    password = settings.get("smtp_password")
    from_email = settings.get("from_email")
    from_name = settings.get("from_name") or "Library"

    if not host or not from_email:
        return False, "SMTP is not configured yet (missing server or from-address)."
    if not looks_like_email(to_email):
        return False, f"'{to_email}' doesn't look like a valid email address."

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg.set_content(body)

    try:
        if security == "ssl":
            context = _ssl_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as server:
                if username:
                    server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                if security == "starttls":
                    server.starttls(context=_ssl_context())
                if username:
                    server.login(username, password)
                server.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)
