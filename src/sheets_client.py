"""Cliente do Google Sheets — atualiza as abas da planilha do monitor."""
import json

import gspread
from google.oauth2.service_account import Credentials

from . import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _client() -> gspread.Client:
    info = json.loads(config.GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def open_sheet() -> gspread.Spreadsheet:
    return _client().open_by_key(config.GOOGLE_SHEET_ID)


def ensure_tabs() -> None:
    """Garante que todas as abas esperadas existem na planilha."""
    sheet = open_sheet()
    existing = {ws.title for ws in sheet.worksheets()}
    for tab in config.SHEET_TABS:
        if tab not in existing:
            sheet.add_worksheet(title=tab, rows=1000, cols=26)


def append_rows(tab: str, rows: list[list]) -> None:
    """Acrescenta linhas ao final de uma aba."""
    ws = open_sheet().worksheet(tab)
    ws.append_rows(rows, value_input_option="USER_ENTERED")


def set_header(tab: str, header: list[str]) -> None:
    ws = open_sheet().worksheet(tab)
    if not ws.row_values(1):
        ws.update("A1", [header])
        format_tab(ws, num_cols=len(header))


HEADER_FORMAT = {
    "backgroundColor": {"red": 0.13, "green": 0.13, "blue": 0.13},
    "textFormat": {
        "foregroundColor": {"red": 1, "green": 1, "blue": 1},
        "bold": True,
    },
    "horizontalAlignment": "CENTER",
}

CURRENCY_FORMAT = {"numberFormat": {"type": "CURRENCY", "pattern": 'R$ #,##0.00'}}
PERCENT_FORMAT = {"numberFormat": {"type": "PERCENT", "pattern": "0.00%"}}
PLAIN_FORMAT = {"numberFormat": {"type": "NUMBER", "pattern": "0"}}


def format_tab(ws: gspread.Worksheet, num_cols: int) -> None:
    """Aplica a formatacao visual padrao: cabecalho escuro, linha congelada,
    moeda nas colunas de R$, percentual nas de taxa, e numero simples nas demais.
    As colunas nao-moeda sao explicitamente formatadas como numero para
    sobrescrever qualquer formatacao antiga grudada (ex: apos reordenar colunas)."""
    last_col = chr(ord("A") + num_cols - 1)
    ws.format(f"A1:{last_col}1", HEADER_FORMAT)
    ws.freeze(rows=1)

    header = ws.row_values(1)
    for idx, name in enumerate(header):
        col = chr(ord("A") + idx)
        rng = f"{col}2:{col}1000"
        if "R$" in name or "CPL" in name or "Invest" in name:
            ws.format(rng, CURRENCY_FORMAT)
        elif "%" in name or "rate" in name.lower() or "CTR" in name:
            ws.format(rng, PERCENT_FORMAT)
        elif name in ("Data", "Campanha", "Anúncio", "Grupo", "Mês", "Período (início)",
                      "Período (fim)", "Ação", "Motivo", "Status", "Aprovado por",
                      "Executado em", "Semana"):
            continue  # colunas de texto/data — nao mexe
        else:
            ws.format(rng, PLAIN_FORMAT)  # Leads, Impressões, Cliques, etc.
