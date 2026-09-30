"""Visualizações organizadas na planilha.

- "📊 Resumo": a aba que se abre e entende tudo. Faixa de título, tira de KPIs
  (investimento, leads, CPL geral, consumo do teto), tabela por campanha com
  cores por saúde/status, bloco de orçamento e a análise do agente.
- Uma aba por campanha: histórico diário limpo de cada campanha (com linha de
  TOTAL), derivado da aba bruta "Campanhas" (que continua alimentando o Looker).

Toda a formatação é aplicada por código (batch_update) a cada reconstrução, então
a planilha nunca "desformata" — mesmo com a coleta diária reescrevendo os dados.
"""
import calendar
import re
from datetime import date

from . import analyst, budget, sheets_client
from .report_builder import collect_campaign_data

RESUMO_TAB = "📊 Resumo"
MESES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
               "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _month_tab_name(month_key: str) -> str:
    """'2026-08' -> 'Resumo Ago/2026' (nome da aba de fechamento do mês)."""
    y, m = int(month_key[:4]), int(month_key[5:7])
    return f"Resumo {MESES_ABREV[m - 1]}/{y}"

SAUDE_LABEL = {"boa": "🟢 Boa", "atencao": "🟡 Atenção", "critica": "🔴 Requer ação"}
STATUS_LABEL = {"ACTIVE": "Ativa", "PAUSED": "Pausada", "DRAFT": "Rascunho",
                "COMPLETED": "Concluída", "": "—"}

RESUMO_HEADER = [
    "Campanha", "Tipo", "Status", "Saúde", "Invest (R$)", "Leads", "CPL (R$)",
    "Impressões", "Cliques", "CTR", "Diagnóstico", "Recomendação",
]
NCOLS = len(RESUMO_HEADER)  # 12 (A..L)

# ---- Paleta (RGB 0-1) ----
NAVY = (0.122, 0.216, 0.388)
WHITE = (1, 1, 1)
GRAY_TXT = (0.4, 0.4, 0.4)
ZEBRA = (0.96, 0.965, 0.975)
KPI_BG = (0.93, 0.95, 0.99)
GREEN_BG, GREEN_TX = (0.85, 0.94, 0.82), (0.0, 0.38, 0.0)
YEL_BG, YEL_TX = (1.0, 0.90, 0.60), (0.60, 0.40, 0.0)
RED_BG, RED_TX = (0.96, 0.80, 0.80), (0.60, 0.0, 0.0)
BORDER = (0.75, 0.75, 0.75)

SAUDE_COLORS = {"boa": (GREEN_BG, GREEN_TX), "atencao": (YEL_BG, YEL_TX),
                "critica": (RED_BG, RED_TX)}


def _c(rgb):
    return {"red": rgb[0], "green": rgb[1], "blue": rgb[2]}


def _brl(v: float) -> str:
    return f"R$ {v:,.0f}".replace(",", ".")


def _num(s) -> float:
    """Converte string pt-BR ('R$ 1.234,56', '2.408') em float."""
    t = re.sub(r"[^\d,.-]", "", str(s))
    if not t:
        return 0.0
    if "," in t:  # vírgula = decimal; ponto = milhar
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return 0.0


def _tab_name(nome: str) -> str:
    """Nome de aba seguro: remove sufixo '[...]' e caracteres inválidos, até 60 chars."""
    base = re.sub(r"\[.*?\]", "", nome)
    base = re.sub(r"[:\\/?*\[\]]", "", base).strip(" ·-")
    return base[:60] or "Campanha"


# ---------- helpers de request para o batch_update ----------
def _fmt(sid, r0, r1, c0, c1, fmt, fields):
    return {"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
                  "startColumnIndex": c0, "endColumnIndex": c1},
        "cell": {"userEnteredFormat": fmt},
        "fields": f"userEnteredFormat({fields})"}}


def _merge(sid, r0, r1, c0, c1):
    return {"mergeCells": {"range": {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
            "startColumnIndex": c0, "endColumnIndex": c1}, "mergeType": "MERGE_ALL"}}


