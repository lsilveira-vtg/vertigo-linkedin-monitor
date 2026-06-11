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
