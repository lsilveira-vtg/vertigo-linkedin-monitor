"""Configuracao central — le todas as variaveis de ambiente."""
import os

from dotenv import load_dotenv

load_dotenv()

# LinkedIn
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
# Refresh token (vale ~1 ano) — usado para gerar um access token novo a cada
# execução, evitando que a coleta quebre quando o access token expira (~60 dias).
LINKEDIN_REFRESH_TOKEN = os.getenv("LINKEDIN_REFRESH_TOKEN", "")
LINKEDIN_ACCOUNT_ID = os.getenv("LINKEDIN_ACCOUNT_ID", "")

# Google
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")

# URL pública do painel/relatório (para links nos e-mails)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://midiapaga-api.vtgdev.net").rstrip("/")

# E-mail
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
REPORT_RECIPIENTS = [e.strip() for e in os.getenv("REPORT_RECIPIENTS", "").split(",") if e.strip()]
APPROVED_APPROVERS = [e.strip() for e in os.getenv("APPROVED_APPROVERS", "").split(",") if e.strip()]

# Discord
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID", "")
# Webhook do canal (posta reports automaticamente, sem precisar do bot rodando 24/7)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Anthropic (camada de análise por IA — opcional; sem chave usa o motor próprio)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANALYST_MODEL = os.getenv("ANALYST_MODEL", "claude-sonnet-5-5")
# Orçamento mensal de referência da chave (USD) — usado no contador de custo
ANTHROPIC_MONTHLY_BUDGET_USD = float(os.getenv("ANTHROPIC_MONTHLY_BUDGET_USD", "5"))

# Abas da planilha
SHEET_TABS = [
    "Campanhas",
    "Anúncios",
    "Budget Mensal",
    "Histórico Semanal",
    "Histórico Mensal",
    "Recomendações",
]
