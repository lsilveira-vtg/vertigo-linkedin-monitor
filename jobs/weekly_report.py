"""Job semanal (segunda-feira): gera e envia o report da semana anterior."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import analyst, mailer, config
from src.report_builder import build_report_for_period, collect_campaign_data


def main() -> None:
    today = date.today()
    end = today - timedelta(days=1)          # domingo
    start = end - timedelta(days=6)          # segunda anterior

    period = f"{start.strftime('%d/%m')} a {end.strftime('%d/%m/%Y')}"
    body = build_report_for_period(start, end)

    # Análise do agente (IA se houver chave, senão motor próprio) — anexada ao report
    data = analysis = None
    try:
        data = collect_campaign_data(start, end)
        analysis = analyst.run_analysis(period, data, ref_date=end)
        body += "\n\n" + analyst.format_analysis(analysis)
    except Exception as exc:
        print(f"  aviso: análise falhou: {exc}")

    # Publica como página no vtg-link e compartilha com o time (além do e-mail).
    # Nunca interrompe o report: se o vtg-link falhar, o e-mail sai mesmo assim.
    link = None
    if analysis and data is not None and config.REPORT_RECIPIENTS:
        try:
            from src import report_html, vtglink
            html = report_html.build_html_report(period, data, analysis, ref_date=end)
            fname = f"report-semanal-{end.strftime('%Y-%m-%d')}.html"
            pagina = vtglink.publicar_e_compartilhar(
                html, fname, f"Vertigo · Report Semanal LinkedIn | {period}", config.REPORT_RECIPIENTS)
            link = pagina.get("url")
        except Exception as exc:
            print(f"  aviso: não publiquei no vtg-link: {exc}")

    if link:
        body += f"\n\n———\nVer online (requer login Vertigo): {link}"

    mailer.send_email(subject=f"Vertigo | Report Semanal LinkedIn | {period}", body=body)
    print(f"Report semanal {period} enviado.")


if __name__ == "__main__":
    main()