def _width(sid, col, px):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": col, "endIndex": col + 1},
        "properties": {"pixelSize": px}, "fields": "pixelSize"}}


def _border(sid, r0, r1, c0, c1):
    line = {"style": "SOLID", "color": _c(BORDER)}
    return {"updateBorders": {
        "range": {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
                  "startColumnIndex": c0, "endColumnIndex": c1},
        "top": line, "bottom": line, "left": line, "right": line,
        "innerHorizontal": line, "innerVertical": line}}


def rebuild_summary(period_label, campaign_data, analysis, ref_date=None,
                    tab_name=RESUMO_TAB, fechado=False):
    """Reescreve uma aba de Resumo, formatada, do zero. `tab_name` permite gerar
    abas de fechamento por mês (ex.: 'Resumo Ago/2026'); `fechado` ajusta o texto."""
    sheet = sheets_client.open_sheet()
    try:
        ws = sheet.worksheet(tab_name)
    except Exception:
        ws = sheet.add_worksheet(title=tab_name, rows=200, cols=NCOLS)
    sid = ws.id

    data = sorted(campaign_data, key=lambda x: x.get("investimento_brl", 0) or 0, reverse=True)
    verdict_by_name = {v.nome: v for v in analysis.campanhas}

    total_invest = sum(c.get("investimento_brl", 0) or 0 for c in data)
    # CPL geral: só campanhas de LEAD (tráfego/branding não miram formulário),
    # igual ao dashboard, senão o CPL fica inflado pelo gasto de tráfego.
    lead_camps = [c for c in data if c.get("tipo", "leads") not in ("trafego", "branding")]
    invest_leads = sum(c.get("investimento_brl", 0) or 0 for c in lead_camps)
    total_leads = sum(c.get("leads", 0) or 0 for c in lead_camps)
    cpl_geral = invest_leads / total_leads if total_leads else None
    consumo = None
    teto = None
    if ref_date is not None:
        st = budget.account_status(total_invest, ref_date)
        teto, consumo = st["teto"], st["consumo"]

    # ---- monta as linhas ----
    rows = []
    rows.append([f"Vertigo · LinkedIn Ads — {period_label}"] + [""] * (NCOLS - 1))
    if fechado:
        sub = ("Fechamento do mês · dados consolidados · leads = formulários do "
               "LinkedIn (MQLs vêm do CRM e podem diferir)")
    else:
        sub = ("Resumo consolidado · atualizado em "
               f"{date.today().strftime('%d/%m/%Y')} · leads = formulários do LinkedIn "
               "(MQLs vêm do CRM e podem diferir)")
    rows.append([sub] + [""] * (NCOLS - 1))
    rows.append([""] * NCOLS)
    rows.append(["INVESTIMENTO TOTAL", "", "", "LEADS", "", "", "CPL GERAL", "", "",
                 "CONSUMO DO TETO", "", ""])
    kpi_teto = (f"{consumo * 100:.0f}%" if consumo is not None else "—")
    rows.append([_brl(total_invest), "", "", str(total_leads), "", "",
                 (_brl(cpl_geral) if cpl_geral else "—"), "", "", kpi_teto, "", ""])
    rows.append([""] * NCOLS)
    header_row = len(rows)          # índice 0-based da linha de cabeçalho
    rows.append(RESUMO_HEADER)
    data_start = len(rows)
    saude_seq = []
    for c in data:
        v = verdict_by_name.get(c["nome"])
        saude = v.saude if v else ""
        saude_seq.append(saude)
        rows.append([
            c["nome"],
            c.get("tipo", ""),
            STATUS_LABEL.get(c.get("status", ""), c.get("status", "")),
            SAUDE_LABEL.get(saude, ""),
            round(c.get("investimento_brl", 0) or 0, 2),
            c.get("leads", 0) or 0,
            (round(c["cpl_brl"], 2) if c.get("cpl_brl") is not None else "—"),
            c.get("impressoes", 0) or 0,
            c.get("cliques", 0) or 0,
            (c["ctr"] if c.get("ctr") is not None else ""),
            analyst._strip_md(v.diagnostico) if v else "",
            analyst._strip_md(v.recomendacao) if v else "",
        ])
    data_end = len(rows)

    rows.append([""] * NCOLS)
    budget_hdr = len(rows)
    rows.append(["ORÇAMENTO MENSAL"] + [""] * (NCOLS - 1))
    budget_lines = []
    if teto:
        pct = f"{consumo * 100:.0f}%" if consumo is not None else "—"
        rows.append([f"Conta (total):  {_brl(total_invest)}  /  {_brl(teto)}   ({pct} do teto)"]
                    + [""] * (NCOLS - 1))
        budget_lines.append((len(rows) - 1, consumo is not None and consumo > 1.0))
    else:
        rows.append([f"Conta (total):  {_brl(total_invest)}   (teto não configurado)"]
                    + [""] * (NCOLS - 1))
        budget_lines.append((len(rows) - 1, False))
    for c in data:
        regra = budget.campaign_rule(c["nome"])
        if regra and regra.get("limite_mensal"):
            gasto = c.get("investimento_brl", 0) or 0
            lim = float(regra["limite_mensal"])
            rows.append([f"{regra['chave']}:  {_brl(gasto)}  /  {_brl(lim)} mensal"]
                        + [""] * (NCOLS - 1))
            budget_lines.append((len(rows) - 1, gasto > lim))

    rows.append([""] * NCOLS)
    analysis_hdr = len(rows)
    rows.append(["ANÁLISE DO AGENTE"] + [""] * (NCOLS - 1))
    analysis_txt = len(rows)
    rows.append([analyst._strip_md(analysis.resumo_executivo)] + [""] * (NCOLS - 1))

    # ---- escreve valores ----
    ws.clear()
    ws.update(values=rows, range_name="A1")

    # ---- formatação (um único batch) ----
    last = len(rows) + 2
    reqs = [
        # limpa formatação e merges antigos de toda a área
        _fmt(sid, 0, last, 0, 26, {}, "backgroundColor,textFormat,borders,horizontalAlignment,"
             "verticalAlignment,numberFormat,wrapStrategy"),
        {"unmergeCells": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": last,
                                    "startColumnIndex": 0, "endColumnIndex": NCOLS}}},
        # título
        _merge(sid, 0, 1, 0, NCOLS),
        _fmt(sid, 0, 1, 0, NCOLS, {"backgroundColor": _c(NAVY), "verticalAlignment": "MIDDLE",
             "textFormat": {"bold": True, "fontSize": 14, "foregroundColor": _c(WHITE)}},
             "backgroundColor,verticalAlignment,textFormat"),
        # subtítulo
        _merge(sid, 1, 2, 0, NCOLS),
        _fmt(sid, 1, 2, 0, NCOLS, {"textFormat": {"italic": True, "fontSize": 9,
             "foregroundColor": _c(GRAY_TXT)}}, "textFormat"),
    ]
    # KPIs (4 blocos de 3 colunas)
    for i in range(4):
        c0 = i * 3
        reqs += [
            _merge(sid, 3, 4, c0, c0 + 3),
            _merge(sid, 4, 5, c0, c0 + 3),
            _fmt(sid, 3, 4, c0, c0 + 3, {"backgroundColor": _c(KPI_BG),
                 "horizontalAlignment": "CENTER", "textFormat": {"bold": True, "fontSize": 8,
                 "foregroundColor": _c(GRAY_TXT)}}, "backgroundColor,horizontalAlignment,textFormat"),
        ]
        over = (i == 3 and consumo is not None and consumo > 1.0)
        val_color = RED_TX if over else NAVY
        reqs.append(_fmt(sid, 4, 5, c0, c0 + 3, {"backgroundColor": _c(KPI_BG),
                    "horizontalAlignment": "CENTER", "textFormat": {"bold": True, "fontSize": 15,
                    "foregroundColor": _c(val_color)}},
                    "backgroundColor,horizontalAlignment,textFormat"))
    # cabeçalho da tabela
    reqs.append(_fmt(sid, header_row, header_row + 1, 0, NCOLS,
                {"backgroundColor": _c(NAVY), "horizontalAlignment": "CENTER",
                 "textFormat": {"bold": True, "foregroundColor": _c(WHITE)}},
                "backgroundColor,horizontalAlignment,textFormat"))
    # zebra
    for i in range(data_start, data_end):
        if (i - data_start) % 2 == 1:
            reqs.append(_fmt(sid, i, i + 1, 0, NCOLS, {"backgroundColor": _c(ZEBRA)},
                        "backgroundColor"))
    # saúde colorida (col D = índice 3)
    for offset, saude in enumerate(saude_seq):
        if saude in SAUDE_COLORS:
            bg, tx = SAUDE_COLORS[saude]
            r = data_start + offset
            reqs.append(_fmt(sid, r, r + 1, 3, 4, {"backgroundColor": _c(bg),
                        "horizontalAlignment": "CENTER",
                        "textFormat": {"bold": True, "foregroundColor": _c(tx)}},
                        "backgroundColor,horizontalAlignment,textFormat"))
    if data_end > data_start:
        # formatos numéricos por coluna (moeda, inteiro, percentual)
        cur = {"numberFormat": {"type": "CURRENCY", "pattern": "R$ #,##0.00"}}
        intg = {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}
        pct = {"numberFormat": {"type": "PERCENT", "pattern": "0.00%"}}
        reqs += [
            _fmt(sid, data_start, data_end, 4, 5, cur, "numberFormat"),   # Invest
            _fmt(sid, data_start, data_end, 6, 7, cur, "numberFormat"),   # CPL
            _fmt(sid, data_start, data_end, 5, 6, intg, "numberFormat"),  # Leads
            _fmt(sid, data_start, data_end, 7, 8, intg, "numberFormat"),  # Impressões
            _fmt(sid, data_start, data_end, 8, 9, intg, "numberFormat"),  # Cliques
            _fmt(sid, data_start, data_end, 9, 10, pct, "numberFormat"),  # CTR
            # alinhamentos e quebra de texto
            _fmt(sid, data_start, data_end, 4, 10, {"horizontalAlignment": "CENTER"},
                 "horizontalAlignment"),
            _fmt(sid, data_start, data_end, 2, 3, {"horizontalAlignment": "CENTER"},
                 "horizontalAlignment"),
            _fmt(sid, data_start, data_end, 10, 12, {"wrapStrategy": "WRAP",
                 "verticalAlignment": "TOP", "textFormat": {"fontSize": 9}},
                 "wrapStrategy,verticalAlignment,textFormat"),
            _border(sid, header_row, data_end, 0, NCOLS),
        ]
    # bloco de orçamento
    reqs += [
        _merge(sid, budget_hdr, budget_hdr + 1, 0, NCOLS),
        _fmt(sid, budget_hdr, budget_hdr + 1, 0, NCOLS, {"backgroundColor": _c(NAVY),
             "textFormat": {"bold": True, "foregroundColor": _c(WHITE)}},
             "backgroundColor,textFormat"),
    ]
    for r, over in budget_lines:
        reqs.append(_merge(sid, r, r + 1, 0, NCOLS))
        reqs.append(_fmt(sid, r, r + 1, 0, NCOLS,
                    {"textFormat": {"bold": over, "foregroundColor": _c(RED_TX if over else GRAY_TXT)}},
                    "textFormat"))
    # bloco de análise
    reqs += [
        _merge(sid, analysis_hdr, analysis_hdr + 1, 0, NCOLS),
        _fmt(sid, analysis_hdr, analysis_hdr + 1, 0, NCOLS, {"backgroundColor": _c(NAVY),
             "textFormat": {"bold": True, "foregroundColor": _c(WHITE)}},
             "backgroundColor,textFormat"),
        _merge(sid, analysis_txt, analysis_txt + 1, 0, NCOLS),
        _fmt(sid, analysis_txt, analysis_txt + 1, 0, NCOLS,
             {"wrapStrategy": "WRAP", "verticalAlignment": "TOP", "textFormat": {"fontSize": 10}},
             "wrapStrategy,verticalAlignment,textFormat"),
    ]
    # larguras + congelamento
    widths = [220, 70, 80, 95, 95, 60, 85, 95, 75, 65, 340, 340]
    for col, px in enumerate(widths):
        reqs.append(_width(sid, col, px))
    reqs.append({"updateSheetProperties": {"properties": {"sheetId": sid,
                 "gridProperties": {"frozenRowCount": header_row + 1}},
                 "fields": "gridProperties.frozenRowCount"}})
    # altura da linha da análise
    reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS",
                 "startIndex": analysis_txt, "endIndex": analysis_txt + 1},
                 "properties": {"pixelSize": 90}, "fields": "pixelSize"}})

    sheet.batch_update({"requests": reqs})


