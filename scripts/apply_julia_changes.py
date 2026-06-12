"""Aplica os ajustes da Julia: coluna CPL e periodos nos historicos."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src import sheets_client
from setup_sheet import HEADERS

sheet = sheets_client.open_sheet()

for tab, header in HEADERS.items():
    ws = sheet.worksheet(tab)
    ws.clear()
    ws.update(values=[header], range_name="A1")
    sheets_client.format_tab(ws, num_cols=len(header))
    print("OK:", tab)

# Linha de exemplo com CPL calculado (100 / 2 = 50)
ws = sheet.worksheet("Campanhas")
ws.append_rows(
    [["2026-06-11", "[EXEMPLO - apagar depois]", 100, 2, 50, 5000, 50, 10, 1, 0]],
    value_input_option="USER_ENTERED",
)
print("Linha de exemplo recriada.")
