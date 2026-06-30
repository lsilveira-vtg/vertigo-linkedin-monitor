"""Análise de desempenho das campanhas — motor próprio do agente.

Aplica heurísticas e benchmarks de mídia paga B2B (LinkedIn Ads) para produzir
um feedback no nível de um analista sênior, sem depender de API externa.
A análise é consultiva — não executa nenhuma ação nas campanhas.
"""
from dataclasses import dataclass, field

# Benchmarks de referência para LinkedIn Ads B2B de tecnologia.
# Ajustar conforme o histórico real da conta for crescendo.
CTR_BOM = 0.0060          # CTR >= 0.60% é bom no LinkedIn
CTR_BAIXO = 0.0035        # CTR < 0.35% é fraco
CPL_BOM = 60.0            # CPL <= R$ 60 é bom para o segmento
CPL_ALTO = 120.0          # CPL > R$ 120 acende alerta
ENGAGEMENT_BOM = 0.0200   # engagement rate >= 2% é bom para branding
ENGAGEMENT_BAIXO = 0.0050 # < 0.5% é fraco
GASTO_SEM_LEAD = 50.0     # gasto acima disso sem nenhum lead = crítico (campanha de leads)


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


def _brl(v: float) -> str:
    return f"R$ {v:,.0f}".replace(",", ".")


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
                        "É o pior cenário de eficiência: dinheiro saindo sem retorno direto.",
            saude="critica",
            recomendacao="Pausar ou revisar urgentemente — checar segmentação, oferta e formulário. "
                         "Não faz sentido manter o gasto sem conversão.",
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


def analyze(period_label: str, campaign_data: list[dict], budgets: dict | None = None) -> Analysis:
    """Analisa os dados das campanhas e retorna o veredito estruturado."""
    verdicts: list[CampaignVerdict] = []
    for c in campaign_data:
        tipo = c.get("tipo", "leads")
        if tipo == "branding":
            verdicts.append(_analisar_branding(c))
        elif tipo == "inmail":
            verdicts.append(_analisar_inmail(c))
        else:
            verdicts.append(_analisar_leads(c))

    # Resumo executivo: panorama + destaque
    total_invest = sum(c.get("investimento_brl", 0) or 0 for c in campaign_data)
    total_leads = sum(c.get("leads", 0) or 0 for c in campaign_data)
    cpl_geral = total_invest / total_leads if total_leads else None
    criticas = [v for v in verdicts if v.saude == "critica"]
    atencao = [v for v in verdicts if v.saude == "atencao"]

    partes = [
        f"No período, {len(campaign_data)} campanha(s) somaram {_brl(total_invest)} de investimento "
        f"e {total_leads} lead(s)" + (f" (CPL geral {_brl(cpl_geral)})." if cpl_geral else ".")
    ]
    if criticas:
        partes.append(f"{len(criticas)} campanha(s) em estado crítico exigem ação imediata.")
    elif atencao:
        partes.append(f"{len(atencao)} campanha(s) pedem atenção, mas nada crítico.")
    else:
        partes.append("Nenhum alerta crítico — operação saudável no período.")
    resumo = " ".join(partes)

    # Ações prioritárias: críticas primeiro, depois atenção
    acoes: list[str] = []
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


def run_analysis(period_label: str, campaign_data: list[dict], budgets: dict | None = None) -> Analysis:
    """Ponto de entrada único. Usa a camada de IA se ANTHROPIC_API_KEY estiver
    configurada (com fallback para o motor próprio em caso de erro); senão usa
    o motor próprio de regras."""
    from . import config
    if config.ANTHROPIC_API_KEY:
        try:
            from . import analyst_ai
            return analyst_ai.analyze(period_label, campaign_data, budgets)
        except Exception as exc:
            print(f"  aviso: análise por IA falhou ({exc}); usando motor próprio.")
    return analyze(period_label, campaign_data, budgets)


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
    return "\n".join(lines)
