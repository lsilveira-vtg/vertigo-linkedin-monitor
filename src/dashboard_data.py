"""Monta o pacote de dados do dashboard (JSON) — consumido pela API.

Reúne, num único dict, o que o painel precisa: KPIs, orçamento, tabela de
campanhas e a análise do agente. Reaproveita a coleta e o analista existentes.
"""
import calendar
from datetime import date, datetime, timedelta, timezone

from . import analyst, analyst_ai, budget, config, plano
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


def _resumo_periodo(p_start: date, p_end: date, data: list[dict] | None = None) -> dict | None:
    """Resumo compacto de QUALQUER período (paralelo de início de mês e comparações
    no chat). Inclui números por grupo (com engajamento) para responder perguntas
    tipo 'CPL/CTR do grupo X no mês passado'."""
    try:
        data = data if data is not None else collect_campaign_data(p_start, p_end)
    except Exception as exc:
        print(f"  aviso: não li o período {p_start}..{p_end}: {exc}")
        return None
    if not data:
        return None
    total = sum(c.get("investimento_brl", 0) or 0 for c in data)
    lead_camps = [c for c in data if c.get("tipo", "leads") not in ("trafego", "branding")]
    inv_leads = sum(c.get("investimento_brl", 0) or 0 for c in lead_camps)
    leads = sum(c.get("leads", 0) or 0 for c in lead_camps)
    st = budget.account_status(total, p_end)
    return {
        "periodo": _period_label(p_start, p_end),
        "investimento": round(total, 2),
        "leads": leads,
        "cpl_geral": round(inv_leads / leads, 2) if leads else None,
        "consumo_teto": st.get("consumo"),
        "teto": st.get("teto"),
        "grupos": [{"nome": c["nome"], "tipo": c.get("tipo", "leads"),
                    "invest": round(c.get("investimento_brl", 0) or 0, 2),
                    "leads": c.get("leads", 0) or 0, "cpl": c.get("cpl_brl"),
                    "impressoes": c.get("impressoes", 0) or 0,
                    "cliques": c.get("cliques", 0) or 0, "ctr": c.get("ctr")} for c in data],
    }


def _resumo_mes_anterior(start: date) -> dict | None:
    """Resumo compacto do mês ANTERIOR ao `start` (para o paralelo de início de mês)."""
    prev_end = start - timedelta(days=1)
    return _resumo_periodo(prev_end.replace(day=1), prev_end)


