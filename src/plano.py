"""Plano de mídia paga da Vertigo — Q4 2026 (fonte única).

Definido por Júlia e Vitor. O Vitor executa no Campaign Manager; cada mudança é
registrada aqui (a Júlia avisa) para os relatórios considerarem. Este módulo:

- CONTEXTO: bloco de texto AUTORITATIVO injetado nos prompts da IA (análise do
  painel, relatório PDF e chat), para o agente seguir as regras e os orçamentos
  do plano em vez dos valores genéricos antigos.
- Constantes/funções do patrocínio Liferay (teto total de R$ 7.200), usadas no
  acompanhamento de ritmo.

Como atualizar: quando o Vitor mudar algo, acrescente a linha em MUDANÇAS e, se
for orçamento, ajuste ORÇAMENTO DIÁRIO. Tetos mensais ficam em budget.py.
"""
from datetime import date

# ----------------------------------------------------------------------------
# Patrocínio Liferay (50/50): a Vertigo paga tudo e a Liferay reembolsa 50%.
# O teto de R$ 7.200 vale para a SOMA de tudo da Liferay (grupo de marca
# "IA no Canal do Corretor" + campanha nova "Liferay leads" + Case CNP).
# ----------------------------------------------------------------------------
LIFERAY_TETO_TOTAL = 7200.00          # teto do patrocínio (R$ 3.600 de cada lado)
LIFERAY_GASTO_BASE = 6119.15          # gasto acumulado (bruto) até a data base
LIFERAY_BASE_DATA = date(2026, 11, 10)
LIFERAY_FIM = date(2026, 11, 30)      # a campanha encerra nesta data


# Bloco autoritativo para os prompts da IA. Tem PRIORIDADE sobre os valores
# genéricos do SYSTEM_PROMPT (estrutura antiga de campanhas, tetos antigos etc.).
CONTEXTO = """

== PLANO DE MÍDIA PAGA — Q4 2026 (AUTORIDADE MÁXIMA, use SEMPRE) ==
Plano definido por Júlia e Vitor para usar a verba até o fim de 2026. O Vitor executa
no Campaign Manager do LinkedIn; cada mudança é registrada abaixo. Estes valores e
regras TÊM PRIORIDADE sobre qualquer estrutura/teto genérico citado antes.

REGRAS GERAIS (seguir sempre):
- NUNCA recomende PAUSAR nenhum conjunto de anúncios até 31/12/2026 — pausar reinicia o
  aprendizado. A ÚNICA alavanca de corte é REDUZIR a verba aos poucos (cerca de 20% por
  vez), até o PISO de R$ 20/dia por conjunto. Não sugira pausa em hipótese alguma.
- O orçamento diário é configurado por CONJUNTO de anúncios. Trate e reporte cada conjunto
  SEPARADO dos outros, num relatório único (para medir cada resultado).
- Os valores de referência de orçamento são os DESTE plano. IGNORE tetos antigos (ex.:
  R$ 1.500) e não os cite.
- Porte desejado dos leads: empresas com 200+ funcionários.
- Reporte leads TOTAIS e o custo por lead (CPL) de CADA conjunto. NÃO classifique leads por
  nível/senioridade (A/B/C/D) nem comente cargo do lead — isso está desligado por ora.

LIFERAY (patrocínio 50/50 — a Vertigo paga tudo e a Liferay reembolsa 50%):
- O grupo atual "IA no Canal do Corretor" é de CONHECIMENTO DA MARCA (alcance). Avalie-o por
  alcance, impressões e engajamento (CPC/CTR), NUNCA por leads/CPL, e NÃO o compare com os
  conjuntos de leads.
- Teto TOTAL do patrocínio: R$ 7.200 (R$ 3.600 de cada lado), somando TODOS os anúncios da
  Liferay (marca "IA no Canal do Corretor" + campanha nova "Liferay leads" + Case CNP). Gasto
  acumulado (bruto) até 10/11/2026: R$ 6.119,15 — restam cerca de R$ 1.080. A campanha encerra
  em 30/11/2026. Acompanhe o ritmo e ALERTE se o gasto projetar passar de R$ 7.200 até lá.

ORÇAMENTO DIÁRIO POR CONJUNTO (R$/dia, por data de vigência). Os nomes abaixo são EXATOS
como aparecem no Campaign Manager (código entre parênteses):
- Materiais Ricos - Segmentos (Financeiras) (cód. 276543063): 70 -> 56 (12/11) -> 45 (19/11)
  -> 30 (1/12) -> 20 (19/12)
- VeeCode - Materiais Ricos (cód. 296725553): 40 -> 32 (12/11) -> 26 (19/11) -> 20 (1/12)
- Artigos - Bruno (cód. 377232663 — tráfego/engajamento): 35 -> 28 (12/11) -> 22 (19/11)
  -> 20 (1/12)
- Impulsionamento - IA no Canal do Corretor (cód. 775502383 — Liferay, MARCA): 25/dia até 30/11
- Liferay - Leads - Canal do Corretor + Case CNP (cód. 902105083 — novo, leads): 28/dia de
  12/11 a 30/11
- EUA - FSI Florida - E-book AI Gateway (EN) (cód. 902243203 — inglês, leads): 25/dia de 13/11
  a 18/12 (pode seguir em 20/dia até 31/12 se o custo por lead do e-book ficar abaixo de
  R$ 150 em 14/12)
- Darkpost - Case CNP Seguradora (cód. 810057963 — Liferay, MARCA/alcance): conjunto de marca
  sob a campanha Liferay; avaliar por alcance, nunca por leads/CPL.

ESTRUTURA DE CAMPANHAS (campaignGroup) no Campaign Manager:
- "Campanhas Plano de Mídia - Vertigo": Materiais Ricos (Financeiras), VeeCode, Artigos - Bruno.
- "Liferay - Junho>Novembro26" (Conhecimento da marca): IA no Canal do Corretor, Darkpost Case CNP.
- "Liferay - Geração de Leads - Nov26": Liferay - Leads - Canal do Corretor + Case CNP.
- "EUA - E-book AI Gateway (EN) - Leads": EUA - FSI Florida - E-book AI Gateway (EN).
O rateio 50/50 vale para TUDO das duas campanhas Liferay (gasto entra pela metade no painel).

TETOS MENSAIS DE REFERÊNCIA (já com Liferay a 50% e o conjunto em inglês):
nov/2026 = R$ 4.600; dez/2026 = R$ 2.750.

MUDANÇAS REGISTRADAS (considerar conforme a data do período do relatório):
- 12/11: criada a campanha "Liferay leads" (R$ 28/dia, até 30/11); subida a campanha em inglês
  (e-book EUA, R$ 25/dia, entrou entre 13 e 16/11); 1ª redução de verba (Financeiras 56,
  VeeCode 32, Artigos do Bruno 28).
- 19/11: 2ª redução de verba (Financeiras 45, VeeCode 26, Artigos do Bruno 22).
- 23/11: diagnóstico VAIM em inglês entra como 2º anúncio do MESMO conjunto em inglês (os
  R$ 25/dia são do conjunto, não por anúncio); material novo do webinar e Case CNP entram na
  campanha "Liferay leads".
- 30/11: a campanha Liferay encerra — gerar o FECHAMENTO do período (gasto total e leads por
  criativo) para os prints de comprovação.
- 1/12: reduções (Financeiras 30, VeeCode 20, Artigos do Bruno 20).
- 19/12: Financeiras 20. O conjunto em inglês pode encerrar em 18/12 (ou seguir em 20/dia até
  31/12, conforme o custo por lead do e-book em 14/12).
"""


