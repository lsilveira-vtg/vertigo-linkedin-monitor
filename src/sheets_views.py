"""Visualizações organizadas na planilha:

- "📊 Resumo": uma linha por campanha com totais do período, status, saúde,
  diagnóstico do agente e bloco de orçamento. A aba que se abre e entende tudo.
- Uma aba por campanha: histórico diário separado e limpo de cada campanha,
  derivado da aba bruta "Campanhas" (que continua alimentando o dashboard).
"""
import re
import time

from . import analyst, sheets_client
from .report_builder import MONTHLY_BUDGETS, collect_campaign_data

RESUMO_TAB = "📊 Resumo"

SAUDE_LABEL = {"boa": "🟢 Boa", "atencao": "🟡 Atenção", "critica": "🔴 Crítica"}
STATUS_LABEL = {"ACTIVE": "Ativa", "PAUSED": "Pausada", "DRAFT": "Rascunho",
                "COMPLETED": "Concluída", "": "—"}

RESUMO_HEADER = [
    "Campanha", "Tipo", "Status", "Saúde", "Invest (R$)", "Leads", "CPL (R$)",
    "Impressões", "Cliques", "CTR", "Diagnóstico", "Recomendação",
]


def _tab_name(nome: str) -> str:
    """Nome de aba seguro: sem caracteres proibidos, curto."""
    # Tira o sufixo "[...]" e caracteres invalidos para titulo de aba
    base = re.sub(r"\[.*?\]", "", nome)
    base = re.sub(r"[:\\/?*\[\]]", "", base).strip(" ·-")
    return base[:40] or "Campanha"


def rebuild_summary(period_label: str, campaign_data: list[dict], analysis: analyst.Analysis) -> None:
    """Reescreve a aba 📊 Resumo do zero com os dados do período."""
    sheet = sheets_client.open_sheet()
    try:
        ws = sheet.worksheet(RESUMO_TAB)
    except Exception:
        ws = sheet.add_worksheet(title=RESUMO_TAB, rows=200, cols=len(RESUMO_HEADER))
    ws.clear()

    verdict_by_name = {v.nome: v for v in analysis.campanhas}
    rows = [
        [f"Vertigo · Resumo LinkedIn Ads — {period_label}"],
        [],
        RESUMO_HEADER,
    ]
    for c in campaign_data:
        v = verdict_by_name.get(c["nome"])
        rows.append([
            c["nome"],
            c.get("tipo", ""),
            STATUS_LABEL.get(c.get("status", ""), c.get("status", "")),
            SAUDE_LABEL.get(v.saude, "") if v else "",
            c.get("investimento_brl", 0),
            c.get("leads", 0),
            c.get("cpl_brl") if c.get("cpl_brl") is not None else "—",
            c.get("impressoes", 0),
            c.get("cliques", 0),
            f"{c['ctr'] * 100:.2f}%" if c.get("ctr") is not None else "—",
            v.diagnostico if v else "",
            v.recomendacao if v else "",
        ])

    # Bloco de orçamento mensal
    rows += [[], ["— Orçamento mensal —"]]
    for grupo, limite in MONTHLY_BUDGETS.items():
        rows.append([grupo, "", "", "", "", "", "", "", "", "", f"limite {limite:.0f}", ""])

    # Resumo executivo do agente no rodapé
    rows += [[], ["— Análise do agente —"], [analysis.resumo_executivo]]

    ws.update(values=rows, range_name="A1")

    # Formatação: título, cabeçalho, larguras
    last_col = chr(ord("A") + len(RESUMO_HEADER) - 1)
    ws.merge_cells(f"A1:{last_col}1")
    ws.format("A1", {"textFormat": {"bold": True, "fontSize": 13}})
    ws.format(f"A3:{last_col}3", sheets_client.HEADER_FORMAT)
    ws.freeze(rows=3)
    ws.format("E4:I200", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
    ws.format("E4:E200", sheets_client.CURRENCY_FORMAT)
    ws.format("G4:G200", sheets_client.CURRENCY_FORMAT)


def rebuild_per_campaign() -> None:
    """Cria/atualiza uma aba por campanha a partir da aba bruta 'Campanhas'."""
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
    # Header da aba por campanha = igual ao master mas sem a coluna "Campanha"
    sub_header = [h for i, h in enumerate(header) if i != name_idx]

    for nome, linhas in grupos.items():
        tab = _tab_name(nome)
        if tab not in existing:
            ws = sheet.add_worksheet(title=tab, rows=400, cols=len(sub_header))
            existing.add(tab)
        else:
            ws = sheet.worksheet(tab)
        ws.clear()
        data = [sub_header] + [
            [v for i, v in enumerate(linha) if i != name_idx] for linha in linhas
        ]
        ws.update(values=data, range_name="A1")
        # Formatação leve (poucas chamadas) — cabeçalho + linha congelada
        last_col = chr(ord("A") + len(sub_header) - 1)
        ws.format(f"A1:{last_col}1", sheets_client.HEADER_FORMAT)
        ws.freeze(rows=1)
        time.sleep(2)  # respeita o limite de escrita por minuto do Sheets


def rebuild_all(period_label: str, start, end) -> None:
    """Reconstrói todas as visualizações organizadas após uma coleta."""
    data = collect_campaign_data(start, end)
    analysis = analyst.run_analysis(period_label, data, ref_date=end)
    rebuild_summary(period_label, data, analysis)
    rebuild_per_campaign()
