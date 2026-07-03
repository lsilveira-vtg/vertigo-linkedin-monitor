"""Regras de orçamento da conta de anúncios da Vertigo.

Carregadas do Secret BUDGET_RULES_JSON (para não expor valores no código).
Estrutura esperada:

{
  "total_mensal": 2636.37,                 # teto mensal padrão da conta
  "overrides": {"2026-07": 2534.44},       # tetos específicos por mês (compensações)
  "campanhas": {
    "Liferay": {"limite_mensal": 1200.00, "pausar_apos": "2026-11"}
  }
}

- overrides: quando um mês precisa compensar gasto anterior, cadastra-se o teto
  daquele mês (Leandro comunica o valor).
- campanhas: sub-limites por nome (match parcial, case-insensitive) e data-limite
  de veiculação ("pausar_apos" = último mês em que pode rodar, formato AAAA-MM).
"""
import json
import os
from datetime import date

_RULES: dict = json.loads(os.getenv("BUDGET_RULES_JSON", "{}"))


def total_cap(year_month: str) -> float | None:
    """Teto total da conta para o mês (AAAA-MM). Usa override se houver."""
    overrides = _RULES.get("overrides", {})
    if year_month in overrides:
        return float(overrides[year_month])
    total = _RULES.get("total_mensal")
    return float(total) if total is not None else None


def account_status(spent: float, ref: date) -> dict:
    """Situação da conta no mês de `ref`: teto, gasto, % e sinal de estouro."""
    ym = ref.strftime("%Y-%m")
    cap = total_cap(ym)
    pct = (spent / cap) if cap else None
    return {"mes": ym, "teto": cap, "gasto": round(spent, 2), "consumo": pct}


def campaign_rule(campaign_name: str) -> dict | None:
    """Retorna a regra da campanha cujo nome casa (parcial, case-insensitive)."""
    name_low = (campaign_name or "").lower()
    for chave, regra in _RULES.get("campanhas", {}).items():
        if chave.lower() in name_low:
            return {"chave": chave, **regra}
    return None


def campaign_alerts(campaign_name: str, spent: float, ref: date) -> list[str]:
    """Alertas de sub-limite e de data-limite para uma campanha específica."""
    regra = campaign_rule(campaign_name)
    if not regra:
        return []
    alerts: list[str] = []
    limite = regra.get("limite_mensal")
    if limite and spent > float(limite):
        alerts.append(
            f"{regra['chave']}: gasto de R$ {spent:,.0f} ultrapassou o sub-limite mensal "
            f"de R$ {float(limite):,.0f}.".replace(",", ".")
        )
    pausar_apos = regra.get("pausar_apos")
    if pausar_apos and ref.strftime("%Y-%m") > pausar_apos:
        alerts.append(
            f"{regra['chave']}: veiculação expirou em {pausar_apos} — deve ser PAUSADA."
        )
    return alerts
