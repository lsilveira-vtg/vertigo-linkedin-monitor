"""Gera o relatório semanal/mensal como uma página HTML autocontida.

Usada para publicar no vtg-link (além do e-mail em texto). Recebe os mesmos
dados do report (campanhas + análise + orçamento) e devolve um documento HTML
completo, com CSS embutido (o vtg-link não serve assets externos).
"""
from datetime import date

from .analyst import Analysis
from . import budget

NAVY = "#1f3864"; ACCENT = "#2f6bd8"
GOOD = "#15803d"; WARN = "#b45309"; CRIT = "#c62828"
HEALTH = {"boa": ("🟢", GOOD), "atencao": ("🟡", WARN), "critica": ("🔴", CRIT)}
STATUS = {"ACTIVE": "Ativa", "PAUSED": "Pausada", "COMPLETED": "Concluída", "DRAFT": "Rascunho", "": "—"}


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def _brl2(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v) -> str:
    return f"{v * 100:.2f}%".replace(".", ",") if v is not None else "—"


def build_html_report(period_label: str, campaign_data: list[dict],
                      analysis: Analysis, ref_date: date | None = None) -> str:
    total_invest = sum(c.get("investimento_brl", 0) or 0 for c in campaign_data)
    lead_camps = [c for c in campaign_data if c.get("tipo", "leads") not in ("trafego", "branding")]
    invest_leads = sum(c.get("investimento_brl", 0) or 0 for c in lead_camps)
    total_leads = sum(c.get("leads", 0) or 0 for c in lead_camps)
    cpl_geral = invest_leads / total_leads if total_leads else None

    teto = consumo = None
    if ref_date is not None:
        st = budget.account_status(total_invest, ref_date)
        teto, consumo = st["teto"], st["consumo"]

    over = consumo is not None and consumo > 1.0
    kpis = [
        ("Investimento", _brl(total_invest), f"{len(campaign_data)} campanhas"),
        ("Leads", str(total_leads), "formulários do LinkedIn"),
        ("CPL geral", _brl(cpl_geral) if cpl_geral else "n/d", "campanhas de lead"),
        ("Consumo do teto", (f"{consumo*100:.0f}%" if consumo is not None else "n/d"),
         (f"{_brl(total_invest)} / {_brl(teto)}" if teto else "teto não configurado")),
    ]
    kpi_html = "".join(
        f'<div class="kpi{" crit" if (lab=="Consumo do teto" and over) else ""}">'
        f'<div class="lab">{lab}</div><div class="val">{val}</div><div class="sub">{sub}</div></div>'
        for lab, val, sub in kpis)

    alert = ""
    if over:
        alert = (f'<div class="alert"><b>⚠️ Orçamento acima do teto ({consumo*100:.0f}% do limite).</b> '
                 f'Gasto de {_brl(total_invest)} sobre um teto de {_brl(teto)} no mês.</div>')

    rows = ""
    order = sorted(campaign_data, key=lambda x: x.get("investimento_brl", 0) or 0, reverse=True)
    for c in order:
        emoji, color = HEALTH.get(_saude(c, analysis), ("", "#888"))
        traf = c.get("tipo") == "trafego"
        clk = c.get("cliques", 0) or 0
        clk_fmt = f"{clk:,}".replace(",", ".")
        cpc = _brl2(c["investimento_brl"] / clk) if (traf and clk) else "n/d"
        leads = "n/d" if traf else (c.get("leads", 0) or 0)
        cpl = "n/d" if (traf or not c.get("cpl_brl")) else _brl(c["cpl_brl"])
        tag = ' <span class="t">TRÁFEGO</span>' if traf else ""
        status = STATUS.get(c.get("status", ""), c.get("status", ""))
        rows += (f'<tr><td class="nm"><span style="color:{color}">{emoji}</span> {c["nome"]}{tag}</td>'
                 f'<td>{status}</td>'
                 f'<td class="r">{_brl(c.get("investimento_brl",0) or 0)}</td>'
                 f'<td class="r">{leads}</td><td class="r">{cpl}</td>'
                 f'<td class="r">{clk_fmt}</td>'
                 f'<td class="r">{cpc}</td><td class="r">{_pct(c.get("ctr"))}</td></tr>')

    acts = "".join(f"<li>{a}</li>" for a in analysis.acoes_prioritarias)
    rodape = f'<p class="rod">{analysis.rodape}</p>' if getattr(analysis, "rodape", "") else ""

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vertigo · Report LinkedIn — {period_label}</title>
<style>
 body{{margin:0;background:#f5f7fa;color:#16202e;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;line-height:1.5}}
 .wrap{{max-width:960px;margin:0 auto;padding:24px 18px 48px}}
 .head{{background:linear-gradient(140deg,{ACCENT},{NAVY});color:#fff;border-radius:16px;padding:22px 24px;margin-bottom:20px}}
 .head h1{{margin:0;font-size:20px;letter-spacing:-.01em}} .head p{{margin:6px 0 0;opacity:.85;font-size:13px}}
 .alert{{background:#fde3e3;border:1px solid #f1b0b0;color:#7c1d1d;border-radius:12px;padding:13px 16px;margin-bottom:18px;font-size:14px}}
 .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
 .kpi{{background:#fff;border:1px solid #dce1ea;border-radius:13px;padding:14px}}
 .kpi .lab{{font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:#5c6879}}
 .kpi .val{{font-size:26px;font-weight:800;margin-top:6px;letter-spacing:-.02em}}
 .kpi .sub{{font-size:11.5px;color:#5c6879;margin-top:4px}} .kpi.crit .val{{color:{CRIT}}}
 .card{{background:#fff;border:1px solid #dce1ea;border-radius:14px;padding:18px 20px;margin-bottom:18px}}
 .card h2{{margin:0 0 12px;font-size:15px}}
 table{{width:100%;border-collapse:collapse;font-size:13px}}
 th{{text-align:right;font-size:10.5px;letter-spacing:.04em;text-transform:uppercase;color:#5c6879;padding:8px 10px;border-bottom:1px solid #dce1ea}}
 th:first-child,td.nm{{text-align:left}} td{{padding:10px;border-bottom:1px solid #eef1f6;font-variant-numeric:tabular-nums}} td.r{{text-align:right}}
 .nm{{font-weight:600}} .t{{font-size:9.5px;font-weight:700;color:{ACCENT};background:#e8f0fc;padding:1px 5px;border-radius:4px}}
 .card ol{{margin:0;padding-left:20px}} .card li{{margin:7px 0;font-size:14px}}
 .sum{{font-size:14px}} .rod{{color:#5c6879;font-size:12px;margin-top:14px}}
 .foot{{color:#8a93a3;font-size:12px;text-align:center;margin-top:8px}}
 @media(max-width:640px){{.kpis{{grid-template-columns:repeat(2,1fr)}} .tbl{{overflow-x:auto}}}}
</style></head><body><div class="wrap">
 <div class="head"><h1>Vertigo · Mídia Paga LinkedIn</h1><p>Report do período {period_label} · gerado pelo agente</p></div>
 {alert}
 <div class="kpis">{kpi_html}</div>
 <div class="card"><h2>Análise do agente</h2><p class="sum">{analysis.resumo_executivo}</p>{rodape}</div>
 <div class="card"><h2>Ações prioritárias</h2><ol>{acts}</ol></div>
 <div class="card"><h2>Campanhas</h2><div class="tbl"><table>
   <tr><th>Campanha</th><th>Status</th><th>Invest.</th><th>Leads</th><th>CPL</th><th>Cliques</th><th>CPC</th><th>CTR</th></tr>
   {rows}</table></div></div>
 <p class="foot">Leads = formulários do LinkedIn (MQLs vêm do CRM e podem diferir). Gerado automaticamente.</p>
</div></body></html>"""


def _saude(c: dict, analysis: Analysis) -> str:
    for v in analysis.campanhas:
        if v.nome == c["nome"]:
            return v.saude
    return ""
