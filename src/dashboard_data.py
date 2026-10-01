"""Monta o pacote de dados do dashboard (JSON) — consumido pela API.

Reúne, num único dict, o que o painel precisa: KPIs, orçamento, tabela de
campanhas e a análise do agente. Reaproveita a coleta e o analista existentes.
"""
import calendar
from datetime import date, datetime, timedelta, timezone

from . import analyst, analyst_ai, budget, config
from .report_builder import collect_campaign_data, RATEIO_FATOR

BRT = timezone(timedelta(hours=-3))


def _num(v) -> float:
    """Converte um valor da planilha (número ou texto pt-BR/en) em float."""
    s = str(v).strip().replace("R$", "").replace(" ", "")
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")   # 1.234,56 -> 1234.56
    elif "," in s:
        s = s.replace(",", ".")                      # 882,59 -> 882.59
    try:
        return float(s)
    except ValueError:
        return 0.0


def _serie_diaria(start: date, end: date,
                  rateio_nomes: set[str] | None = None) -> list[dict]:
    """Gasto acumulado por dia do mês, lido da aba 'Campanhas' da planilha.

    Retorna [{'dia': 1, 'acumulado': 123.45}, ...] do dia 1 até `end`. Se a
    planilha não estiver acessível, devolve [] (o gráfico simplesmente some).

    `rateio_nomes`: nomes dos grupos que entram rateados (Liferay 50/50). A aba
    'Campanhas' guarda o gasto BRUTO por dia; aplicamos o mesmo fator dos KPIs
    nesses grupos para o acumulado do gráfico bater com o cartão de Investimento
    (senão a linha "estoura" o teto sem ter estourado de verdade).
    """
    rateio_nomes = rateio_nomes or set()
    try:
        from .sheets_client import open_sheet
        linhas = open_sheet().worksheet("Campanhas").get_all_values()[1:]
    except Exception as exc:
        print(f"  aviso: série diária indisponível: {exc}")
        return []
    por_dia: dict[date, float] = {}
    for r in linhas:
        try:
            d = date.fromisoformat((r[0] or "").strip())
        except (ValueError, IndexError, AttributeError):
            continue
        if not (start <= d <= end):
            continue
        inv = _num(r[2]) if len(r) > 2 else 0.0
        nome = (r[1] or "").strip() if len(r) > 1 else ""
        if nome in rateio_nomes:
            inv *= RATEIO_FATOR                      # mesmo rateio dos KPIs
        por_dia[d] = por_dia.get(d, 0.0) + inv
    serie, acc, d = [], 0.0, start
    while d <= end:
        acc += por_dia.get(d, 0.0)
        serie.append({"dia": d.day, "acumulado": round(acc, 2)})
        d += timedelta(days=1)
    return serie


def _period_label(start: date, end: date) -> str:
    return f"{start.strftime('%d/%m')} a {end.strftime('%d/%m/%Y')}"


def build_analysis_ia(start: date, end: date, ref_date: date | None = None,
                      data: list[dict] | None = None, fechado: bool = False,
                      inicio_mes: bool = False) -> dict:
    """Só a análise (IA) — parte lenta, carregada à parte para o painel abrir rápido.
    `fechado`: mês encerrado -> retrospectiva. `inicio_mes`: mês começando -> leitura leve."""
    ref_date = ref_date or end
    if data is None:
        data = collect_campaign_data(start, end)
    a = analyst.run_analysis(_period_label(start, end), data, ref_date=ref_date,
                             fechado=fechado, inicio_mes=inicio_mes)
    return {
        "resumo": a.resumo_executivo,
        "acoes": a.acoes_prioritarias,
        "rodape": getattr(a, "rodape", ""),
    }


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def build_report_analysis(start: date, end: date, ref_date: date | None = None,
                          data: list[dict] | None = None, fechado: bool = False,
                          inicio_mes: bool = False) -> dict:
    """Relatório formal (7 seções) para o PDF. Usa a IA quando há chave; se falhar
    ou não houver chave, monta uma versão estruturada pelo motor de regras (o PDF
    nunca fica sem análise). É persistido pela API (1x/dia), então todos veem o mesmo.

    `fechado`: relatório de fechamento (retrospectivo). `inicio_mes`: leitura leve
    do mês começando (sem alarme de teto)."""
    ref_date = ref_date or end
    if data is None:
        data = collect_campaign_data(start, end)
    period = _period_label(start, end)
    total_invest = sum(c.get("investimento_brl", 0) or 0 for c in data)
    st = budget.account_status(total_invest, ref_date)
    budgets = {"gasto": st["gasto"], "teto": st["teto"], "consumo": st["consumo"], "mes": st["mes"]}

    if config.ANTHROPIC_API_KEY:
        try:
            return analyst_ai.build_report_analysis(period, data, budgets,
                                                    fechado=fechado, inicio_mes=inicio_mes)
        except Exception as exc:
            print(f"  aviso: relatório por IA falhou, usando motor próprio: {exc}")
    return _report_fallback(period, data, ref_date, st, fechado)


