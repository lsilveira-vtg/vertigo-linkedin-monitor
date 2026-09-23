"""Análise de desempenho das campanhas — motor próprio do agente.

Aplica heurísticas e benchmarks de mídia paga B2B (LinkedIn Ads) para produzir
um feedback no nível de um analista sênior, sem depender de API externa.
A análise é consultiva — não executa nenhuma ação nas campanhas.
"""
from dataclasses import dataclass, field

# Benchmarks calibrados com o histórico real da Vertigo (jul/2026).
# Base: campanhas de leads eficientes rodam a R$ 22–30; CPL médio (blended) da
# conta ~R$ 104; ponderado com tudo ~R$ 140. Régua para campanhas de LEADS:
CPL_BOM = 40.0            # <= R$ 40 = excelente (faixa das melhores campanhas)
CPL_ALTO = 100.0          # > R$ 100 = alerta (pior que a média da conta)
CTR_BOM = 0.0060          # CTR >= 0.60% é bom no LinkedIn
CTR_BAIXO = 0.0035        # CTR < 0.35% é fraco
ENGAGEMENT_BOM = 0.0100   # engagement rate >= 1% é bom para branding (base Vertigo ~0.12%)
ENGAGEMENT_BAIXO = 0.0010 # < 0.1% é fraco
GASTO_SEM_LEAD = 50.0     # gasto acima disso sem nenhum lead = crítico (campanha de leads)

# CPL de referência da conta (base histórica) — usado para contextualizar cada campanha.
CPL_REFERENCIA_CONTA = 104.0


@dataclass
class CampaignVerdict:
    nome: str
    diagnostico: str
    saude: str            # boa | atencao | critica
    recomendacao: str


@dataclass
class Analysis:
    resumo_executivo: str
    campanhas: list[CampaignVerdict] = field(default_factory=list)
    acoes_prioritarias: list[str] = field(default_factory=list)
    rodape: str = ""   # linha de custo da IA (vazio quando é o motor próprio)


def _brl(v: float) -> str:
    return f"R$ {v:,.0f}".replace(",", ".")


def _brl2(v: float) -> str:
    """Formata em reais com centavos (para valores pequenos, ex.: CPC)."""
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def _analisar_leads(c: dict) -> CampaignVerdict:
    invest = c.get("investimento_brl", 0) or 0
    leads = c.get("leads", 0) or 0
    cpl = c.get("cpl_brl")
    ctr = c.get("ctr")

    # Gasto relevante sem nenhum lead → crítico
    if leads == 0 and invest >= GASTO_SEM_LEAD:
        return CampaignVerdict(
            nome=c["nome"],
            diagnostico=f"Investiu {_brl(invest)} no período e não gerou nenhum lead. "
                        "O gasto sem conversão costuma vir de segmentação, criativo, oferta ou "
                        "do fluxo pós-clique (formulário/landing).",
            saude="critica",
            recomendacao="Otimizar antes de pausar: (1) testar novos criativos e ganchos; "
                         "(2) refinar a segmentação; (3) revisar a oferta e o formulário/landing. "
                         "Ajustar o lance/budget gradualmente. Se após 1–2 semanas de ajustes "
                         "ainda não gerar leads, aí sim considerar pausar.",
        )
    if leads == 0:
        return CampaignVerdict(
            nome=c["nome"],
            diagnostico=f"Sem leads no período, com gasto baixo ({_brl(invest)}). "
                        "Volume insuficiente para conclusão — pode ser só início de veiculação.",
            saude="atencao",
            recomendacao="Monitorar mais alguns dias antes de agir; se persistir sem leads, revisar a oferta.",
        )

    # Tem leads — avaliar CPL
    if cpl is not None and cpl > CPL_ALTO:
        diag = f"Gerou {leads} lead(s) a um CPL de {_brl(cpl)}, acima do limite saudável de {_brl(CPL_ALTO)}."
        rec = "Reduzir o budget diário e testar refinamento de segmentação/criativo para baixar o CPL."
        saude = "atencao"
    elif cpl is not None and cpl <= CPL_BOM:
        diag = f"Gerou {leads} lead(s) a um CPL de {_brl(cpl)} — eficiente, dentro ou abaixo da meta de {_brl(CPL_BOM)}."
        rec = "Manter e, se houver verba, considerar escalar o budget — é uma das campanhas mais eficientes."
        saude = "boa"
    else:
        diag = f"Gerou {leads} lead(s) a um CPL de {_brl(cpl)} — dentro da faixa aceitável."
        rec = "Manter e acompanhar a evolução do CPL."
        saude = "boa"

    # Complemento de CTR, se disponível
    if ctr is not None and ctr < CTR_BAIXO:
        diag += f" O CTR de {_pct(ctr)} está baixo, o que encarece a entrega."
        rec = "Testar novos criativos para elevar o CTR — " + rec.lower()
        if saude == "boa":
            saude = "atencao"
    return CampaignVerdict(nome=c["nome"], diagnostico=diag, saude=saude, recomendacao=rec)


