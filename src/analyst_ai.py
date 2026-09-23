"""Camada opcional de análise por IA (Claude API).

Só é usada quando ANTHROPIC_API_KEY está configurada. Produz a mesma estrutura
(Analysis) que o motor próprio em analyst.py, então o report formata igual.
Acrescenta análise contextual, cruzamento entre campanhas e padrões não previstos
nas regras. Não executa nenhuma ação — é consultiva.
"""
import json
import re

from . import config
from .analyst import Analysis, CampaignVerdict


def _limpar(texto: str) -> str:
    """Garante as regras de escrita mesmo que a IA escorregue: sem travessão e
    sem 'estourou/estourado' (usa 'acima do teto/limite')."""
    if not texto:
        return texto
    t = texto
    # travessão/meia-risca como pontuação -> vírgula; meia-risca em faixas (22–40) -> hífen
    t = t.replace(" — ", ", ").replace(" – ", ", ").replace("—", ", ")
    t = re.sub(r"(?<=\d)\s*–\s*(?=\d)", "-", t)  # 22–40 -> 22-40
    t = t.replace("–", ", ")
    # terminologia de orçamento
    t = re.sub(r"estourou o teto", "ficou acima do teto", t, flags=re.I)
    t = re.sub(r"estourou o limite", "ficou acima do limite", t, flags=re.I)
    t = re.sub(r"estourou", "ficou acima do teto", t, flags=re.I)
    t = re.sub(r"estourad[oa]s?", "acima do teto", t, flags=re.I)
    t = re.sub(r"estourar", "passar do teto", t, flags=re.I)
    t = re.sub(r"estouro", "excesso", t, flags=re.I)
    t = re.sub(r" {2,}", " ", t).replace(" ,", ",").replace(",,", ",")
    return t.strip()

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
- PRIORIZE OTIMIZAÇÃO ANTES DE PAUSAR. Para campanha com baixo desempenho, primeiro
  sugira melhorias concretas (novos criativos/ganchos, refino de segmentação, ajuste
  de oferta, revisão de formulário/landing, ajuste gradual de lance/budget). Pausar é
  ÚLTIMO RECURSO — só depois de tentativas de otimização não surtirem efeito (ex.: 1–2
  semanas), ou para estancar um gasto claramente perdido. Tom construtivo, não agressivo:
  proponha o caminho de melhoria, não apenas o corte.
- Recomende ações concretas; não execute nem prometa executar. A aprovação é humana.

REGRAS DE ESCRITA (obrigatórias):
- NUNCA use travessão ("—") nem meia-risca ("–") como pontuação. Use vírgula, ponto, \
dois-pontos ou parênteses no lugar.
- Ao descrever gasto acima do teto/limite, escreva "acima do teto" ou "acima do limite". \
NUNCA use "estourou", "estourado", "estourar" nem "estouro".
- Comece cada frase e cada bullet com letra maiúscula.

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
        resumo_executivo=_limpar(data["resumo_executivo"]),
        campanhas=[
            CampaignVerdict(
                nome=c["nome"],
                diagnostico=_limpar(c["diagnostico"]),
                saude=c["saude"],
                recomendacao=_limpar(c["recomendacao"]),
            )
            for c in data["campanhas"]
        ],
        acoes_prioritarias=[_limpar(a) for a in data["acoes_prioritarias"]],
        rodape=rodape,
    )


ASK_SYSTEM = SYSTEM_PROMPT + (
    "\n\nAgora você está respondendo a UMA pergunta do time no chat do painel. "
    "Responda de forma curta e direta (2-6 frases ou poucos bullets), sempre com base "
    "nos dados fornecidos. Se a pergunta não puder ser respondida com os dados, diga isso. "
    "Não invente números."
)


def answer_question(question: str, campaign_data: list[dict], budgets: dict | None = None) -> str:
    """Responde uma pergunta ao vivo (chat do dashboard) usando os dados atuais.

    Usa a IA se houver ANTHROPIC_API_KEY; senão devolve um aviso simples.
    O custo é registrado normalmente (aba Custos IA).
    """
    if not config.ANTHROPIC_API_KEY:
        return ("A resposta ao vivo por IA está indisponível (sem chave configurada). "
                "Consulte os KPIs e a tabela de campanhas no painel.")

    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    payload = {"campanhas": campaign_data, "orcamento": budgets or {}}
    user_msg = (f"Pergunta: {question}\n\nDados atuais:\n```json\n"
                f"{json.dumps(payload, ensure_ascii=False)}\n```")

    with client.messages.stream(
        model=config.ANALYST_MODEL,
        max_tokens=1200,
        system=ASK_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        response = stream.get_final_message()

    texto = "".join(b.text for b in response.content if b.type == "text").strip()
    try:
        from . import ai_costs
        ai_costs.log_and_summarize(response.usage, config.ANALYST_MODEL)
    except Exception as exc:
        print(f"  aviso: contador de custo falhou: {exc}")
    return _limpar(texto) or "Não consegui gerar uma resposta agora."