def liferay_projecao(fim: date = LIFERAY_FIM) -> dict:
    """Projeção determinística do gasto final da Liferay (bruto) vs o teto de R$ 7.200,
    a partir do gasto base e dos orçamentos diários planejados até o encerramento.

    Soma, dia a dia após a data base: R$ 25/dia do grupo de marca (até 30/11) + R$ 28/dia
    da campanha "Liferay leads" (a partir de 12/11). Serve de alerta de ritmo; o gasto real
    pode variar conforme a execução do Vitor."""
    gasto = LIFERAY_GASTO_BASE
    d = LIFERAY_BASE_DATA
    while d < fim:
        d = date.fromordinal(d.toordinal() + 1)
        if d <= LIFERAY_FIM:
            gasto += 25.0                      # marca "IA no Canal do Corretor"
            if d >= date(2026, 11, 12):
                gasto += 28.0                  # "Liferay leads" (novo, de 12/11)
    pct = gasto / LIFERAY_TETO_TOTAL if LIFERAY_TETO_TOTAL else None
    return {
        "teto": LIFERAY_TETO_TOTAL,
        "gasto_base": LIFERAY_GASTO_BASE,
        "projetado_fim": round(gasto, 2),
        "pct_projetado": pct,
        "estoura": gasto > LIFERAY_TETO_TOTAL,
        "fim": LIFERAY_FIM.isoformat(),
    }


def liferay_resumo(ref: date | None = None) -> dict | None:
    """Dados do banner do patrocínio Liferay no painel. Relevante só enquanto a
    campanha roda (o mês de encerramento, 11/2026). Fora disso retorna None."""
    ref = ref or date.today()
    if not (ref.year == LIFERAY_FIM.year and ref.month == LIFERAY_FIM.month):
        return None
    proj = liferay_projecao()
    return {
        "teto": LIFERAY_TETO_TOTAL,
        "gasto_base": LIFERAY_GASTO_BASE,
        "base_data": LIFERAY_BASE_DATA.strftime("%d/%m"),
        "restante": round(LIFERAY_TETO_TOTAL - LIFERAY_GASTO_BASE, 2),
        "projetado_fim": proj["projetado_fim"],
        "pct_base": LIFERAY_GASTO_BASE / LIFERAY_TETO_TOTAL,
        "pct_projetado": proj["pct_projetado"],
        "fim": LIFERAY_FIM.strftime("%d/%m"),
        "estoura": proj["estoura"],
    }
