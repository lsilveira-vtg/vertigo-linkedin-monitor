"""Teste manual da análise do agente (camada IA se ANTHROPIC_API_KEY existir).

Coleta os dados do mês corrente e imprime a análise no log do job — sem enviar
e-mail nem alterar a planilha. Serve para validar a análise por IA em produção.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src import analyst, config
from src.report_builder import collect_campaign_data


def main() -> None:
    hoje = date.today()
    inicio = hoje.replace(day=1)
    period = f"{inicio.strftime('%d/%m')} a {hoje.strftime('%d/%m/%Y')}"

    camada = "IA (Claude)" if config.ANTHROPIC_API_KEY else "motor próprio (regras)"
    print(f"=== Teste de análise — {period} — camada: {camada} ===\n")

    data = collect_campaign_data(inicio, hoje)
    analysis = analyst.run_analysis(period, data, ref_date=hoje)
    print(analyst.format_analysis(analysis))


if __name__ == "__main__":
    main()
