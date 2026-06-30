"""Job semanal (segunda-feira): gera e envia o report da semana anterior."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import analyst, mailer
from src.report_builder import build_report_for_period, collect_campaign_data


def main() -> None:
    today = date.today()
    end = today - timedelta(days=1)          # domingo
    start = end - timedelta(days=6)          # segunda anterior

    period = f"{start.strftime('%d/%m')} a {end.strftime('%d/%m/%Y')}"
    body = build_report_for_period(start, end)

    # Análise do agente (IA se houver chave, senão motor próprio) — anexada ao report
    try:
        data = collect_campaign_data(start, end)
        analysis = analyst.run_analysis(period, data)
        body += "\n\n" + analyst.format_analysis(analysis)
    except Exception as exc:
        print(f"  aviso: análise falhou: {exc}")

    mailer.send_email(subject=f"Vertigo | Report Semanal LinkedIn | {period}", body=body)
    print(f"Report semanal {period} enviado.")


if __name__ == "__main__":
    main()