def _report_fallback(period: str, data: list[dict], ref_date: date, st: dict,
                     fechado: bool = False) -> dict:
    """Relatório estruturado sem IA (motor de regras) — rede de segurança."""
    a = analyst.analyze(period, data, ref_date=ref_date)
    consumo = st.get("consumo")
    consumo_txt = f"{round(consumo * 100)}%" if consumo is not None else "n/d"
    if fechado:
        contexto = (f"Relatório de fechamento do período {period} (mês encerrado). Foram "
                    f"acompanhados {len(data)} grupos de anúncios. Leads referem-se a formulários "
                    "do LinkedIn; a qualificação (MQL) vem do CRM e pode divergir.")
        orc = (f"Consumo final de {consumo_txt} do teto do mês "
               f"({_brl(st.get('gasto', 0))} de {_brl(st.get('teto', 0))}). "
               "A campanha Liferay entra rateada em 50/50 (a Vertigo banca metade).")
        passos = [
            "Aplicar no próximo mês os aprendizados dos grupos de melhor CPL.",
            "Rever verba dos grupos de baixo retorno antes de repetir a estratégia.",
            "Testar novos criativos/segmentação nos grupos com bom alcance e pouca conversão.",
        ]
    else:
        contexto = (f"Relatório parcial do período {period} (mês em curso). Foram acompanhados "
                    f"{len(data)} grupos de anúncios. Leads referem-se a formulários do LinkedIn; "
                    "a qualificação (MQL) vem do CRM e pode divergir.")
        orc = (f"Consumo de {consumo_txt} do teto do mês "
               f"({_brl(st.get('gasto', 0))} de {_brl(st.get('teto', 0))}). "
               "A campanha Liferay entra rateada em 50/50 (a Vertigo banca metade).")
        passos = [
            "Reavaliar os grupos de menor retorno ainda neste mês.",
            "Concentrar a verba nos grupos de menor CPL de leads qualificados.",
            "Revisar criativos e segmentação antes de escalar qualquer grupo.",
        ]
    return {
        "contexto": contexto,
        "resumo_executivo": a.resumo_executivo,
        "orcamento_ritmo": orc,
        "por_grupo": [
            {"nome": c.nome, "saude": c.saude,
             "texto": " ".join(x for x in (c.diagnostico, c.recomendacao) if x)}
            for c in a.campanhas
        ],
        "riscos_oportunidades": "",
        "recomendacoes": a.acoes_prioritarias,
        "proximos_passos": passos,
    }


def build_dashboard_data(start: date, end: date, ref_date: date | None = None,
                         data: list[dict] | None = None, use_ia: bool = True) -> dict:
    ref_date = ref_date or end
    period = _period_label(start, end)
    if data is None:
        data = collect_campaign_data(start, end)
    # use_ia=False usa só o motor de regras (rápido, sem chamar a IA) — mantém a
    # saúde das campanhas e um resumo imediato; a análise rica da IA vem depois.
    analysis = (analyst.run_analysis(period, data, ref_date=ref_date) if use_ia
                else analyst.analyze(period, data, ref_date=ref_date))
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
        "budget": {
            "gasto": st["gasto"], "teto": st["teto"], "consumo": st["consumo"], "mes": st["mes"],
            "dias_no_mes": calendar.monthrange(ref_date.year, ref_date.month)[1],
            "dia_atual": ref_date.day,
        },
        "serie_diaria": _serie_diaria(
            start.replace(day=1), ref_date,
            {c["nome"] for c in data if c.get("rateio_5050")}),
        "campaigns": campaigns,
        "analysis": {
            "resumo": analysis.resumo_executivo,
            "acoes": analysis.acoes_prioritarias,
            "rodape": getattr(analysis, "rodape", ""),
        },
    }