PC_HEADER = ["Data", "Invest (R$)", "Leads", "CPL (R$)", "Impressões", "Cliques",
             "Reações", "Comentários", "Compartilhamentos"]


def rebuild_per_campaign(current_names=None):
    """Cria/atualiza uma aba por campanha (com linha de TOTAL) a partir de 'Campanhas'.
    `current_names`: nomes das campanhas do mês atual; as que não estão nele têm a aba
    OCULTA (campanha que parou), para não poluir o workbook."""
    sheet = sheets_client.open_sheet()
    master = sheet.worksheet("Campanhas")
    values = master.get_all_values()
    if len(values) < 2:
        return
    header = values[0]
    name_idx = header.index("Campanha")

    grupos: dict[str, list[list]] = {}
    for row in values[1:]:
        if len(row) <= name_idx or not row[name_idx]:
            continue
        grupos.setdefault(row[name_idx], []).append(row)

    existing = {ws.title for ws in sheet.worksheets()}
    ncol = len(PC_HEADER)

    for nome, linhas in grupos.items():
        tab = _tab_name(nome)
        # campanha que não está rodando no mês atual -> oculta a aba (se existir) e pula
        if current_names is not None and nome not in current_names:
            if tab in existing:
                try:
                    hide_tab(tab)
                except Exception:
                    pass
            continue
        if tab not in existing:
            ws = sheet.add_worksheet(title=tab, rows=400, cols=ncol)
            existing.add(tab)
        else:
            ws = sheet.worksheet(tab)
        sid = ws.id

        # converte para números (para somar e formatar de verdade)
        body = []
        tot = [0.0] * ncol  # índices 1,2,4,5,6,7,8 são numéricos
        for linha in linhas:
            vals = [v for i, v in enumerate(linha) if i != name_idx]
            data_dia = vals[0] if vals else ""
            invest = _num(vals[1]) if len(vals) > 1 else 0.0
            leads = int(_num(vals[2])) if len(vals) > 2 else 0
            impr = int(_num(vals[4])) if len(vals) > 4 else 0
            clk = int(_num(vals[5])) if len(vals) > 5 else 0
            rea = int(_num(vals[6])) if len(vals) > 6 else 0
            com = int(_num(vals[7])) if len(vals) > 7 else 0
            sha = int(_num(vals[8])) if len(vals) > 8 else 0
            cpl = round(invest / leads, 2) if leads else "—"
            body.append([data_dia, round(invest, 2), leads, cpl, impr, clk, rea, com, sha])
            tot[1] += invest; tot[2] += leads; tot[4] += impr
            tot[5] += clk; tot[6] += rea; tot[7] += com; tot[8] += sha

        cpl_tot = round(tot[1] / tot[2], 2) if tot[2] else "—"
        total_row = ["TOTAL", round(tot[1], 2), int(tot[2]), cpl_tot,
                     int(tot[4]), int(tot[5]), int(tot[6]), int(tot[7]), int(tot[8])]
        # Faixa de título + cabeçalho + dados + TOTAL
        out = [[f"Vertigo · {nome}"] + [""] * (ncol - 1), PC_HEADER] + body + [total_row]

        ws.clear()
        ws.update(values=out, range_name="A1")

        last = len(out)          # total de linhas
        hdr, d0 = 1, 2           # cabeçalho na linha 1; dados a partir da 2
        cur = {"numberFormat": {"type": "CURRENCY", "pattern": "R$ #,##0.00"}}
        intg = {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}
        reqs = [
            _fmt(sid, 0, last + 1, 0, ncol, {},
                 "backgroundColor,textFormat,borders,numberFormat,horizontalAlignment"),
            {"unmergeCells": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": last + 1,
                                        "startColumnIndex": 0, "endColumnIndex": ncol}}},
            _merge(sid, 0, 1, 0, ncol),
            _fmt(sid, 0, 1, 0, ncol, {"backgroundColor": _c(NAVY), "verticalAlignment": "MIDDLE",
                 "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": _c(WHITE)}},
                 "backgroundColor,verticalAlignment,textFormat"),
            _fmt(sid, hdr, hdr + 1, 0, ncol, {"backgroundColor": _c(NAVY),
                 "horizontalAlignment": "CENTER", "textFormat": {"bold": True,
                 "foregroundColor": _c(WHITE)}}, "backgroundColor,horizontalAlignment,textFormat"),
            _fmt(sid, d0, last, 1, 2, cur, "numberFormat"),      # Invest
            _fmt(sid, d0, last, 3, 4, cur, "numberFormat"),      # CPL
            _fmt(sid, d0, last, 2, 3, intg, "numberFormat"),     # Leads
            _fmt(sid, d0, last, 4, ncol, intg, "numberFormat"),  # Impr/Cliques/Reações/...
            _fmt(sid, d0, last, 1, ncol, {"horizontalAlignment": "CENTER"}, "horizontalAlignment"),
            _fmt(sid, last - 1, last, 0, ncol, {"backgroundColor": _c(KPI_BG),
                 "textFormat": {"bold": True}}, "backgroundColor,textFormat"),   # TOTAL
            _border(sid, hdr, last, 0, ncol),
        ]
        for i in range(d0, last - 1):        # zebra nas linhas de dados (sem o TOTAL)
            if (i - d0) % 2 == 1:
                reqs.append(_fmt(sid, i, i + 1, 0, ncol, {"backgroundColor": _c(ZEBRA)},
                            "backgroundColor"))
        for col, px in enumerate([110, 105, 70, 95, 100, 85, 85, 110, 135]):
            reqs.append(_width(sid, col, px))
        reqs.append({"updateSheetProperties": {"properties": {"sheetId": sid,
                     "gridProperties": {"frozenRowCount": 2}, "hidden": False},
                     "fields": "gridProperties.frozenRowCount,hidden"}})
        sheet.batch_update({"requests": reqs})


