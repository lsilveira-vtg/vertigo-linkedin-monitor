"""Configuracao central — le todas as variaveis de ambiente."""
import os

from dotenv import load_dotenv

load_dotenv()

# LinkedIn
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_ACCOUNT_ID = os.getenv("LINKEDIN_ACCOUNT_ID", "")

# Google
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")

# E-mail
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "")
REPORT_RECIPIENTS = [e.strip() for e in os.getenv("REPORT_RECIPIENTS", "").split(",") if e.strip()]
APPROVED_APPROVERS = [e.strip() for e in os.getenv("APPROVED_APPROVERS", "").split(",") if e.strip()]

# Discord
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID", "")

# Abas da planilha
SHEET_TABS = [
    "Campanhas",
    "Anúncios",
    "Budget Mensal",
    "Histórico Semanal",
    "Histórico Mensal",
    "Recomendações",
]
