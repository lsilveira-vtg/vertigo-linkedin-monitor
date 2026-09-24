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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BRT = timezone(timedelta(hours=-3))

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src import dashboard_data, analyst_ai, chat_history, analysis_store
from src.report_builder import collect_campaign_data

STATIC = Path(__file__).parent / "static"

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")
ALLOWED_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "vertigo.com.br")
CACHE_TTL = int(os.getenv("DASHBOARD_CACHE_TTL", "600"))  # 10 min (KPIs/números)
# A análise da IA é gerada 1x por dia e persistida (ver analysis_store): todos veem
# a MESMA leitura ao longo do dia; ela renova quando vira o dia.

app = FastAPI(title="Agente Mídia Paga — API", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN] if ALLOWED_ORIGIN != "*" else ["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

_cache: dict = {"ts": 0, "raw": None, "dash": None}
_cache_ia: dict = {"ts": 0, "analysis": None}


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
    """Dados rápidos do painel (sem a IA): KPIs, orçamento, campanhas, gráficos.
    A análise aqui vem do motor de regras (instantânea)."""
    if not force and _cache["dash"] and (time.time() - _cache["ts"] < CACHE_TTL):
        return _cache["raw"], _cache["dash"]
    start, end = _period()
    raw = collect_campaign_data(start, end)
    dash = dashboard_data.build_dashboard_data(start, end, ref_date=end, data=raw, use_ia=False)
    _cache.update(ts=time.time(), raw=raw, dash=dash)
    return raw, dash


def _load_analise_ia(force: bool = False):
    """Análise rica por IA: gerada 1x por dia e persistida (igual para todos e
    estável ao longo do dia). Renova quando vira o dia."""
    today = datetime.now(BRT).date().isoformat()
    if not force and _cache_ia.get("analysis") and _cache_ia.get("day") == today:
        return _cache_ia["analysis"]
    if not force:
        try:
            stored = analysis_store.get(today)
        except Exception as exc:
            stored = None
            print(f"  aviso: não li a análise do dia: {exc}")
        if stored:
            _cache_ia.update(analysis=stored, day=today)
            return stored
    raw, _ = _load()
    start, end = _period()
    analise = dashboard_data.build_analysis_ia(start, end, ref_date=end, data=raw)
    analise["gerada_em"] = datetime.now(BRT).strftime("%d/%m %H:%M")
    try:
        analysis_store.save(today, analise["gerada_em"], analise)
    except Exception as exc:
        print(f"  aviso: não persisti a análise do dia: {exc}")
    _cache_ia.update(analysis=analise, day=today)
    return analise


# ---------- rotas ----------
@app.get("/")
def index():
    # no-cache: o navegador sempre revalida o HTML (via ETag), então toda
    # atualização do painel aparece na hora, sem precisar limpar o cache.
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/report")
def report_page():
    """Relatório completo (imprimível/PDF). A própria página busca os dados com
    o login do usuário (mesma origem); protege via /api/* que exige token."""
    return FileResponse(STATIC / "report.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config_public():
    """Config pública para o frontend (o client_id do Google não é segredo)."""
    sid = os.getenv("GOOGLE_SHEET_ID", "")
    return {
        "google_client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
        "domain": ALLOWED_DOMAIN,
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{sid}/edit" if sid else "",
    }


@app.get("/api/dashboard")
def dashboard(_: str = Depends(current_user)):
    _, dash = _load()
    return dash


@app.get("/api/analysis")
def analysis(_: str = Depends(current_user)):
    """Análise rica por IA (carregada à parte para o painel abrir rápido)."""
    return _load_analise_ia()


class Pergunta(BaseModel):
    question: str


@app.post("/api/ask")
def ask(p: Pergunta, user: str = Depends(current_user)):
    q = (p.question or "").strip()
    if not q:
        raise HTTPException(422, "Pergunta vazia.")
    raw, dash = _load()
    resposta = analyst_ai.answer_question(q, raw, dash.get("budget"))
    try:
        chat_history.add(q, resposta, user.split("@")[0],
                         datetime.now(BRT).strftime("%d/%m %H:%M"))
    except Exception as exc:
        print(f"  aviso: não salvei no histórico: {exc}")
    return {"answer": resposta, "asked_by": user}


@app.get("/api/history")
def history(_: str = Depends(current_user)):
    """Consultas recentes do time (persistidas na planilha). Antiga -> nova."""
    try:
        return chat_history.last()
    except Exception as exc:
        print(f"  aviso: histórico indisponível: {exc}")
        return []


class DelHist(BaseModel):
    id: str


@app.post("/api/history/delete")
def history_delete(p: DelHist, _: str = Depends(current_user)):
    try:
        chat_history.delete(p.id)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(500, f"Não consegui deletar: {exc}")