ADS_VIEW_TAB = "🔗 Anúncios"
ADS_VIEW_HEADER = ["Anúncio", "Campanha", "Invest (R$)", "Impressões", "Cliques", "CTR"]


def rebuild_ads_view() -> None:
    """Aba '🔗 Anúncios': um anúncio por linha (mês corrente), agregado, com LINK
    clicável para o post no LinkedIn. Lê a aba bruta 'Anúncios' (não a altera)."""
    sheet = sheets_client.open_sheet()
    try:
        master = sheet.worksheet("Anúncios")
    except Exception:
        return
    vals = master.get_all_values()
    if len(vals) < 2:
        return
    cur = date.today().strftime("%Y-%m")          # só o mês corrente
    ag: dict[str, dict] = {}
    for r in vals[1:]:
        if len(r) < 7 or not str(r[0]).startswith(cur):
            continue
        a = ag.setdefault(r[1] or "", {"camp": "", "link": "", "inv": 0.0, "imp": 0, "clk": 0})
        if r[2]:
            a["camp"] = r[2]
        if r[3]:
            a["link"] = r[3]
        a["inv"] += _num(r[4]); a["imp"] += int(_num(r[5])); a["clk"] += int(_num(r[6]))
    if not ag:
        return

    try:
        ws = sheet.worksheet(ADS_VIEW_TAB)
    except Exception:
        ws = sheet.add_worksheet(title=ADS_VIEW_TAB, rows=300, cols=len(ADS_VIEW_HEADER))
    sid = ws.id
    nc = len(ADS_VIEW_HEADER)

    rows = [[f"Vertigo · Anúncios do mês — {date.today().strftime('%m/%Y')}"] + [""] * (nc - 1),
            ADS_VIEW_HEADER]
    for _aid, a in sorted(ag.items(), key=lambda kv: kv[1]["inv"], reverse=True):
        ctr = (a["clk"] / a["imp"]) if a["imp"] else 0
        link = (a["link"] or "").replace('"', "")
        cell = f'=HYPERLINK("{link}";"Ver anúncio ▸")' if link else "(sem link)"
        rows.append([cell, a["camp"], round(a["inv"], 2), a["imp"], a["clk"], ctr])

    ws.clear()
    ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")

    d0, d1 = 2, len(rows)
    cur_f = {"numberFormat": {"type": "CURRENCY", "pattern": "R$ #,##0.00"}}
    intg = {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}
    pctf = {"numberFormat": {"type": "PERCENT", "pattern": "0.00%"}}
    reqs = [
        _fmt(sid, 0, len(rows) + 2, 0, nc, {},
             "backgroundColor,textFormat,borders,horizontalAlignment,numberFormat,wrapStrategy"),
        {"unmergeCells": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": len(rows) + 2,
                                    "startColumnIndex": 0, "endColumnIndex": nc}}},
        _merge(sid, 0, 1, 0, nc),
        _fmt(sid, 0, 1, 0, nc, {"backgroundColor": _c(NAVY), "verticalAlignment": "MIDDLE",
             "textFormat": {"bold": True, "fontSize": 13, "foregroundColor": _c(WHITE)}},
             "backgroundColor,verticalAlignment,textFormat"),
        _fmt(sid, 1, 2, 0, nc, {"backgroundColor": _c(NAVY), "horizontalAlignment": "CENTER",
             "textFormat": {"bold": True, "foregroundColor": _c(WHITE)}},
             "backgroundColor,horizontalAlignment,textFormat"),
        _fmt(sid, d0, d1, 2, 3, cur_f, "numberFormat"),
        _fmt(sid, d0, d1, 3, 4, intg, "numberFormat"),
        _fmt(sid, d0, d1, 4, 5, intg, "numberFormat"),
        _fmt(sid, d0, d1, 5, 6, pctf, "numberFormat"),
        _fmt(sid, d0, d1, 2, 6, {"horizontalAlignment": "CENTER"}, "horizontalAlignment"),
        _fmt(sid, d0, d1, 0, 1, {"textFormat": {"foregroundColor": _c((0.18, 0.42, 0.85)),
             "underline": True}}, "textFormat"),
        _border(sid, 1, d1, 0, nc),
    ]
    for i in range(d0, d1):
        if (i - d0) % 2 == 1:
            reqs.append(_fmt(sid, i, i + 1, 0, nc, {"backgroundColor": _c(ZEBRA)}, "backgroundColor"))
    for col, px in enumerate([150, 260, 120, 110, 90, 80]):
        reqs.append(_width(sid, col, px))
    reqs.append({"updateSheetProperties": {"properties": {"sheetId": sid,
                 "gridProperties": {"frozenRowCount": 2}}, "fields": "gridProperties.frozenRowCount"}})
    sheet.batch_update({"requests": reqs})


