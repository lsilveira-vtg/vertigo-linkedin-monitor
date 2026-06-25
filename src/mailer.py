"""Envio de e-mails via SMTP do Gmail (Senha de App).

Usa a conta GMAIL_SENDER autenticada por GMAIL_APP_PASSWORD (senha de app de
16 caracteres gerada em myaccount.google.com). Nao depende de delegacao do admin.
"""
import smtplib
from email.mime.text import MIMEText

from . import config

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_email(subject: str, body: str, recipients: list[str] | None = None) -> None:
    recipients = recipients or config.REPORT_RECIPIENTS
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = ", ".join(recipients)
    msg["From"] = config.GMAIL_SENDER
    msg["Subject"] = subject

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(config.GMAIL_SENDER, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_SENDER, recipients, msg.as_string())
