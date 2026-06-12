"""Job diario: coleta dados do LinkedIn Ads e atualiza a planilha."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import linkedin_client, sheets_client


def main() -> None:
    yesterday = date.today() - timedelta(days=1)

    campaigns = linkedin_client.get_campaigns()
    analytics = linkedin_client.get_analytics(yesterday, yesterday, pivot="CAMPAIGN")
    ad_analytics = linkedin_client.get_analytics(yesterday, yesterday, pivot="CREATIVE")

    names = {c["id"]: c.get("name", str(c["id"])) for c in campaigns}

    campaign_rows = []
    for row in analytics:
        pivot = row.get("pivotValues", [""])[0]
        invest = float(row.get("costInLocalCurrency", 0) or 0)
        leads = int(row.get("oneClickLeads", 0) or 0)
        cpl = round(invest / leads, 2) if leads else ""
        campaign_rows.append([
            yesterday.isoformat(),
            names.get(pivot, pivot),
            invest,
            leads,
            cpl,
            row.get("impressions", 0),
            row.get("clicks", 0),
            row.get("reactions", 0),
            row.get("comments", 0),
            row.get("shares", 0),
        ])

    ad_rows = []
    for row in ad_analytics:
        ad_rows.append([
            yesterday.isoformat(),
            row.get("pivotValues", [""])[0],
            row.get("costInLocalCurrency", 0),
            row.get("impressions", 0),
            row.get("clicks", 0),
            row.get("reactions", 0),
            row.get("comments", 0),
            row.get("shares", 0),
        ])

    sheets_client.ensure_tabs()
    sheets_client.set_header("Campanhas", [
        "Data", "Campanha", "Invest (R$)", "Leads", "CPL (R$)",
        "Impressões", "Cliques", "Reações", "Comentários", "Compartilhamentos",
    ])
    sheets_client.set_header("Anúncios", [
        "Data", "Anúncio", "Invest (R$)", "Impressões", "Cliques",
        "Reações", "Comentários", "Compartilhamentos",
    ])
    if campaign_rows:
        sheets_client.append_rows("Campanhas", campaign_rows)
    if ad_rows:
        sheets_client.append_rows("Anúncios", ad_rows)

    print(f"Coleta de {yesterday} concluída: {len(campaign_rows)} campanhas, {len(ad_rows)} anúncios.")


if __name__ == "__main__":
    main()
