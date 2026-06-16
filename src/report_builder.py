"""Monta o report de um periodo a partir dos dados do LinkedIn.

Conecta a coleta (linkedin_client) ao formato padrao (report).
A classificacao de cada campanha (leads/branding/inmail, emoji, budget)
fica em CAMPAIGN_CONFIG — ajustar quando as campanhas reais estiverem
disponiveis apos a aprovacao da API.
"""
import json
import os
from datetime import date

from . import linkedin_client
from .report import CampaignReport, format_report

# Configuracao por campanha: id -> propriedades de exibicao (emoji, type, display, note, budget_cap).
# Dados sensiveis NAO ficam no codigo: carregados do Secret CAMPAIGN_CONFIG_JSON.
# Formato: {"123456": {"emoji": "...", "type": "leads", "display": "..."}}
CAMPAIGN_CONFIG: dict[str, dict] = json.loads(os.getenv("CAMPAIGN_CONFIG_JSON", "{}"))

# Limites de orcamento mensal por grupo (dados sensiveis) — vem do Secret MONTHLY_BUDGETS_JSON.
# Formato: {"Grupo": limite_em_reais}
MONTHLY_BUDGETS: dict[str, float] = json.loads(os.getenv("MONTHLY_BUDGETS_JSON", "{}"))


def _aggregate(rows: list[dict]) -> dict[str, dict]:
    """Soma metricas diarias por campanha."""
    out: dict[str, dict] = {}
    for row in rows:
        key = row.get("pivotValues", [""])[0]
        agg = out.setdefault(key, {})
        for metric in ("impressions", "clicks", "costInLocalCurrency", "oneClickLeads",
                       "reactions", "comments", "shares", "sends", "opens"):
            agg[metric] = agg.get(metric, 0) + float(row.get(metric, 0) or 0)
    return out


def build_report_for_period(start: date, end: date) -> str:
    analytics = _aggregate(linkedin_client.get_analytics(start, end, pivot="CAMPAIGN"))
    campaigns_meta = {c["id"]: c for c in linkedin_client.get_campaigns()}

    reports: list[CampaignReport] = []
    for campaign_id, metrics in analytics.items():
        cfg = CAMPAIGN_CONFIG.get(str(campaign_id), {})
        meta = campaigns_meta.get(campaign_id, {})
        ctype = cfg.get("type", "leads")

        rep = CampaignReport(
            emoji=cfg.get("emoji", "📊"),
            name=cfg.get("display", meta.get("name", str(campaign_id))),
            note=cfg.get("note", ""),
            invest=metrics.get("costInLocalCurrency", 0),
        )
        if ctype == "branding":
            rep.reactions = int(metrics.get("reactions", 0))
            rep.comments = int(metrics.get("comments", 0))
            rep.shares = int(metrics.get("shares", 0))
            rep.impressions = int(metrics.get("impressions", 0))
        elif ctype == "inmail":
            rep.sends = int(metrics.get("sends", 0))
            rep.opens = int(metrics.get("opens", 0))
            rep.clicks = int(metrics.get("clicks", 0))
            rep.leads = int(metrics.get("oneClickLeads", 0))
            rep.budget_cap = cfg.get("budget_cap")
        else:
            rep.leads = int(metrics.get("oneClickLeads", 0))
        reports.append(rep)

    # Orcamento mensal: gasto MTD por grupo (simplificado — refinar com dados reais)
    budgets = {name: (0.0, cap) for name, cap in MONTHLY_BUDGETS.items()}

    period = f"{start.strftime('%d/%m')} a {end.strftime('%d/%m/%Y')}"
    return format_report(period, reports, budgets, deltas={})
