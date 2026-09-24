"""Job mensal (1o dia util): gera e envia o report do mes anterior."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import analyst, mailer, config
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

    period = f"{start.strftime('%d/%m')} a {end.strftime('%d/%m/%Y')}"
    body = build_report_for_period(start, end)

    data = analysis = None
    try:
        data = collect_campaign_data(start, end)
        analysis = analyst.run_analysis(period, data, ref_date=end)
        body += "\n\n" + analyst.format_analysis(analysis)
    except Exception as exc:
        print(f"  aviso: análise falhou: {exc}")

    # Publica como página no vtg-link e compartilha (além do e-mail).
    link = None
    if analysis and data is not None and config.REPORT_RECIPIENTS:
        try:
            from src import report_html, vtglink
            html = report_html.build_html_report(period, data, analysis, ref_date=end)
            fname = f"report-mensal-{end.strftime('%Y-%m')}.html"
            pagina = vtglink.publicar_e_compartilhar(
                html, fname, f"Vertigo · Report Mensal LinkedIn | {period}", config.REPORT_RECIPIENTS)
            link = pagina.get("url")
        except Exception as exc:
            print(f"  aviso: não publiquei no vtg-link: {exc}")

    if link:
        body += f"\n\n---\nVer online (requer login Vertigo): {link}"

    mailer.send_email(subject=f"Vertigo | Report Mensal LinkedIn | {period}", body=body)
    print(f"Report mensal {period} enviado.")


if __name__ == "__main__":
    main()