def _analisar_branding(c: dict) -> CampaignVerdict:
    invest = c.get("investimento_brl", 0) or 0
    impressoes = c.get("impressoes", 0) or 0
    reacoes = c.get("reacoes", 0) or 0
    comentarios = c.get("comentarios", 0) or 0
    compart = c.get("compartilhamentos", 0) or 0
    engaj = (reacoes + comentarios + compart) / impressoes if impressoes else None

    if engaj is None or impressoes == 0:
        return CampaignVerdict(
            nome=c["nome"],
            diagnostico="Sem impressões registradas no período — nada a avaliar.",
            saude="atencao",
            recomendacao="Verificar se a campanha está ativa e com verba.",
        )
    if engaj >= ENGAGEMENT_BOM:
        diag = (f"Engagement rate de {_pct(engaj)} sobre {impressoes:,} impressões — forte para branding. "
                f"({reacoes} reações, {comentarios} coments, {compart} compart.)").replace(",", ".")
        rec = "Manter; o conteúdo está ressoando. Vale replicar o formato/tema em novas peças."
        saude = "boa"
    elif engaj < ENGAGEMENT_BAIXO:
        diag = (f"Engagement rate de {_pct(engaj)} sobre {impressoes:,} impressões — fraco. "
                "O conteúdo não está gerando interação relevante.").replace(",", ".")
        rec = "Revisar a linha criativa e o gancho do post; testar formatos diferentes."
        saude = "atencao"
    else:
        diag = f"Engagement rate de {_pct(engaj)} — dentro do esperado para branding B2B.".replace(",", ".")
        rec = "Manter e buscar ganhos incrementais com variações de criativo."
        saude = "boa"
    return CampaignVerdict(nome=c["nome"], diagnostico=diag, saude=saude, recomendacao=rec)


def _analisar_inmail(c: dict) -> CampaignVerdict:
    sends = c.get("sends", 0) or 0
    opens = c.get("opens", 0) or 0
    leads = c.get("leads", 0) or 0
    open_rate = opens / sends if sends else None
    if sends == 0:
        return CampaignVerdict(c["nome"], "Sem envios no período.", "atencao",
                               "Verificar se a campanha de InMail está ativa.")
    diag = f"{sends} envios com {_pct(open_rate)} de taxa de abertura e {leads} lead(s)."
    if leads == 0 and opens > 0:
        return CampaignVerdict(c["nome"], diag + " Boa abertura, mas sem conversão.", "atencao",
                               "Revisar a call-to-action e a oferta dentro do InMail.")
    return CampaignVerdict(c["nome"], diag, "boa", "Manter e acompanhar a conversão.")


def _analisar_trafego(c: dict) -> CampaignVerdict:
    """Campanha de tráfego/cliques: avalia por CPC e CTR, não por leads/CPL."""
    invest = c.get("investimento_brl", 0) or 0
    clicks = c.get("cliques", 0) or 0
    impr = c.get("impressoes", 0) or 0
    ctr = c.get("ctr")
    if clicks == 0:
        return CampaignVerdict(
            c["nome"],
            f"Sem cliques no período, com gasto de {_brl(invest)}.",
            "atencao",
            "Revisar criativo/gancho e segmentação para gerar tráfego.",
        )
    cpc = invest / clicks
    diag = f"Gerou {clicks} cliques a um CPC de {_brl2(cpc)}"
    if ctr is not None:
        diag += f" e CTR de {_pct(ctr)}"
    impr_fmt = f"{impr:,}".replace(",", ".")
    diag += f", sobre {impr_fmt} impressões."
    if ctr is not None and ctr >= CTR_BOM:
        rec = "Bom volume de tráfego — manter e, se houver verba, escalar gradualmente monitorando o CPC."
        saude = "boa"
    elif ctr is not None and ctr < CTR_BAIXO:
        rec = "CTR baixo encarece o clique — testar novos criativos/ganchos e refinar segmentação para baixar o CPC."
        saude = "atencao"
    else:
        rec = "Manter e acompanhar o CPC; testar criativos para melhorar o custo por clique."
        saude = "boa"
    return CampaignVerdict(c["nome"], diag, saude, rec)


