"""Configuracao inicial da planilha: abas, cabecalhos e formatacao."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src import sheets_client

HEADERS = {
    "Campanhas": ["Data", "Campanha", "Invest (R$)", "Impressões", "Cliques",
                  "Leads", "Reações", "Comentários", "Compartilhamentos"],
    "Anúncios": ["Data", "Anúncio", "Invest (R$)", "Impressões", "Cliques",
                 "Reações", "Comentários", "Compartilhamentos"],
    "Budget Mensal": ["Mês", "Grupo", "Gasto (R$)", "Limite (R$)", "Consumo %"],
    "Histórico Semanal": ["Semana", "Campanha", "Invest (R$)", "Leads",
                          "CPL (R$)", "Impressões", "CTR %"],
    "Histórico Mensal": ["Mês", "Campanha", "Invest (R$)", "Leads",
                         "CPL (R$)", "Impressões", "CTR %"],
    "Recomendações": ["Data", "Campanha", "Ação", "Motivo", "Status",
                      "Aprovado por", "Executado em"],
}


def main() -> None:
    sheets_client.ensure_tabs()
    sheet = sheets_client.open_sheet()
    for tab, header in HEADERS.items():
        ws = sheet.worksheet(tab)
        ws.update("A1", [header])
        sheets_client.format_tab(ws, num_cols=len(header))
        print("OK:", tab)


if __name__ == "__main__":
    main()
