import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


def send_email(to, subject, body):
    """Send a plain-text email. With no MAIL_SERVER set, the message is printed to the log instead."""
    cfg = current_app.config
    if not cfg.get("MAIL_SERVER"):
        current_app.logger.warning("MAIL_SERVER not set. Email NOT sent.\nTo: %s\nSubject: %s\n\n%s", to, subject, body)
        return True

    msg = EmailMessage()
    msg["From"] = cfg["MAIL_FROM"] or cfg.get("MAIL_USERNAME")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        if cfg["MAIL_USE_SSL"]:
            server = smtplib.SMTP_SSL(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15,
                                      context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15)
            if cfg["MAIL_USE_TLS"]:
                server.starttls(context=ssl.create_default_context())
        with server:
            if cfg.get("MAIL_USERNAME"):
                server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            server.send_message(msg)
        return True
    except Exception:
        current_app.logger.exception("Could not send email to %s", to)
        return False