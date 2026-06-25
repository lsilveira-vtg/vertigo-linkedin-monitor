"""Backfill: coleta o historico diario de campanhas de um intervalo e grava na aba Campanhas.

Uso: python scripts/backfill.py [dias]   (padrao: 30)

A AdAnalytics com timeGranularity=DAILY ja retorna uma linha por campanha por dia
(com o campo dateRange), entao uma unica chamada cobre todo o periodo.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src import linkedin_client, sheets_client

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 30


def _d(obj: dict) -> date:
    return date(obj["year"], obj["month"], obj["day"])


def main() -> None:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=DAYS - 1)

    campaigns = linkedin_client.get_campaigns()
    names = {str(c["id"]): c.get("name", str(c["id"])) for c in campaigns}

    rows = linkedin_client.get_analytics(start, end, pivot="CAMPAIGN")
    out = []
    for r in rows:
        dr = r.get("dateRange", {}).get("start")
        if not dr:
            continue
        day = _d(dr)
        pivot = r.get("pivotValues", [""])[0]
        cid = pivot.rsplit(":", 1)[-1]
        invest = round(float(r.get("costInLocalCurrency", 0) or 0), 2)
        leads = int(r.get("oneClickLeads", 0) or 0)
        cpl = round(invest / leads, 2) if leads else ""
        out.append([
            day.isoformat(),
            names.get(cid, pivot),
            invest, leads, cpl,
            int(r.get("impressions", 0) or 0),
            int(r.get("clicks", 0) or 0),
            int(r.get("likes", 0) or 0),
            int(r.get("comments", 0) or 0),
            int(r.get("shares", 0) or 0),
        ])

    out.sort(key=lambda x: (x[0], x[1]))
    sheets_client.ensure_tabs()
    if out:
        sheets_client.append_rows("Campanhas", out)
    print(f"Backfill {start} a {end}: {len(out)} linhas gravadas.")


if __name__ == "__main__":
    main()
