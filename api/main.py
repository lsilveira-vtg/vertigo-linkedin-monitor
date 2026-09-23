"""API do dashboard do agente de mídia paga.

Roda ao lado do bot (mesma máquina/compose). O nginx da Vertigo faz o HTTPS e o
proxy para a porta interna (padrão 8000). Autenticação: login Google do Workspace
(verifica o ID token e o domínio); em desenvolvimento aceita um token estático
(API_TOKEN) para testar antes do Google estar configurado.

Endpoints:
  GET  /api/health     — sem auth, para o healthcheck
  GET  /api/dashboard  — dados do painel (KPIs, campanhas, orçamento, análise)
  POST /api/ask        — pergunta ao vivo ao agente  { "question": "..." }

Variáveis de ambiente:
  API_PORT             porta interna (default 8000)
  ALLOWED_ORIGIN       origem do painel para o CORS (ex.: https://vtglink.demo.vtgdev.net)
  GOOGLE_OAUTH_CLIENT_ID  client id do Workspace (quando presente, exige login Google)
  ALLOWED_EMAIL_DOMAIN dominio aceito (default vertigo.com.br)
  API_TOKEN            token estático de teste (usado só se GOOGLE_OAUTH_CLIENT_ID não estiver setado)
"""
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src import dashboard_data, analyst_ai
from src.report_builder import collect_campaign_data

STATIC = Path(__file__).parent / "static"

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")
ALLOWED_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "vertigo.com.br")
CACHE_TTL = int(os.getenv("DASHBOARD_CACHE_TTL", "600"))  # 10 min

app = FastAPI(title="Agente Mídia Paga — API", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN] if ALLOWED_ORIGIN != "*" else ["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

_cache: dict = {"ts": 0, "raw": None, "dash": None}


# ---------- autenticação ----------
def current_user(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Faltou o token (Authorization: Bearer …).")
    token = authorization[7:].strip()

    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    if client_id:
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as grequests
            info = id_token.verify_oauth2_token(token, grequests.Request(), client_id)
        except Exception:
            raise HTTPException(401, "Login Google inválido ou expirado.")
        email = (info.get("email") or "").lower()
        if not info.get("email_verified") or not email.endswith("@" + ALLOWED_DOMAIN):
            raise HTTPException(403, "Acesso restrito à organização.")
        return email

    dev_token = os.getenv("API_TOKEN", "")
    if dev_token and token == dev_token:
        return f"dev@{ALLOWED_DOMAIN}"
    raise HTTPException(401, "Token inválido.")


# ---------- dados (com cache curto para não martelar o LinkedIn) ----------
def _period():
    end = date.today() - timedelta(days=1)
    start = end.replace(day=1)
    return start, end


def _load(force: bool = False):
    if not force and _cache["dash"] and (time.time() - _cache["ts"] < CACHE_TTL):
        return _cache["raw"], _cache["dash"]
    start, end = _period()
    raw = collect_campaign_data(start, end)
    dash = dashboard_data.build_dashboard_data(start, end, ref_date=end, data=raw)
    _cache.update(ts=time.time(), raw=raw, dash=dash)
    return raw, dash


# ---------- rotas ----------
@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config_public():
    """Config pública para o frontend (o client_id do Google não é segredo)."""
    return {"google_client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""), "domain": ALLOWED_DOMAIN}


@app.get("/api/dashboard")
def dashboard(_: str = Depends(current_user)):
    _, dash = _load()
    return dash


class Pergunta(BaseModel):
    question: str


@app.post("/api/ask")
def ask(p: Pergunta, user: str = Depends(current_user)):
    q = (p.question or "").strip()
    if not q:
        raise HTTPException(422, "Pergunta vazia.")
    raw, dash = _load()
    resposta = analyst_ai.answer_question(q, raw, dash.get("budget"))
    return {"answer": resposta, "asked_by": user}
