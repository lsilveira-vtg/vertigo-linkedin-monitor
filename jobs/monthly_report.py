"""Job mensal (1o dia util): gera e envia o report do mes anterior."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import mailer
from src.report_builder import build_report_for_period


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

    mailer.send_email(subject=f"Vertigo | Report Mensal LinkedIn | {period}", body=body)
    print(f"Report mensal {period} enviado.")


if __name__ == "__main__":
    main()
