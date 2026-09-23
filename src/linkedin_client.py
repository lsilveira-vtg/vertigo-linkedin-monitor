"""Cliente da LinkedIn Advertising API.

Coleta metricas de campanhas e anuncios e executa acoes aprovadas
(pausar/reativar campanha, ajustar budget e lance).
"""
from datetime import date

import requests

from . import config

BASE_URL = "https://api.linkedin.com/rest"
API_VERSION = "202606"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

# Access token válido para este processo (renovado uma vez via refresh token).
_access_token: str | None = None


def _get_access_token() -> str:
    """Devolve um access token válido.

    Se houver refresh token + credenciais do app, gera um token novo a cada
    processo (o access token do LinkedIn expira em ~60 dias; o refresh token
    vale ~1 ano). Assim a coleta não quebra mais quando o access token vence.
    Em caso de falha na renovação, cai no LINKEDIN_ACCESS_TOKEN estático.
    """
    global _access_token
    if _access_token:
        return _access_token

    if config.LINKEDIN_REFRESH_TOKEN and config.LINKEDIN_CLIENT_ID and config.LINKEDIN_CLIENT_SECRET:
        try:
            resp = requests.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": config.LINKEDIN_REFRESH_TOKEN,
                    "client_id": config.LINKEDIN_CLIENT_ID,
                    "client_secret": config.LINKEDIN_CLIENT_SECRET,
                },
                timeout=30,
            )
            resp.raise_for_status()
            _access_token = resp.json()["access_token"]
            print("Token LinkedIn renovado via refresh token.")
            return _access_token
        except Exception as exc:
            print(f"  aviso: falha ao renovar token LinkedIn ({exc}); "
                  "usando LINKEDIN_ACCESS_TOKEN estático.")

    _access_token = config.LINKEDIN_ACCESS_TOKEN
    return _access_token


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_access_token()}",
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def _request(method: str, url: str, *, extra_headers: dict | None = None, **kwargs):
    """Faz a requisição e, se tomar 401 (token expirado durante um processo
    longo como o bot), renova o token uma vez e tenta de novo. Isso mantém o
    bot funcionando por semanas sem reinício, mesmo quando o access token vence.
    """
    global _access_token

    def _do():
        h = _headers()
        if extra_headers:
            h.update(extra_headers)
        return requests.request(method, url, headers=h, timeout=30, **kwargs)

    resp = _do()
    if resp.status_code == 401:
        print("  401 do LinkedIn — renovando token e tentando novamente.")
        _access_token = None  # força nova renovação via refresh token
        resp = _do()
    resp.raise_for_status()
    return resp


def get_campaigns() -> list[dict]:
    """Lista todas as campanhas da conta (com paginacao)."""
    url = f"{BASE_URL}/adAccounts/{config.LINKEDIN_ACCOUNT_ID}/adCampaigns"
    campaigns: list[dict] = []
    page_token = None
    while True:
        params = {"q": "search", "pageSize": 1000}
        if page_token:
            params["pageToken"] = page_token
        resp = _request("GET", url, params=params)
        data = resp.json()
        campaigns.extend(data.get("elements", []))
        page_token = data.get("metadata", {}).get("nextPageToken")
        if not page_token:
            break
    return campaigns


# Metricas pedidas no relatorio (campos validos da AdAnalytics API).
ANALYTICS_FIELDS = [
    "impressions", "clicks", "costInLocalCurrency", "oneClickLeads",
    "externalWebsiteConversions", "likes", "comments", "shares",
    "follows", "landingPageClicks", "dateRange", "pivotValues",
]


def get_creative(creative_id: str) -> dict:
    """Busca um criativo (anuncio) por id. Retorna o dict da API.

    Campos uteis: 'name' (geralmente vazio), 'campaign' (urn) e
    'content'->'reference' (urn do post/share que da origem ao anuncio).
    """
    enc = f"urn%3Ali%3AsponsoredCreative%3A{creative_id}"
    url = f"{BASE_URL}/adAccounts/{config.LINKEDIN_ACCOUNT_ID}/creatives/{enc}"
    return _request("GET", url).json()


def post_url(share_urn: str) -> str:
    """Monta a URL publica do post/anuncio a partir do urn (share ou ugcPost)."""
    if not share_urn:
        return ""
    return f"https://www.linkedin.com/feed/update/{share_urn}"


def get_analytics(start: date, end: date, pivot: str = "CAMPAIGN") -> list[dict]:
    """Metricas (impressoes, cliques, gasto, leads) por campanha ou anuncio.

    pivot: CAMPAIGN ou CREATIVE.

    A query string e montada manualmente porque a API do LinkedIn usa sintaxe
    Rest.li (parenteses, List(), virgulas em `fields`) que o requests codifica
    de forma incompativel se passada via `params`.
    """
    date_range = (
        f"(start:(year:{start.year},month:{start.month},day:{start.day}),"
        f"end:(year:{end.year},month:{end.month},day:{end.day}))"
    )
    account_urn = f"List(urn%3Ali%3AsponsoredAccount%3A{config.LINKEDIN_ACCOUNT_ID})"
    query = (
        f"q=analytics&pivot={pivot}&timeGranularity=DAILY"
        f"&dateRange={date_range}"
        f"&accounts={account_urn}"
        f"&fields={','.join(ANALYTICS_FIELDS)}"
    )
    url = f"{BASE_URL}/adAnalytics?{query}"
    return _request("GET", url).json().get("elements", [])


# --- Acoes (executadas somente apos aprovacao) ---

def _update_campaign(campaign_id: str, payload: dict) -> None:
    url = f"{BASE_URL}/adAccounts/{config.LINKEDIN_ACCOUNT_ID}/adCampaigns/{campaign_id}"
    _request(
        "POST", url,
        extra_headers={"X-RestLi-Method": "PARTIAL_UPDATE"},
        json={"patch": {"$set": payload}},
    )


def pause_campaign(campaign_id: str) -> None:
    _update_campaign(campaign_id, {"status": "PAUSED"})


def activate_campaign(campaign_id: str) -> None:
    _update_campaign(campaign_id, {"status": "ACTIVE"})


def set_daily_budget(campaign_id: str, amount_brl: float) -> None:
    _update_campaign(
        campaign_id,
        {"dailyBudget": {"amount": f"{amount_brl:.2f}", "currencyCode": "BRL"}},
    )


def set_bid(campaign_id: str, amount_brl: float) -> None:
    _update_campaign(
        campaign_id,
        {"unitCost": {"amount": f"{amount_brl:.2f}", "currencyCode": "BRL"}},
    )