def historico_para_chat(start: date, end: date, n_meses: int = 2) -> dict:
    """Histórico compacto para o chat COMPARAR meses sem o usuário trocar o seletor:
    resumos dos últimos `n_meses` meses cheios + o MESMO intervalo de dias do mês
    anterior (ex.: 01-19/set para comparar com 01-19/out). Cada chamada bate na API
    do LinkedIn, então o chamador (API) deve cachear — meses passados são imutáveis."""
    meses: list[dict] = []
    m_end = start - timedelta(days=1)
    for _ in range(max(1, n_meses)):
        m_start = m_end.replace(day=1)
        r = _resumo_periodo(m_start, m_end)
        if r:
            meses.append(r)
        m_end = m_start - timedelta(days=1)       # recua para o mês anterior
    # mesmo intervalo de dias no mês anterior (comparação "mesmo período")
    prev_first = (start.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_prev = calendar.monthrange(prev_first.year, prev_first.month)[1]
    sp = _resumo_periodo(prev_first, date(prev_first.year, prev_first.month, min(end.day, last_prev)))
    return {"meses": meses, "mesmo_periodo_mes_anterior": sp}


def build_analysis_ia(start: date, end: date, ref_date: date | None = None,
                      data: list[dict] | None = None, fechado: bool = False,
                      inicio_mes: bool = False) -> dict:
    """Só a análise (IA) — parte lenta, carregada à parte para o painel abrir rápido.
    `fechado`: mês encerrado -> retrospectiva. `inicio_mes`: mês começando -> leitura leve
    com paralelo ao mês anterior."""
    ref_date = ref_date or end
    if data is None:
        data = collect_campaign_data(start, end)
    prev = _resumo_mes_anterior(start) if inicio_mes else None
    a = analyst.run_analysis(_period_label(start, end), data, ref_date=ref_date,
                             fechado=fechado, inicio_mes=inicio_mes, mes_anterior=prev)
    return {
        "resumo": a.resumo_executivo,
        "acoes": a.acoes_prioritarias,
        "rodape": getattr(a, "rodape", ""),
    }


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def cpl_consolidado(rateio_nomes: set | None = None, traf_nomes: set | None = None):
    """CPL blended de TODO o histórico disponível (aba 'Campanhas'): só grupos de
    LEAD (exclui tráfego/branding) e com o rateio 50/50 da Liferay aplicado. É um
    benchmark estável, usado como referência frente ao CPL do mês."""
    rateio_nomes = rateio_nomes or set()
    traf_nomes = traf_nomes or set()
    try:
        from .sheets_client import open_sheet
        linhas = open_sheet().worksheet("Campanhas").get_all_values()
    except Exception as exc:
        print(f"  aviso: CPL consolidado indisponível: {exc}")
        return None
    if len(linhas) < 2:
        return None
    header = linhas[0]

    def _idx(nome, pad):
        try:
            return header.index(nome)
        except ValueError:
            return pad
    i_nome, i_inv, i_leads = _idx("Campanha", 1), _idx("Invest (R$)", 2), _idx("Leads", 3)
    inv_leads, leads = 0.0, 0
    for r in linhas[1:]:
        if len(r) <= max(i_nome, i_inv, i_leads):
            continue
        nome = (r[i_nome] or "").strip()
        if not nome or nome in traf_nomes:        # tráfego/branding não entra no CPL
            continue
        fator = RATEIO_FATOR if nome in rateio_nomes else 1.0
        inv_leads += _num(r[i_inv]) * fator
        leads += int(_num(r[i_leads]))
    return round(inv_leads / leads, 2) if leads > 0 else None


def cpl_consolidado_por_grupo(rateio_nomes: set | None = None, traf_nomes: set | None = None):
    """CPL histórico (todo o período da aba 'Campanhas') QUEBRADO por grupo de
    anúncios. Mesma regra do consolidado geral (rateio 50/50 e exclusão de
    tráfego/branding), só que somando invest/leads por nome. Devolve {nome: cpl}
    apenas para os grupos que tiveram lead no histórico."""
    rateio_nomes = rateio_nomes or set()
    traf_nomes = traf_nomes or set()
    try:
        from .sheets_client import open_sheet
        linhas = open_sheet().worksheet("Campanhas").get_all_values()
    except Exception as exc:
        print(f"  aviso: CPL histórico por grupo indisponível: {exc}")
        return {}
    if len(linhas) < 2:
        return {}
    header = linhas[0]

    def _idx(nome, pad):
        try:
            return header.index(nome)
        except ValueError:
            return pad
    i_nome, i_inv, i_leads = _idx("Campanha", 1), _idx("Invest (R$)", 2), _idx("Leads", 3)
    acc: dict[str, list] = {}       # nome -> [invest_rateado, leads]
    for r in linhas[1:]:
        if len(r) <= max(i_nome, i_inv, i_leads):
            continue
        nome = (r[i_nome] or "").strip()
        if not nome or nome in traf_nomes:
            continue
        fator = RATEIO_FATOR if nome in rateio_nomes else 1.0
        a = acc.setdefault(nome, [0.0, 0])
        a[0] += _num(r[i_inv]) * fator
        a[1] += int(_num(r[i_leads]))
    return {nome: round(inv / leads, 2) for nome, (inv, leads) in acc.items() if leads > 0}


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
    prev = _resumo_mes_anterior(start) if inicio_mes else None

    if config.ANTHROPIC_API_KEY:
        try:
            return analyst_ai.build_report_analysis(period, data, budgets, fechado=fechado,
                                                    inicio_mes=inicio_mes, mes_anterior=prev)
        except Exception as exc:
            print(f"  aviso: relatório por IA falhou, usando motor próprio: {exc}")
    return _report_fallback(period, data, ref_date, st, fechado, inicio_mes, prev)


def _report_fallback(period: str, data: list[dict], ref_date: date, st: dict,
                     fechado: bool = False, inicio_mes: bool = False,
                     mes_anterior: dict | None = None) -> dict:
    """Relatório estruturado sem IA (motor de regras) — rede de segurança."""
    a = analyst.analyze(period, data, ref_date=ref_date)
    resumo = a.resumo_executivo
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
    elif inicio_mes:
        ma = mes_anterior or {}
        prev_cpl = ma.get("cpl_geral")
        prev_leads = ma.get("leads")
        prev_periodo = ma.get("periodo", "o mês anterior")
        ref = (f" No mês anterior ({prev_periodo}) foram {prev_leads} leads a um CPL geral de "
               f"{_brl(prev_cpl)}." if prev_cpl else "")
        contexto = (f"Relatório de início de mês do período {period}. Estamos na primeira semana, "
                    "então os números ainda são parciais e servem mais para calibrar o ritmo do que "
                    "para concluir sobre o mês. A leitura abaixo se apoia no desempenho do mês "
                    f"anterior.{ref} Leads referem-se a formulários do LinkedIn; a qualificação (MQL) "
                    "vem do CRM e pode divergir.")
        resumo = ("Mês começando: nos primeiros dias foram "
                  f"{_brl(st.get('gasto', 0))} investidos (consumo de {consumo_txt} do teto de "
                  f"{_brl(st.get('teto', 0))}), volume ainda baixo e esperado para o início. "
                  "Como há poucos dados, a referência é o mês anterior"
                  + (f", que fechou com CPL geral de {_brl(prev_cpl)}" if prev_cpl else "")
                  + ". O plano para este mês é concentrar a verba nos grupos de menor CPL de leads "
                  "qualificados, replicar o que funcionou e revisar os grupos de baixo retorno antes "
                  "de escalar. As projeções do mês devem ser confirmadas conforme os dados chegarem.")
        orc = (f"Consumo de {consumo_txt} do teto do mês ({_brl(st.get('gasto', 0))} de "
               f"{_brl(st.get('teto', 0))}), ritmo natural para o início do mês. A campanha Liferay "
               "entra rateada em 50/50 (a Vertigo banca metade).")
        passos = [
            "Acompanhar o ritmo de gasto nos próximos dias antes de ajustar a verba.",
            "Concentrar a verba nos grupos de menor CPL de leads qualificados.",
            "Replicar o que funcionou no mês anterior e revisar os grupos de baixo retorno.",
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
        "resumo_executivo": resumo,
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
    # CPL consolidado (todo o histórico) — benchmark estável frente ao CPL do mês.
    rateio_nomes = {c["nome"] for c in data if c.get("rateio_5050")}
    traf_nomes = {c["nome"] for c in data if c.get("tipo", "leads") in ("trafego", "branding")}
    cpl_consol = cpl_consolidado(rateio_nomes, traf_nomes)
    cpl_hist_grupo = cpl_consolidado_por_grupo(rateio_nomes, traf_nomes)

    st = budget.account_status(total_invest, ref_date)

    campaigns = []
    for c in sorted(data, key=lambda x: x.get("investimento_brl", 0) or 0, reverse=True):
        v = saude_by.get(c["nome"])
        clk = c.get("cliques", 0) or 0
        # "reach" = tráfego ou conhecimento de marca: avaliar por alcance/CPC/CTR,
        # nunca por leads/CPL (ex.: grupo de marca da Liferay).
        reach = c.get("tipo") in ("trafego", "branding")
        campaigns.append({
            "nome": c["nome"],
            "tipo": c.get("tipo", "leads"),
            "status": c.get("status", ""),
            "saude": v.saude if v else "",
            "investimento": round(c.get("investimento_brl", 0) or 0, 2),
            "leads": None if reach else (c.get("leads", 0) or 0),
            "cpl": c.get("cpl_brl") if not reach else None,
            "cpl_hist": None if reach else cpl_hist_grupo.get(c["nome"]),
            "impressoes": c.get("impressoes", 0) or 0,
            "cliques": clk,
            "cpc": round(c["investimento_brl"] / clk, 2) if (reach and clk) else None,
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
            "cpl_consolidado": cpl_consol,
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
        "liferay": plano.liferay_resumo(ref_date),      # banner do patrocínio (None fora de nov/26)
        "analysis": {
            "resumo": analysis.resumo_executivo,
            "acoes": analysis.acoes_prioritarias,
            "rodape": getattr(analysis, "rodape", ""),
        },
    }
