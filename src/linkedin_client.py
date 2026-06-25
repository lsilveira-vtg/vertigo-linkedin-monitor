"""Cliente da LinkedIn Advertising API.

Coleta metricas de campanhas e anuncios e executa acoes aprovadas
(pausar/reativar campanha, ajustar budget e lance).
"""
from datetime import date

import requests

from . import config

BASE_URL = "https://api.linkedin.com/rest"
API_VERSION = "202606"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.LINKEDIN_ACCESS_TOKEN}",
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def get_campaigns() -> list[dict]:
    """Lista todas as campanhas da conta (com paginacao)."""
    url = f"{BASE_URL}/adAccounts/{config.LINKEDIN_ACCOUNT_ID}/adCampaigns"
    campaigns: list[dict] = []
    page_token = None
    while True:
        params = {"q": "search", "pageSize": 1000}
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(url, headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
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
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json().get("elements", [])


# --- Acoes (executadas somente apos aprovacao) ---

def _update_campaign(campaign_id: str, payload: dict) -> None:
    url = f"{BASE_URL}/adAccounts/{config.LINKEDIN_ACCOUNT_ID}/adCampaigns/{campaign_id}"
    resp = requests.post(
        url,
        headers={**_headers(), "X-RestLi-Method": "PARTIAL_UPDATE"},
        json={"patch": {"$set": payload}},
        timeout=30,
    )
    resp.raise_for_status()


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
