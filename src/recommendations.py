"""Logica de recomendacao de acoes sobre as campanhas.

Nenhuma acao e executada automaticamente — toda recomendacao passa
pelo fluxo de aprovacao (e-mail/Discord) antes de chegar a LinkedIn API.
"""
from dataclasses import dataclass

# Limiares iniciais — ajustar conforme histórico real
CPL_MAX_BRL = 100.0          # CPL acima disso gera recomendacao
BUDGET_PACE_MAX = 1.30       # gasto 30% acima do ritmo ideal do mes
ENGAGEMENT_MIN = 0.005       # engagement rate minimo para branding


@dataclass
class Recommendation:
    campaign_id: str
    campaign_name: str
    action: str       # PAUSE | REDUCE_BUDGET | INCREASE_BUDGET | ADJUST_BID | REACTIVATE
    reason: str
    current_value: str
    proposed_value: str


def evaluate_campaign(c: dict) -> list[Recommendation]:
    """Avalia metricas consolidadas de uma campanha e gera recomendacoes.

    Espera um dict com: id, name, type (leads|branding|inmail), invest,
    leads, cpl, daily_budget, month_spent, month_cap, engagement_rate.
    """
    recs: list[Recommendation] = []

    cpl = c.get("cpl")
    if c.get("type") == "leads" and cpl and cpl > CPL_MAX_BRL:
        recs.append(Recommendation(
            campaign_id=c["id"],
            campaign_name=c["name"],
            action="REDUCE_BUDGET",
            reason=f"CPL de R$ {cpl:.0f} acima do limite de R$ {CPL_MAX_BRL:.0f}",
            current_value=f"R$ {c['daily_budget']:.0f}/dia",
            proposed_value=f"R$ {c['daily_budget'] * 0.7:.0f}/dia",
        ))

    pace = c.get("month_spent", 0) / c["month_cap"] if c.get("month_cap") else 0
    if pace > BUDGET_PACE_MAX:
        recs.append(Recommendation(
            campaign_id=c["id"],
            campaign_name=c["name"],
            action="PAUSE",
            reason=f"Orçamento mensal em {pace:.0%} do limite — risco de estouro",
            current_value="ACTIVE",
            proposed_value="PAUSED",
        ))

    eng = c.get("engagement_rate")
    if c.get("type") == "branding" and eng is not None and eng < ENGAGEMENT_MIN:
        recs.append(Recommendation(
            campaign_id=c["id"],
            campaign_name=c["name"],
            action="ADJUST_BID",
            reason=f"Engagement rate de {eng:.2%} abaixo do mínimo de {ENGAGEMENT_MIN:.1%}",
            current_value="lance atual",
            proposed_value="revisar lance/criativo",
        ))

    return recs
