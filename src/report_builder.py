"""Monta o report de um periodo a partir dos dados do LinkedIn.

Conecta a coleta (linkedin_client) ao formato padrao (report).
A classificacao de cada campanha (leads/branding/inmail, emoji, budget)
fica em CAMPAIGN_CONFIG — ajustar quando as campanhas reais estiverem
disponiveis apos a aprovacao da API.
"""
import json
import os
from datetime import date

from . import linkedin_client
from .report import CampaignReport, format_report

# Configuracao por campanha: id -> propriedades de exibicao (emoji, type, display, note, budget_cap).
# Padrao no codigo (nao sensivel: id + tipo + rotulo de exibicao) garante a
# classificacao correta mesmo sem a variavel no ambiente. O Secret
# CAMPAIGN_CONFIG_JSON, quando presente, sobrescreve/complementa.
# Formato: {"123456": {"emoji": "...", "type": "leads", "display": "..."}}
# Códigos reais confirmados no Campaign Manager (13/11/2026). Os conjuntos de
# LEADS (padrão) NÃO precisam entrar aqui. Só os que NÃO são leads — avaliados por
# alcance/engajamento (CPC/CTR), nunca por CPL:
_DEFAULT_CAMPAIGN_CONFIG: dict[str, dict] = {
    # Artigos - Bruno = trafego/engajamento: avaliar por cliques/CPC/CTR, não por leads/CPL.
    "377232663": {"type": "trafego", "display": "Artigos - Bruno", "emoji": "📊"},
    # Impulsionamento - IA no Canal do Corretor (Liferay) = conhecimento da marca (alcance).
    "775502383": {"type": "branding", "display": "Impulsionamento - IA no Canal do Corretor", "emoji": "📣"},
    # Darkpost - Case CNP Seguradora (Liferay, marca) = alcance.
    "810057963": {"type": "branding", "display": "Darkpost - Case CNP Seguradora", "emoji": "📣"},
}
CAMPAIGN_CONFIG: dict[str, dict] = {
    **_DEFAULT_CAMPAIGN_CONFIG,
    **json.loads(os.getenv("CAMPAIGN_CONFIG_JSON", "{}")),
}

# Limites de orcamento mensal por grupo (dados sensiveis) — vem do Secret MONTHLY_BUDGETS_JSON.
# Formato: {"Grupo": limite_em_reais}
MONTHLY_BUDGETS: dict[str, float] = json.loads(os.getenv("MONTHLY_BUDGETS_JSON", "{}"))

# RATEIO 50/50: campanhas (grupos de campanha) cujo gasto/orcamento deve entrar
# no painel pela metade (a Vertigo banca so 50%). Match por SUBSTRING no nome da
# campanha, case-insensitive. Ex.: "Liferay - Junho>Novembro26".
RATEIO_CAMPANHAS: tuple[str, ...] = ("liferay",)
RATEIO_FATOR: float = 0.5

# Tipo por SUBSTRING do nome, quando nao ha config por id (CAMPAIGN_CONFIG manda).
# Fallback caso um código mude. Marca/alcance da Liferay: "Impulsionamento - IA no
# Canal do Corretor" e "Darkpost - Case CNP Seguradora". Cuidado: o conjunto de LEADS
# "Liferay - Leads - Canal do Corretor + Case CNP" NÃO pode casar aqui (fica leads).
_TYPE_BY_NAME: tuple[tuple[str, str], ...] = (
    ("ia no canal do corretor", "branding"),
    ("darkpost - case cnp", "branding"),
)


def _tipo(cfg: dict, nome: str) -> str:
    """Tipo da campanha: config por id tem prioridade; senao casa por nome; senao leads."""
    if cfg.get("type"):
        return cfg["type"]
    low = (nome or "").lower()
    for sub, tipo in _TYPE_BY_NAME:
        if sub in low:
            return tipo
    return "leads"


def _group_names() -> dict[str, str]:
    """{id_do_grupo_de_campanha: nome}. Se a API falhar, retorna {} (sem rateio)."""
    try:
        return {str(g["id"]): (g.get("name") or "") for g in linkedin_client.get_campaign_groups()}
    except Exception as exc:
        print(f"  aviso: nao listei os grupos de campanha (rateio 50/50 nao aplicado): {exc}")
        return {}


def _fator_rateio(meta: dict, group_names: dict[str, str]) -> float:
    """0.5 se o grupo de anuncios pertence a uma campanha de rateio (ex.: Liferay)."""
    urn = str(meta.get("campaignGroup") or "")
    gid = urn.rsplit(":", 1)[-1]
    nome = group_names.get(gid, "").lower()
    return RATEIO_FATOR if any(t in nome for t in RATEIO_CAMPANHAS) else 1.0


