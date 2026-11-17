"""CPL histórico por campanha (base: leads de formulário do LinkedIn).

Puxa os últimos 12 meses da AdAnalytics e calcula, por campanha, investimento,
leads (oneClickLeads) e CPL. Imprime no log E, se CPL_HIST_SHEET_ID estiver
configurado (planilha compartilhada com a conta de serviço), REESCREVE essa
planilha com os dados frescos — para ela não ficar desatualizada. Roda
semanalmente (agendamento) e também manualmente.

ATENÇÃO: o "lead" aqui é o formulário de lead do LinkedIn (oneClickLeads).
Não inclui MQLs nem conversões de site (que vêm do CRM), então o CPL pode
diferir do número reportado pelo time de vendas/CRM.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src import config, linkedin_client
from src.report_builder import CAMPAIGN_CONFIG


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _coletar(start: date, end: date) -> tuple[list[dict], float, int]:
    """Agrega invest/leads por campanha nos últimos 12 meses. Devolve
    (linhas ordenadas por invest, invest_total, leads_total)."""
    rows = linkedin_client.get_analytics(start, end, pivot="CAMPAIGN")
    campaigns_meta = {str(c["id"]): c for c in linkedin_client.get_campaigns()}

    agg: dict[str, dict] = {}
    for r in rows:
        cid = r.get("pivotValues", [""])[0].rsplit(":", 1)[-1]
        a = agg.setdefault(cid, {"invest": 0.0, "leads": 0})
        a["invest"] += float(r.get("costInLocalCurrency", 0) or 0)
        a["leads"] += int(r.get("oneClickLeads", 0) or 0)

    linhas: list[dict] = []
    tot_inv = 0.0
    tot_leads = 0
    for cid, a in sorted(agg.items(), key=lambda x: x[1]["invest"], reverse=True):
        if a["invest"] < 1:
            continue
        cfg = CAMPAIGN_CONFIG.get(cid, {})
        nome = cfg.get("display", campaigns_meta.get(cid, {}).get("name", cid))
        status = campaigns_meta.get(cid, {}).get("status", "")
        cpl = a["invest"] / a["leads"] if a["leads"] else None
        tot_inv += a["invest"]
        tot_leads += a["leads"]
        linhas.append({"nome": nome, "status": status, "invest": a["invest"],
                       "leads": a["leads"], "cpl": cpl})
    return linhas, tot_inv, tot_leads


def _escrever_planilha(linhas, tot_inv, tot_leads, start, end) -> None:
    """Reescreve a planilha separada do CPL histórico (CPL_HIST_SHEET_ID)."""
    from src import sheets_client
    cpl_geral = tot_inv / tot_leads if tot_leads else None
    hoje = date.today().strftime("%d/%m/%Y")
    valores = [
        ["Vertigo · CPL Histórico por Campanha — LinkedIn Ads"],
        [f"Período: {start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}  ·  "
         f"base: leads de formulário do LinkedIn (não inclui MQL/conversões de site do CRM)  ·  "
         f"atualizado em {hoje}"],
        [""],
        ["Campanha", "Status", "Investimento (R$)", "Leads", "CPL (R$)"],
    ]
    for l in linhas:
        cpl_val = round(l["cpl"], 2) if l["cpl"] else "— (sem leads)"
        valores.append([l["nome"], l["status"], round(l["invest"], 2), l["leads"], cpl_val])
    valores.append(["TOTAL", "", round(tot_inv, 2), tot_leads,
                    round(cpl_geral, 2) if cpl_geral else "—"])

    sh = sheets_client._client().open_by_key(config.CPL_HIST_SHEET_ID)
    ws = sh.sheet1
    ws.clear()
    ws.update(valores, "A1", value_input_option="USER_ENTERED")
    # Formatação leve
    ws.format("A1", {"textFormat": {"bold": True, "fontSize": 12}})
    ws.format("A2", {"textFormat": {"italic": True, "foregroundColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}})
    ws.format("A4:E4", {"textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                        "backgroundColor": {"red": 0.11, "green": 0.22, "blue": 0.40},
                        "horizontalAlignment": "CENTER"})
    ultima = len(valores)
    ws.format(f"C5:C{ultima}", {"numberFormat": {"type": "CURRENCY", "pattern": '"R$" #,##0.00'}})
    ws.format(f"E5:E{ultima}", {"numberFormat": {"type": "CURRENCY", "pattern": '"R$" #,##0.00'}})
    ws.format(f"A{ultima}:E{ultima}", {"textFormat": {"bold": True}})
    try:
        ws.freeze(rows=4)
        sh.batch_update({"requests": [
            {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS",
             "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 320}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": ws.id, "dimension": "COLUMNS",
             "startIndex": 2, "endIndex": 3}, "properties": {"pixelSize": 140}, "fields": "pixelSize"}},
        ]})
    except Exception:
        pass
    print(f"\nPlanilha do CPL histórico atualizada: "
          f"https://docs.google.com/spreadsheets/d/{config.CPL_HIST_SHEET_ID}")


def main() -> None:
    end = date.today()
    start = end - timedelta(days=365)
    print(f"=== CPL histórico por campanha — {start} a {end} (base: leads de formulário LinkedIn) ===\n")

    linhas, tot_inv, tot_leads = _coletar(start, end)
    for l in linhas:
        cpl_txt = _brl(l["cpl"]) if l["cpl"] else "— (sem leads)"
        print(f"{l['nome']} [{l['status']}]\n   Invest: {_brl(l['invest'])} | "
              f"Leads: {l['leads']} | CPL: {cpl_txt}")
    cpl_geral = tot_inv / tot_leads if tot_leads else None
    print(f"\nTOTAL: Invest {_brl(tot_inv)} | Leads {int(tot_leads)} | "
          f"CPL geral {_brl(cpl_geral) if cpl_geral else '—'}")
    print("\nObs: leads = formulários do LinkedIn; MQLs/conversões de site (CRM) não entram aqui.")

    if config.CPL_HIST_SHEET_ID:
        try:
            _escrever_planilha(linhas, tot_inv, tot_leads, start, end)
        except Exception as exc:
            print(f"\n  aviso: não consegui escrever na planilha do CPL histórico ({exc}).\n"
                  f"  Confirme que ela foi COMPARTILHADA (Editor) com a conta de serviço e que "
                  f"CPL_HIST_SHEET_ID está correto.")
    else:
        print("\n(CPL_HIST_SHEET_ID não configurado — só imprimi no log, não atualizei planilha.)")


if __name__ == "__main__":
    main()
