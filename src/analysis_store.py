"""Análise do dia PERSISTIDA na planilha (gerada 1x/dia, igual para todos).

O painel não muda o texto a cada acesso: a leitura fica estável ao longo do dia
e sobrevive a reinícios/deploys. Renova quando vira o dia. Guarda um registro por
dia na aba "Análise do Dia"; lê sempre o mais recente daquele dia.
"""
import json

TAB = "Análise do Dia"
HEADER = ["Data", "Gerada em", "JSON"]


def _ws():
    from .sheets_client import open_sheet
    sh = open_sheet()
    try:
        return sh.worksheet(TAB)
    except Exception:
        ws = sh.add_worksheet(title=TAB, rows=60, cols=len(HEADER))
        ws.append_row(HEADER, value_input_option="RAW")
        return ws


def get(date_iso: str) -> dict | None:
    """Análise já gerada para `date_iso` (AAAA-MM-DD), ou None."""
    ws = _ws()
    col = ws.col_values(1)                       # coluna Data (inclui cabeçalho)
    for i in range(len(col), 1, -1):             # de baixo p/ cima: pega a mais recente
        if col[i - 1] == date_iso:
            row = (ws.row_values(i) + ["", "", ""])[:3]
            try:
                return json.loads(row[2]) if row[2] else None
            except Exception:
                return None
    return None


def save(date_iso: str, gerada_em: str, payload: dict) -> None:
    _ws().append_row([date_iso, gerada_em, json.dumps(payload, ensure_ascii=False)],
                     value_input_option="RAW")
