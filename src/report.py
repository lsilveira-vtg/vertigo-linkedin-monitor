"""Geracao dos reports semanal e mensal no formato padrao da Vertigo."""
from dataclasses import dataclass, field


@dataclass
class CampaignReport:
    emoji: str
    name: str
    note: str = ""          # ex: "campanha de branding/thought leadership"
    invest: float = 0.0
    leads: int | None = None
    mqls: int | None = None
    mqls_new: int | None = None
    reactions: int | None = None
    comments: int | None = None
    shares: int | None = None
    impressions: int | None = None
    sends: int | None = None
    opens: int | None = None
    clicks: int | None = None
    budget_cap: float | None = None  # para campanhas pontuais (ex: R$ 250)
    top_ads: list[dict] = field(default_factory=list)


def _brl(value: float) -> str:
    return f"R$ {value:,.0f}".replace(",", ".")


def _cpl(invest: float, leads: int | None) -> str:
    if not leads:
        return "—"
    return _brl(invest / leads)


def format_campaign(c: CampaignReport) -> str:
    lines = []
    title = f"{c.emoji} {c.name}"
    if c.note:
        title += f" — {c.note}"
    lines.append(title)

    if c.sends is not None:
        # Campanha de InMail
        cap = f" / {_brl(c.budget_cap)}" if c.budget_cap else ""
        pct = f" ({c.invest / c.budget_cap:.0%})" if c.budget_cap else ""
        open_rate = f" ({c.opens / c.sends:.1%})" if c.sends else ""
        ctr = (c.clicks or 0) / c.sends if c.sends else 0
        lines.append(f"Invest: {_brl(c.invest)}{cap}{pct} | Sends: {c.sends} | Opens: {c.opens}{open_rate}")
        lines.append(f"Cliques: {c.clicks or 0} (CTR {ctr:.2%}) | Leads: {c.leads or 0} | CPL: {_cpl(c.invest, c.leads)}")
    elif c.reactions is not None:
        # Campanha de engajamento/branding
        lines.append(
            f"Invest: {_brl(c.invest)} | Reações: {c.reactions} | "
            f"Comentários: {c.comments or 0} | Compartilhamentos: {c.shares or 0}"
        )
        if c.impressions:
            eng = (c.reactions + (c.comments or 0) + (c.shares or 0)) / c.impressions
            lines.append(f"Engagement rate: {eng:.2%} (sobre {c.impressions:,} impressões)".replace(",", "."))
        if c.top_ads:
            lines.append("Top 3 anúncios:")
            for ad in c.top_ads[:3]:
                lines.append(
                    f"- {ad['title']} — {ad['impressions']} impr | {ad['reactions']} reações | "
                    f"{ad['comments']} coments | {ad['shares']} compart | "
                    f"CTR {ad['ctr']:.2%} | {ad['url']}"
                )
    else:
        # Campanha de leads
        lines.append(f"Invest: {_brl(c.invest)} | Leads: {c.leads or 0} | CPL: {_cpl(c.invest, c.leads)}")
        if c.mqls is not None:
            lines.append(f"MQLs: {c.mqls} ({c.mqls_new or 0} novo{'s' if (c.mqls_new or 0) != 1 else ''})")

    return "\n".join(lines)


def format_report(
    period_label: str,
    campaigns: list[CampaignReport],
    budgets: dict[str, tuple[float, float]],  # nome -> (gasto, limite)
    deltas: dict[str, float],                  # metrica -> variacao (ex: 0.21)
) -> str:
    """Monta o report completo no formato padrao."""
    parts = [f"Vertigo | {period_label}", "——TRÁFEGO PAGO (LinkedIn)——", ""]

    for c in campaigns:
        parts.append(format_campaign(c))
        parts.append("")

    parts.append("——ORÇAMENTO MENSAL——")
    total = 0.0
    for name, (spent, cap) in budgets.items():
        total += spent
        parts.append(f"{name}: {_brl(spent)} / {_brl(cap)} ({spent / cap:.0%})")
    parts.append(f"Total: {_brl(total)}")

    if deltas:
        parts.append("")
        parts.append("Δ vs período anterior (MTD)")
        items = []
        for metric, delta in deltas.items():
            arrow = "▲" if delta >= 0 else "▼"
            items.append(f"{metric}: {arrow}{abs(delta):.0%}")
        parts.append(" | ".join(items))

    return "\n".join(parts)
