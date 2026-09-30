"""Job mensal (1o dia util): fecha o mes anterior e envia o relatorio.

Congela o relatorio de FECHAMENTO robusto (7 secoes) e usa esse MESMO documento
no e-mail, garantindo que o e-mail e o PDF do painel sejam identicos (single source
of truth). O relatorio completo fica disponivel em /report?month=AAAA-MM."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import analyst, mailer, config, reports
from src.report_builder import build_report_for_period, collect_campaign_data


def is_first_business_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    first = d.replace(day=1)
    while first.weekday() >= 5:
        first += timedelta(days=1)
    return d == first


def main() -> None:
    today = date.today()
    if not is_first_business_day(today):
        print(f"{today} não é o primeiro dia útil do mês — nada a fazer.")
        return

    end = today.replace(day=1) - timedelta(days=1)   # ultimo dia do mes anterior
    start = end.replace(day=1)
    month_str = end.strftime("%Y-%m")

    period = f"{start.strftime('%d/%m')} a {end.strftime('%d/%m/%Y')}"
    body = build_report_for_period(start, end)   # KPIs e tabela em texto

    # Congela o relatório de FECHAMENTO robusto (grava RPT-M<mês> na planilha) e usa
    # esse mesmo documento no e-mail. Se a IA falhar, cai na análise simples.
    try:
        rel = reports.load_or_build_report(month=month_str)
        body += "\n\n" + reports.to_text(rel)
    except Exception as exc:
        print(f"  aviso: relatório robusto falhou, usando análise simples: {exc}")
        try:
            data = collect_campaign_data(start, end)
            analysis = analyst.run_analysis(period, data, ref_date=end)
            body += "\n\n" + analyst.format_analysis(analysis)
        except Exception as exc2:
            print(f"  aviso: análise falhou: {exc2}")

    # Link para o relatório completo (mesma fonte congelada), requer login Vertigo.
    body += (f"\n\n---\nRelatório completo (requer login Vertigo): "
             f"{config.PUBLIC_BASE_URL}/report?month={month_str}")

    mailer.send_email(subject=f"Vertigo | Report Mensal LinkedIn | {period}", body=body)
    print(f"Report mensal {period} enviado.")


if __name__ == "__main__":
    main()
