"""CPL histórico por campanha (base: leads de formulário do LinkedIn).

Puxa os últimos 12 meses da AdAnalytics e calcula, por campanha, investimento,
leads (oneClickLeads) e CPL. Imprime no log — não altera planilha nem envia e-mail.

ATENÇÃO: o "lead" aqui é o formulário de lead do LinkedIn (oneClickLeads).
Não inclui MQLs nem conversões de site (que vêm do CRM), então o CPL pode
diferir do número reportado pelo time de vendas/CRM.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src import linkedin_client
from src.report_builder import CAMPAIGN_CONFIG


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> None:
    end = date.today()
    start = end - timedelta(days=365)
    print(f"=== CPL histórico por campanha — {start} a {end} (base: leads de formulário LinkedIn) ===\n")

    rows = linkedin_client.get_analytics(start, end, pivot="CAMPAIGN")
    campaigns_meta = {str(c["id"]): c for c in linkedin_client.get_campaigns()}

    # Agrega por campanha
    agg: dict[str, dict] = {}
    for r in rows:
        cid = r.get("pivotValues", [""])[0].rsplit(":", 1)[-1]
        a = agg.setdefault(cid, {"invest": 0.0, "leads": 0})
        a["invest"] += float(r.get("costInLocalCurrency", 0) or 0)
        a["leads"] += int(r.get("oneClickLeads", 0) or 0)

    # Ordena por investimento (maiores primeiro)
    linhas = []
    tot_inv = tot_leads = 0.0
    for cid, a in sorted(agg.items(), key=lambda x: x[1]["invest"], reverse=True):
        if a["invest"] < 1:
            continue
        cfg = CAMPAIGN_CONFIG.get(cid, {})
        nome = cfg.get("display", campaigns_meta.get(cid, {}).get("name", cid))
        status = campaigns_meta.get(cid, {}).get("status", "")
        cpl = a["invest"] / a["leads"] if a["leads"] else None
        tot_inv += a["invest"]; tot_leads += a["leads"]
        cpl_txt = _brl(cpl) if cpl else "— (sem leads)"
        linhas.append(f"{nome} [{status}]\n   Invest: {_brl(a['invest'])} | Leads: {a['leads']} | CPL: {cpl_txt}")

    for l in linhas:
        print(l)
    cpl_geral = tot_inv / tot_leads if tot_leads else None
    print(f"\nTOTAL: Invest {_brl(tot_inv)} | Leads {int(tot_leads)} | "
          f"CPL geral {_brl(cpl_geral) if cpl_geral else '—'}")
    print("\nObs: leads = formulários do LinkedIn; MQLs/conversões de site (CRM) não entram aqui.")


if __name__ == "__main__":
    main()
