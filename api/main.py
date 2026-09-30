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
import calendar
import os
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BRT = timezone(timedelta(hours=-3))

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src import dashboard_data, analyst_ai, chat_history, reports
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

# Caches por mês (chave "AAAA-MM"): permitem consultar meses anteriores sem
# martelar o LinkedIn. A análise tem cache próprio por período.
_data_cache: dict = {}       # "AAAA-MM" -> {ts, raw, dash}
_ia_cache: dict = {}         # chave da análise -> {key, analysis}
_report_cache: dict = {}     # chave do relatório (RPT-...) -> {analysis}


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
def _current_month() -> str:
    return date.today().strftime("%Y-%m")


def _period(month: str | None = None):
    """Intervalo do mês. Mês corrente vai até ontem; mês passado, até o fim do mês."""
    today = date.today()
    if not month:
        end = today - timedelta(days=1)
        return end.replace(day=1), end
    y, m = (int(x) for x in month.split("-"))
    start = date(y, m, 1)
    last = date(y, m, calendar.monthrange(y, m)[1])
    end = min(last, today - timedelta(days=1))
    return start, max(start, end)


def _load(month: str | None = None, force: bool = False):
    """Dados rápidos do painel (sem a IA) para o mês pedido (padrão: corrente).
    A análise aqui vem do motor de regras (instantânea)."""
    mk = month or _current_month()
    c = _data_cache.get(mk)
    if not force and c and (time.time() - c["ts"] < CACHE_TTL):
        return c["raw"], c["dash"]
    start, end = _period(month)
    raw = collect_campaign_data(start, end)
    dash = dashboard_data.build_dashboard_data(start, end, ref_date=end, data=raw, use_ia=False)
    _data_cache[mk] = {"ts": time.time(), "raw": raw, "dash": dash}
    return raw, dash


def _load_analise_ia(month: str | None = None, force: bool = False):
    """Análise rica por IA, persistida e estável. Mês corrente: 1x por dia (renova
    diário). Mês passado: fixa. Lógica keyed compartilhada em src/reports.py, para
    a API e os jobs agendados gerarem/lerem exatamente o mesmo conteúdo."""
    raw, _ = _load(month)
    return reports.load_or_build_card(month, data=raw, force=force, cache=_ia_cache)


def _load_report_analise(month: str | None = None, force: bool = False):
    """Relatório formal (PDF), robusto e estável. Mês corrente: parcial, 1x/dia.
    Mês passado: fechamento, fixo. Mesma lógica keyed compartilhada (src/reports.py)
    que os jobs usam, então o PDF do painel e o e-mail são o MESMO documento."""
    raw, _ = _load(month)
    return reports.load_or_build_report(month, data=raw, force=force, cache=_report_cache)


def _meses_disponiveis(n: int = 6) -> list[str]:
    """Últimos n meses (mais recente primeiro), para o seletor de período."""
    y, m = date.today().year, date.today().month
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return out


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


@app.get("/api/months")
def months(_: str = Depends(current_user)):
    """Meses disponíveis para consulta (mais recente primeiro)."""
    return _meses_disponiveis()


@app.get("/api/dashboard")
def dashboard(month: str | None = None, _: str = Depends(current_user)):
    _, dash = _load(month)
    return dash


@app.get("/api/analysis")
def analysis(month: str | None = None, _: str = Depends(current_user)):
    """Análise rica por IA (carregada à parte para o painel abrir rápido)."""
    return _load_analise_ia(month)


@app.get("/api/report-analysis")
def report_analysis(month: str | None = None, _: str = Depends(current_user)):
    """Relatório formal (7 seções) para o PDF. Estável por período: mês corrente
    renova 1x/dia; mês passado é um relatório de fechamento fixo."""
    return _load_report_analise(month)


class Pergunta(BaseModel):
    question: str
    conversation_id: str | None = None
    month: str | None = None
    history: list[dict] | None = None    # trocas anteriores da conversa (item 7)


@app.post("/api/ask")
def ask(p: Pergunta, user: str = Depends(current_user)):
    q = (p.question or "").strip()
    if not q:
        raise HTTPException(422, "Pergunta vazia.")
    cid = (p.conversation_id or "").strip() or uuid.uuid4().hex[:12]
    raw, dash = _load(p.month)
    resposta = analyst_ai.answer_question(q, raw, dash.get("budget"),
                                          history=p.history, periodo=dash.get("period"))
    try:
        chat_history.add(cid, q, resposta, user.split("@")[0],
                         datetime.now(BRT).strftime("%d/%m %H:%M"))
    except Exception as exc:
        print(f"  aviso: não salvei no histórico: {exc}")
    return {"answer": resposta, "asked_by": user, "conversation_id": cid}


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
