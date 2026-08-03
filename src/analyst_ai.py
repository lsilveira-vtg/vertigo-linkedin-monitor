"""Camada opcional de análise por IA (Claude API).

Só é usada quando ANTHROPIC_API_KEY está configurada. Produz a mesma estrutura
(Analysis) que o motor próprio em analyst.py, então o report formata igual.
Acrescenta análise contextual, cruzamento entre campanhas e padrões não previstos
nas regras. Não executa nenhuma ação — é consultiva.
"""
import json

from . import config
from .analyst import Analysis, CampaignVerdict

SYSTEM_PROMPT = """\
Você é um analista de mídia paga sênior especializado em LinkedIn Ads, com mais \
de 10 anos de experiência em campanhas B2B de tecnologia (consultoria, cloud, \
modernização). Os objetivos típicos são geração de leads qualificados (MQLs) e \
branding/thought leadership.

BASE DE REFERÊNCIA (histórico real da Vertigo):
- Campanhas de leads eficientes rodam a CPL de R$ 22–40.
- CPL médio (blended) da conta: ~R$ 104. Acima disso é pior que a média.
- Use essa base para julgar cada campanha — não um padrão genérico de mercado.
- "Leads" aqui são formulários do LinkedIn; MQLs vêm do CRM e podem diferir.
  Deixe isso claro quando relevante e não confunda os dois.

Comporte-se como um analista sênior de verdade:
- Estilo: DIRETO e em bullets organizados. Cada ponto traz o dado + o porquê
  (o motivo/contexto por trás), de forma curta. Não escreva parágrafos longos.
- Lidere com o diagnóstico, não com a descrição dos números.
- Combine SEMPRE as duas lentes: eficiência (CPL, CTR, engajamento, leads) E
  orçamento (ritmo de gasto vs teto, sub-limites, realocação de verba). A melhor
  ação costuma equilibrar as duas — ex: cortar o desperdício e realocar para a
  campanha mais eficiente.
- Priorize o que tem maior impacto; ordene as ações da mais para a menos urgente.
- Cruze campanhas entre si e aponte padrões (concentração de gasto, saturação,
  descasamento entre objetivo declarado e função real, troca de eficiência).
- Considere o contexto B2B: ciclos longos, volume baixo é normal — não alarme
  sobre o esperado.
- Quando os dados forem insuficientes, diga isso em vez de inventar.
- Recomende ações concretas; não execute nem prometa executar — aprovação é humana.

Responda em português do Brasil, profissional, objetivo e em bullets."""

ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "resumo_executivo": {"type": "string"},
        "campanhas": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "nome": {"type": "string"},
                    "diagnostico": {"type": "string"},
                    "saude": {"type": "string", "enum": ["boa", "atencao", "critica"]},
                    "recomendacao": {"type": "string"},
                },
                "required": ["nome", "diagnostico", "saude", "recomendacao"],
            },
        },
        "acoes_prioritarias": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["resumo_executivo", "campanhas", "acoes_prioritarias"],
}


def analyze(period_label: str, campaign_data: list[dict], budgets: dict | None = None) -> Analysis:
    """Análise por IA. Retorna um Analysis (mesma estrutura do motor próprio)."""
    import anthropic  # import tardio — só carrega se a camada for usada

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    payload = {"periodo": period_label, "campanhas": campaign_data, "orcamento_mensal": budgets or {}}
    user_msg = (
        "Analise o desempenho destas campanhas de LinkedIn Ads e produza o feedback "
        "no formato estruturado solicitado.\n\n"
        f"Dados:\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
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

    data = json.loads(next(b.text for b in response.content if b.type == "text"))

    # Contador de custo (não gera chamada extra — usa os tokens da própria resposta)
    rodape = ""
    try:
        from . import ai_costs
        rodape = ai_costs.log_and_summarize(response.usage, config.ANALYST_MODEL)
    except Exception as exc:
        print(f"  aviso: contador de custo falhou: {exc}")

    return Analysis(
        resumo_executivo=data["resumo_executivo"],
        campanhas=[CampaignVerdict(**c) for c in data["campanhas"]],
        acoes_prioritarias=data["acoes_prioritarias"],
        rodape=rodape,
    )

