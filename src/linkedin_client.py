"""Cliente da LinkedIn Advertising API.

Coleta metricas de campanhas e anuncios e executa acoes aprovadas
(pausar/reativar campanha, ajustar budget e lance).
"""
from datetime import date

import requests

from . import config

BASE_URL = "https://api.linkedin.com/rest"
API_VERSION = "202506"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.LINKEDIN_ACCESS_TOKEN}",
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def get_campaigns() -> list[dict]:
    """Lista campanhas da conta com status e budget."""
    url = f"{BASE_URL}/adAccounts/{config.LINKEDIN_ACCOUNT_ID}/adCampaigns"
    params = {"q": "search", "search": "(status:(values:List(ACTIVE,PAUSED)))"}
    resp = requests.get(url, headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("elements", [])


def get_analytics(start: date, end: date, pivot: str = "CAMPAIGN") -> list[dict]:
    """Metricas (impressoes, cliques, gasto, leads) por campanha ou anuncio.

    pivot: CAMPAIGN ou CREATIVE.
    """
    url = f"{BASE_URL}/adAnalytics"
    params = {
        "q": "analytics",
        "pivot": pivot,
        "dateRange": (
            f"(start:(year:{start.year},month:{start.month},day:{start.day}),"
            f"end:(year:{end.year},month:{end.month},day:{end.day}))"
        ),
        "timeGranularity": "DAILY",
        "accounts": f"List(urn%3Ali%3AsponsoredAccount%3A{config.LINKEDIN_ACCOUNT_ID})",
        "fields": "impressions,clicks,costInLocalCurrency,oneClickLeads,"
                  "reactions,comments,shares,sends,opens,dateRange,pivotValues",
    }
    resp = requests.get(url, headers=_headers(), params=params, timeout=30)
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