def analyze(period_label: str, campaign_data: list[dict], budgets: dict | None = None,
            ref_date=None) -> Analysis:
    """Analisa os dados das campanhas e retorna o veredito estruturado.

    ref_date: data de referência (para checar teto mensal e datas-limite de
    orçamento). Se None, os alertas de orçamento são omitidos.
    """
    verdicts: list[CampaignVerdict] = []
    for c in campaign_data:
        tipo = c.get("tipo", "leads")
        if tipo == "branding":
            verdicts.append(_analisar_branding(c))
        elif tipo == "inmail":
            verdicts.append(_analisar_inmail(c))
        elif tipo == "trafego":
            verdicts.append(_analisar_trafego(c))
        else:
            verdicts.append(_analisar_leads(c))

    # Resumo executivo: panorama + destaque
    total_invest = sum(c.get("investimento_brl", 0) or 0 for c in campaign_data)
    # CPL geral considera só campanhas de lead (tráfego/branding não miram formulário).
    _lead_camps = [c for c in campaign_data if c.get("tipo", "leads") not in ("trafego", "branding")]
    _invest_leads = sum(c.get("investimento_brl", 0) or 0 for c in _lead_camps)
    total_leads = sum(c.get("leads", 0) or 0 for c in _lead_camps)
    cpl_geral = _invest_leads / total_leads if total_leads else None
    criticas = [v for v in verdicts if v.saude == "critica"]
    atencao = [v for v in verdicts if v.saude == "atencao"]

    partes = [
        f"No período, {len(campaign_data)} campanha(s) somaram {_brl(total_invest)} de investimento "
        f"e {total_leads} lead(s)" + (f" (CPL geral {_brl(cpl_geral)})." if cpl_geral else ".")
    ]
    # Contextualiza o CPL do período contra a base histórica da conta (~R$ 104)
    if cpl_geral is not None:
        if cpl_geral <= CPL_BOM:
            partes.append(f"CPL bem abaixo da média histórica da conta ({_brl(CPL_REFERENCIA_CONTA)}) — ótima eficiência.")
        elif cpl_geral > CPL_REFERENCIA_CONTA:
            partes.append(f"CPL acima da média histórica da conta ({_brl(CPL_REFERENCIA_CONTA)}) — atenção à eficiência.")
    if criticas:
        partes.append(f"{len(criticas)} campanha(s) em estado crítico exigem ação imediata.")
    elif atencao:
        partes.append(f"{len(atencao)} campanha(s) pedem atenção, mas nada crítico.")
    else:
        partes.append("Nenhum alerta crítico — operação saudável no período.")
    partes.append("(Leads = formulários do LinkedIn; MQLs vêm do CRM e podem diferir.)")
    resumo = " ".join(partes)

    # Alertas de orçamento (teto da conta + sub-limites/datas por campanha)
    budget_alerts: list[str] = []
    if ref_date is not None:
        from . import budget
        st = budget.account_status(total_invest, ref_date)
        if st["teto"] and st["consumo"] is not None and st["consumo"] > 1.0:
            budget_alerts.append(
                f"Conta ultrapassou o teto de {_brl(st['teto'])} do mês "
                f"({_brl(st['gasto'])} gastos). Reduzir budgets imediatamente."
            )
        elif st["teto"] and st["consumo"] is not None and st["consumo"] >= 0.90:
            budget_alerts.append(
                f"Conta em {_pct(st['consumo'])} do teto de {_brl(st['teto'])} "
                f"({_brl(st['gasto'])}). Atenção para não passar do teto."
            )
        for c in campaign_data:
            budget_alerts += budget.campaign_alerts(
                c["nome"], c.get("investimento_brl", 0) or 0, ref_date
            )
        if st["teto"]:
            resumo += f" Teto do mês: {_brl(st['teto'])} (consumo {_pct(st['consumo']) if st['consumo'] else 'n/d'})."

    # Ações prioritárias: orçamento primeiro (mais sensível), depois críticas e atenção
    acoes: list[str] = list(budget_alerts)
    for v in criticas + atencao:
        acoes.append(f"{v.nome}: {v.recomendacao}")
    if not acoes:
        # Destacar oportunidade de escalar a melhor campanha de leads
        boas = [c for c in campaign_data
                if (c.get("cpl_brl") is not None and c["cpl_brl"] <= CPL_BOM)]
        if boas:
            melhor = min(boas, key=lambda x: x["cpl_brl"])
            acoes.append(f"{melhor['nome']}: melhor CPL do período ({_brl(melhor['cpl_brl'])}) — "
                         "considerar escalar o budget.")
        else:
            acoes.append("Manter a operação e seguir monitorando — sem ações urgentes.")

    return Analysis(resumo_executivo=resumo, campanhas=verdicts, acoes_prioritarias=acoes)


