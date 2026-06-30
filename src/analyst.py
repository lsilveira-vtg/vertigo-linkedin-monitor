"""Análise de desempenho das campanhas por IA (analista de mídia paga sênior).

Usa a API da Claude (Anthropic) para analisar os dados coletados e produzir
um feedback preciso e acionável, no nível de um analista sênior. A análise é
puramente consultiva — não executa nenhuma ação nas campanhas.
"""
import json

import anthropic

from . import config

SYSTEM_PROMPT = """\
Você é um analista de mídia paga sênior especializado em LinkedIn Ads, \
com mais de 10 anos de experiência em campanhas B2B de tecnologia.

Você está analisando as campanhas da Vertigo, uma empresa de tecnologia B2B \
(consultoria, cloud, modernização de aplicações). Os objetivos típicos são \
geração de leads qualificados (MQLs) e branding/thought leadership.

Ao analisar, comporte-se como um analista sênior de verdade:
- Vá direto ao ponto. Lidere com o diagnóstico, não com a descrição dos números.
- Priorize: aponte primeiro o que tem maior impacto no resultado.
- Seja específico e quantitativo: cite os números que sustentam cada conclusão.
- Recomende ações concretas (pausar, ajustar budget, trocar criativo, refinar \
segmentação), sempre com a justificativa.
- Considere o contexto B2B: ciclos longos, CPL naturalmente mais alto que B2C, \
volume baixo é normal. Não alarme sobre coisas esperadas.
- Quando os dados forem insuficientes para uma conclusão, diga isso em vez de inventar.
- Não execute nem prometa executar ações — você recomenda; a aprovação é humana.

Responda em português do Brasil, em tom profissional e objetivo."""

# Schema da análise estruturada — garante consistência entre execuções.
ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "resumo_executivo": {
            "type": "string",
            "description": "2-4 frases com o panorama geral e o ponto mais importante do período.",
        },
        "campanhas": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "nome": {"type": "string"},
                    "diagnostico": {"type": "string", "description": "Avaliação direta do desempenho."},
                    "saude": {"type": "string", "enum": ["boa", "atencao", "critica"]},
                    "recomendacao": {"type": "string", "description": "Ação concreta recomendada."},
                },
                "required": ["nome", "diagnostico", "saude", "recomendacao"],
            },
        },
        "acoes_prioritarias": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Lista ordenada das ações de maior impacto, da mais para a menos urgente.",
        },
    },
    "required": ["resumo_executivo", "campanhas", "acoes_prioritarias"],
}


def analyze(period_label: str, campaign_data: list[dict], budgets: dict | None = None) -> dict:
    """Analisa os dados das campanhas e retorna a análise estruturada.

    campaign_data: lista de dicts com métricas por campanha (nome, tipo, invest,
    leads, cpl, impressões, cliques, reações, etc.).
    budgets: dict opcional {grupo: {"gasto": x, "limite": y}}.
    Retorna dict no formato de ANALYSIS_SCHEMA.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    payload = {
        "periodo": period_label,
        "campanhas": campaign_data,
        "orcamento_mensal": budgets or {},
    }
    user_msg = (
        "Analise o desempenho destas campanhas de LinkedIn Ads e produza o "
        "feedback no formato estruturado solicitado.\n\n"
        f"Dados do período:\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )

    with client.messages.stream(
        model=config.ANALYST_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA}},
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        response = stream.get_final_message()

    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def format_analysis(analysis: dict) -> str:
    """Formata a análise estruturada em texto legível (para e-mail / Discord)."""
    emoji = {"boa": "🟢", "atencao": "🟡", "critica": "🔴"}
    lines = ["🧠 ANÁLISE DO AGENTE (analista de mídia paga sênior)", ""]
    lines.append(analysis["resumo_executivo"])
    lines.append("")
    lines.append("— Por campanha —")
    for c in analysis["campanhas"]:
        lines.append(f"{emoji.get(c['saude'], '•')} {c['nome']}")
        lines.append(f"  {c['diagnostico']}")
        lines.append(f"  → {c['recomendacao']}")
    lines.append("")
    lines.append("— Ações prioritárias —")
    for i, acao in enumerate(analysis["acoes_prioritarias"], 1):
        lines.append(f"{i}. {acao}")
    return "\n".join(lines)