def _aggregate(rows: list[dict]) -> dict[str, dict]:
    """Soma metricas diarias por campanha. A chave e o id numerico da campanha
    (extraido do URN em pivotValues, ex: urn:li:sponsoredCampaign:123 -> 123)."""
    out: dict[str, dict] = {}
    for row in rows:
        pivot = row.get("pivotValues", [""])[0]
        key = pivot.rsplit(":", 1)[-1]
        agg = out.setdefault(key, {})
        for metric in ("impressions", "clicks", "costInLocalCurrency", "oneClickLeads",
                       "likes", "comments", "shares", "sends", "opens"):
            agg[metric] = agg.get(metric, 0) + float(row.get(metric, 0) or 0)
    return out


def build_report_for_period(start: date, end: date) -> str:
    analytics = _aggregate(linkedin_client.get_analytics(start, end, pivot="CAMPAIGN"))
    campaigns_meta = {str(c["id"]): c for c in linkedin_client.get_campaigns()}
    group_names = _group_names()

    reports: list[CampaignReport] = []
    for campaign_id, metrics in analytics.items():
        cfg = CAMPAIGN_CONFIG.get(str(campaign_id), {})
        meta = campaigns_meta.get(campaign_id, {})
        nome = cfg.get("display", meta.get("name", str(campaign_id)))
        ctype = _tipo(cfg, nome)
        fator = _fator_rateio(meta, group_names)

        rep = CampaignReport(
            emoji=cfg.get("emoji", "📊"),
            name=nome,
            note=cfg.get("note", ""),
            kind=ctype,
            invest=metrics.get("costInLocalCurrency", 0) * fator,
        )
        if ctype == "trafego":
            rep.clicks = int(metrics.get("clicks", 0))
            rep.impressions = int(metrics.get("impressions", 0))
        elif ctype == "branding":
            rep.reactions = int(metrics.get("likes", 0))
            rep.comments = int(metrics.get("comments", 0))
            rep.shares = int(metrics.get("shares", 0))
            rep.impressions = int(metrics.get("impressions", 0))
        elif ctype == "inmail":
            rep.sends = int(metrics.get("sends", 0))
            rep.opens = int(metrics.get("opens", 0))
            rep.clicks = int(metrics.get("clicks", 0))
            rep.leads = int(metrics.get("oneClickLeads", 0))
            rep.budget_cap = cfg.get("budget_cap")
        else:
            rep.leads = int(metrics.get("oneClickLeads", 0))
        reports.append(rep)

    # Orçamento mensal: teto da conta (com override do mês) + sub-limites por campanha
    from . import budget
    total_gasto = sum(r.invest for r in reports)
    budgets: dict[str, tuple[float, float | None]] = {}
    teto = budget.total_cap(end.strftime("%Y-%m"))
    if teto is not None:
        budgets["Conta (total)"] = (total_gasto, teto)
    for campaign_id, metrics in analytics.items():
        cfg = CAMPAIGN_CONFIG.get(str(campaign_id), {})
        meta = campaigns_meta.get(campaign_id, {})
        nome = cfg.get("display", meta.get("name", str(campaign_id)))
        regra = budget.campaign_rule(nome)
        if regra and regra.get("limite_mensal"):
            gasto_real = metrics.get("costInLocalCurrency", 0) * _fator_rateio(meta, group_names)
            budgets[regra["chave"]] = (gasto_real, float(regra["limite_mensal"]))

    period = f"{start.strftime('%d/%m')} a {end.strftime('%d/%m/%Y')}"
    return format_report(period, reports, budgets, deltas={})


def collect_campaign_data(start: date, end: date) -> list[dict]:
    """Dados estruturados por campanha para a análise por IA (não formata texto)."""
    analytics = _aggregate(linkedin_client.get_analytics(start, end, pivot="CAMPAIGN"))
    campaigns_meta = {str(c["id"]): c for c in linkedin_client.get_campaigns()}
    group_names = _group_names()

    out: list[dict] = []
    for campaign_id, m in analytics.items():
        cfg = CAMPAIGN_CONFIG.get(str(campaign_id), {})
        meta = campaigns_meta.get(campaign_id, {})
        fator = _fator_rateio(meta, group_names)     # 0.5 nos grupos da Liferay
        invest = round(m.get("costInLocalCurrency", 0) * fator, 2)
        leads = int(m.get("oneClickLeads", 0))
        impressions = int(m.get("impressions", 0))
        clicks = int(m.get("clicks", 0))
        nome = cfg.get("display", meta.get("name", str(campaign_id)))
        out.append({
            "nome": nome,
            "tipo": _tipo(cfg, nome),
            "status": meta.get("status", ""),
            "rateio_5050": fator < 1.0,
            "investimento_brl": invest,
            "leads": leads,
            "cpl_brl": round(invest / leads, 2) if leads else None,
            "impressoes": impressions,
            "cliques": clicks,
            "ctr": round(clicks / impressions, 4) if impressions else None,
            "reacoes": int(m.get("likes", 0)),
            "comentarios": int(m.get("comments", 0)),
            "compartilhamentos": int(m.get("shares", 0)),
        })
    return out