def run_analysis(period_label: str, campaign_data: list[dict], budgets: dict | None = None,
                 ref_date=None) -> Analysis:
    """Ponto de entrada único. Usa a camada de IA se ANTHROPIC_API_KEY estiver
    configurada (com fallback para o motor próprio em caso de erro); senão usa
    o motor próprio de regras. Os alertas de orçamento (ref_date) são sempre
    aplicados pelo motor próprio, mesmo quando a IA gera a análise."""
    from . import config
    if config.ANTHROPIC_API_KEY:
        try:
            from . import analyst_ai
            # Enriquece o contexto de orçamento da IA com o teto do mês e o consumo,
            # para o resumo não dizer "sem dados de orçamento" quando a regra existe.
            budgets_ia = dict(budgets or {})
            if ref_date is not None:
                from . import budget
                total_invest = sum(c.get("investimento_brl", 0) or 0 for c in campaign_data)
                st = budget.account_status(total_invest, ref_date)
                if st["teto"] is not None:
                    budgets_ia["conta"] = {
                        "mes": st["mes"],
                        "teto_mensal_brl": st["teto"],
                        "gasto_periodo_brl": st["gasto"],
                        "consumo_do_teto": st["consumo"],
                    }
            result = analyst_ai.analyze(period_label, campaign_data, budgets_ia)
            # Garante os alertas de orçamento no topo, independentemente da camada IA
            if ref_date is not None:
                base = analyze(period_label, campaign_data, budgets, ref_date)
                extra = [a for a in base.acoes_prioritarias if a not in result.acoes_prioritarias]
                # mantém só os alertas de orçamento (vêm primeiro no motor próprio)
                orc = [a for a in extra if "teto" in a.lower() or "sub-limite" in a.lower()
                       or "PAUSADA" in a or "expirou" in a]
                result.acoes_prioritarias = orc + result.acoes_prioritarias
            return result
        except Exception as exc:
            print(f"  aviso: análise por IA falhou ({exc}); usando motor próprio.")
    return analyze(period_label, campaign_data, budgets, ref_date)


def format_analysis(analysis: Analysis) -> str:
    """Formata a análise em texto legível (para e-mail / Discord)."""
    emoji = {"boa": "🟢", "atencao": "🟡", "critica": "🔴"}
    lines = ["🧠 ANÁLISE DO AGENTE", ""]
    lines.append(analysis.resumo_executivo)
    lines.append("")
    lines.append("— Por campanha —")
    for c in analysis.campanhas:
        lines.append(f"{emoji.get(c.saude, '•')} {c.nome}")
        lines.append(f"  {c.diagnostico}")
        lines.append(f"  → {c.recomendacao}")
    lines.append("")
    lines.append("— Ações prioritárias —")
    for i, acao in enumerate(analysis.acoes_prioritarias, 1):
        lines.append(f"{i}. {acao}")
    if analysis.rodape:
        lines.append("")
        lines.append(analysis.rodape)
    return "\n".join(lines)
