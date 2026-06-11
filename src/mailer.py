"""Envio de e-mails via Gmail API usando a Service Account."""
import base64
import json
from email.mime.text import MIMEText

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from . import config

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _service():
    info = json.loads(config.GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    delegated = creds.with_subject(config.GMAIL_SENDER)
    return build("gmail", "v1", credentials=delegated)


def send_email(subject: str, body: str, recipients: list[str] | None = None) -> None:
    recipients = recipients or config.REPORT_RECIPIENTS
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = ", ".join(recipients)
    msg["From"] = config.GMAIL_SENDER
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    _service().users().messages().send(userId="me", body={"raw": raw}).execute()
