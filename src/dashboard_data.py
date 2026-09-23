"""Monta o pacote de dados do dashboard (JSON) — consumido pela API.

Reúne, num único dict, o que o painel precisa: KPIs, orçamento, tabela de
campanhas e a análise do agente. Reaproveita a coleta e o analista existentes.
"""
from datetime import date, datetime, timedelta, timezone

from . import analyst, budget
from .report_builder import collect_campaign_data

BRT = timezone(timedelta(hours=-3))


def build_dashboard_data(start: date, end: date, ref_date: date | None = None,
                         data: list[dict] | None = None) -> dict:
    ref_date = ref_date or end
    period = f"{start.strftime('%d/%m')} a {end.strftime('%d/%m/%Y')}"
    if data is None:
        data = collect_campaign_data(start, end)
    analysis = analyst.run_analysis(period, data, ref_date=ref_date)
    saude_by = {v.nome: v for v in analysis.campanhas}

    total_invest = sum(c.get("investimento_brl", 0) or 0 for c in data)
    lead_camps = [c for c in data if c.get("tipo", "leads") not in ("trafego", "branding")]
    invest_leads = sum(c.get("investimento_brl", 0) or 0 for c in lead_camps)
    total_leads = sum(c.get("leads", 0) or 0 for c in lead_camps)
    cpl_geral = round(invest_leads / total_leads, 2) if total_leads else None

    st = budget.account_status(total_invest, ref_date)

    campaigns = []
    for c in sorted(data, key=lambda x: x.get("investimento_brl", 0) or 0, reverse=True):
        v = saude_by.get(c["nome"])
        clk = c.get("cliques", 0) or 0
        traf = c.get("tipo") == "trafego"
        campaigns.append({
            "nome": c["nome"],
            "tipo": c.get("tipo", "leads"),
            "status": c.get("status", ""),
            "saude": v.saude if v else "",
            "investimento": round(c.get("investimento_brl", 0) or 0, 2),
            "leads": None if traf else (c.get("leads", 0) or 0),
            "cpl": c.get("cpl_brl") if not traf else None,
            "impressoes": c.get("impressoes", 0) or 0,
            "cliques": clk,
            "cpc": round(c["investimento_brl"] / clk, 2) if (traf and clk) else None,
            "ctr": c.get("ctr"),
            "diagnostico": v.diagnostico if v else "",
            "recomendacao": v.recomendacao if v else "",
        })

    return {
        "period": period,
        "updated_at": datetime.now(BRT).strftime("%d/%m/%Y %H:%M"),
        "kpis": {
            "investimento": round(total_invest, 2),
            "leads": total_leads,
            "cpl_geral": cpl_geral,
            "consumo_teto": st["consumo"],
        },
        "budget": {"gasto": st["gasto"], "teto": st["teto"], "consumo": st["consumo"], "mes": st["mes"]},
        "campaigns": campaigns,
        "analysis": {
            "resumo": analysis.resumo_executivo,
            "acoes": analysis.acoes_prioritarias,
            "rodape": getattr(analysis, "rodape", ""),
        },
    }