def format_chat_history() -> None:
    """Deixa a aba 'Histórico Chat' legível: cabeçalho, congela linha 1, larguras
    e quebra de texto nas colunas de pergunta/resposta."""
    sheet = sheets_client.open_sheet()
    try:
        ws = sheet.worksheet("Histórico Chat")
    except Exception:
        return
    sid = ws.id
    n = max(len(ws.col_values(1)), 2)
    reqs = [
        _fmt(sid, 0, 1, 0, 5, {"backgroundColor": _c(NAVY),
             "textFormat": {"bold": True, "foregroundColor": _c(WHITE)}},
             "backgroundColor,textFormat"),
        {"updateSheetProperties": {"properties": {"sheetId": sid,
         "gridProperties": {"frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}},
        _fmt(sid, 1, n, 3, 5, {"wrapStrategy": "WRAP", "verticalAlignment": "TOP",
             "textFormat": {"fontSize": 10}}, "wrapStrategy,verticalAlignment,textFormat"),
    ]
    for col, px in enumerate([120, 105, 110, 340, 620]):
        reqs.append(_width(sid, col, px))
    sheet.batch_update({"requests": reqs})


def hide_tab(name: str) -> None:
    """Oculta uma aba (continua legível pelo Looker/código; só some da vista)."""
    sheet = sheets_client.open_sheet()
    try:
        ws = sheet.worksheet(name)
    except Exception:
        return
    sheet.batch_update({"requests": [{"updateSheetProperties": {
        "properties": {"sheetId": ws.id, "hidden": True}, "fields": "hidden"}}]})


def rebuild_month(month_key: str) -> bool:
    """Gera/atualiza a aba de fechamento de um mês ('Resumo Ago/2026'), congelada
    (retrospectiva). Retorna True se criou a aba; False se o mês não tem dados."""
    y, m = int(month_key[:4]), int(month_key[5:7])
    start = date(y, m, 1)
    end = date(y, m, calendar.monthrange(y, m)[1])
    data = collect_campaign_data(start, end)
    if not data:
        return False
    period_label = f"{start.strftime('%d/%m')} a {end.strftime('%d/%m/%Y')}"
    analysis = analyst.run_analysis(period_label, data, ref_date=end, fechado=True)
    rebuild_summary(period_label, data, analysis, ref_date=end,
                    tab_name=_month_tab_name(month_key), fechado=True)
    return True


def _meses_com_dados() -> list[str]:
    """Meses (AAAA-MM) presentes na aba 'Campanhas', até o último mês FECHADO
    (exclui o mês corrente, que vive na aba '📊 Resumo' ao vivo)."""
    try:
        col = sheets_client.open_sheet().worksheet("Campanhas").col_values(1)[1:]
    except Exception:
        return []
    cur = date.today().strftime("%Y-%m")
    meses = set()
    for v in col:
        try:
            meses.add(date.fromisoformat(str(v).strip()).strftime("%Y-%m"))
        except (ValueError, AttributeError):
            continue
    return sorted(m for m in meses if m < cur)


def ensure_past_month_tabs() -> None:
    """Cria as abas de fechamento dos meses passados que ainda não existem.
    Idempotente: no regime normal (todas já existem) não faz nada. Roda na coleta
    diária, então o mês recém-fechado ganha sua aba automaticamente."""
    sheet = sheets_client.open_sheet()
    existentes = {ws.title for ws in sheet.worksheets()}
    for mk in _meses_com_dados():
        if _month_tab_name(mk) in existentes:
            continue
        try:
            if rebuild_month(mk):
                print(f"Aba de fechamento criada: {_month_tab_name(mk)}")
        except Exception as exc:
            print(f"  aviso: não gerei a aba {_month_tab_name(mk)}: {exc}")


def rebuild_all(period_label, start, end):
    """Reconstrói as visualizações organizadas após uma coleta."""
    data = collect_campaign_data(start, end)
    analysis = analyst.run_analysis(period_label, data, ref_date=end)
    rebuild_summary(period_label, data, analysis, ref_date=end)
    rebuild_per_campaign({c["nome"] for c in data})
    # Oculta os feeds brutos (seguem alimentando o Looker mesmo ocultos).
    for _bruta in ("Campanhas", "Anúncios"):
        try:
            hide_tab(_bruta)
        except Exception as exc:
            print(f"  aviso: não ocultei a aba {_bruta}: {exc}")
    # Aba "🔗 Anúncios" com links clicáveis dos posts (mês corrente).
    try:
        rebuild_ads_view()
    except Exception as exc:
        print(f"  aviso: não atualizei a aba de anúncios: {exc}")
    # Deixa a aba de histórico do chat legível.
    try:
        format_chat_history()
    except Exception as exc:
        print(f"  aviso: não formatei o histórico do chat: {exc}")
    # Garante as abas de fechamento dos meses passados (cria as que faltam).
    try:
        ensure_past_month_tabs()
    except Exception as exc:
        print(f"  aviso: não atualizei as abas mensais: {exc}")
