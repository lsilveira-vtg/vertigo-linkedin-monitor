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
# O teto de R$ 7.200 vale para a SOMA de TUDO da Liferay (campanha de marca antiga
# + campanha nova de leads). Situação em 16/11/2026 (relatório do Vitor):
#   - Campanha de MARCA "Liferay - Junho>Novembro26" (1152903403): ENCERROU em 15/11,
#     gasto final FIXO de R$ 6.330,81 (não cresce mais; sem reativação).
#   - Campanha NOVA de leads "Liferay - Geração de Leads - Nov26" (1255513733): trava
#     total de R$ 530, roda de 12/11 a 30/11; gasto até 16/11 = R$ 114,98.
# ----------------------------------------------------------------------------
LIFERAY_TETO_TOTAL = 7200.00          # teto do patrocínio (R$ 3.600 de cada lado)
LIFERAY_ANTIGA_FINAL = 6330.81        # campanha de marca encerrada em 15/11 (valor final fixo)
LIFERAY_NOVA_TRAVA = 530.00           # trava total da campanha nova de leads (12/11-30/11)
LIFERAY_NOVA_GASTO = 114.98           # gasto da campanha nova até a data base
LIFERAY_BASE_DATA = date(2026, 11, 16)
LIFERAY_GASTO_BASE = round(LIFERAY_ANTIGA_FINAL + LIFERAY_NOVA_GASTO, 2)  # 6445.79 até 16/11
LIFERAY_FIM = date(2026, 11, 30)      # a campanha nova encerra nesta data


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
- APRENDIZADO: conjuntos recém-criados ou recém-ativados (Liferay leads; o inglês, quando
  subir) ficam ~7 dias em aprendizado. NÃO trate o resultado deles como definitivo na 1ª
  semana — contextualize que ainda estão calibrando.

LIFERAY (patrocínio 50/50 — a Vertigo paga tudo e a Liferay reembolsa 50%):
- Teto TOTAL do patrocínio: R$ 7.200 (R$ 3.600 de cada lado), somando TUDO da Liferay.
- A campanha de MARCA "Liferay - Junho>Novembro26" (alcance: "IA no Canal do Corretor" e
  "Darkpost - Case CNP Seguradora") ENCERROU em 15/11/2026, com gasto final de R$ 6.330,81.
  NÃO será reativada nem editada. A partir de 16/11 a Liferay roda SÓ pela campanha de leads.
- Campanha NOVA de leads "Liferay - Geração de Leads - Nov26": trava total de R$ 530, roda de
  12/11 a 30/11; gasto até 16/11 = R$ 114,98.
- Gasto Liferay acumulado (bruto) até 16/11/2026: R$ 6.445,79 — folga de R$ 754,21 no teto.
  Projeção até 30/11: no MÁXIMO R$ 6.860,81 (antiga fechada + trava de R$ 530 da nova) ≈ 95%
  do teto; NÃO estoura. Só alerte se o combinado projetar passar de R$ 7.200.
- Os conjuntos de marca da antiga só aparecem em períodos até 15/11; avalie-os por
  alcance/engajamento (CPC/CTR), NUNCA por leads/CPL, e não os compare com os de leads.

ORÇAMENTO DIÁRIO POR CONJUNTO (R$/dia, por data de vigência). Nomes EXATOS do Campaign
Manager (código entre parênteses):
- Materiais Ricos - Segmentos (Financeiras) (cód. 276543063): 70 -> 56 (12/11) -> 45 (19/11,
  só se a Júlia confirmar) -> 30 (1/12) -> 20 (19/12)
- VeeCode - Materiais Ricos (cód. 296725553): 40 -> 32 (12/11) -> 26 (19/11, se confirmado)
  -> 20 (1/12)
- Artigos - Bruno (cód. 377232663 — tráfego/engajamento): 35 -> 28 (12/11) -> 22 (19/11, se
  confirmado) -> 20 (1/12)
- Liferay - Leads - Canal do Corretor + Case CNP (cód. 902105083 — NOVO, leads): 28/dia de
  12/11 a 30/11. Público: Brasil, perfil em inglês, gerência+, 201+ funcionários, serviços
  financeiros. Tem 3 anúncios rodando DENTRO deste conjunto (Case CNP, Canal do Corretor 4x5
  e "IA no Canal do Corretor" criativo azul, criado em 16/11 e sob avaliação).
- EUA - FSI Florida - E-book AI Gateway (EN) (cód. 902243203 — inglês, leads): 25/dia, sem
  data final. AINDA NÃO ESTÁ NO AR em 16/11 (anúncio em rascunho, conjunto pausado). Entra a
  partir de ~18/11 (após o post da Mariana, impulsionado para leads). Público: Flórida, inglês,
  diretores+, 201-5.000 funcionários, serviços financeiros e seguros. Pode seguir em 20/dia até
  31/12 se o custo por lead do e-book ficar abaixo de R$ 150 em 14/12.
- Conjuntos de MARCA da Liferay antiga (IA no Canal do Corretor 775502383; Darkpost Case CNP
  810057963): ENCERRADOS em 15/11 (ver bloco LIFERAY). Não têm mais verba diária ativa.

ESTRUTURA DE CAMPANHAS (campaignGroup) no Campaign Manager:
- "Campanhas Plano de Mídia - Vertigo": Materiais Ricos (Financeiras), VeeCode, Artigos - Bruno.
- "Liferay - Junho>Novembro26" (1152903403, Conhecimento da marca): ENCERRADA em 15/11.
- "Liferay - Geração de Leads - Nov26" (1255513733): Liferay - Leads - Canal do Corretor + Case CNP.
- "EUA - E-book AI Gateway (EN) - Leads" (1255465693): EUA - FSI Florida - E-book AI Gateway (EN).
O rateio 50/50 vale para TUDO das campanhas Liferay (gasto entra pela metade no painel).

TETOS MENSAIS DE REFERÊNCIA (já com Liferay a 50% e o conjunto em inglês):
nov/2026 = R$ 4.600; dez/2026 = R$ 2.750.

MUDANÇAS REGISTRADAS (fatos confirmados pelo Vitor em 16/11; o resto é planejado):
- 12/11 (feito): 1ª redução de verba (Financeiras 56, VeeCode 32, Artigos - Bruno 28), só o
  diário, sem pausar nem mexer em segmentação/criativo. Criada a campanha nova de leads da
  Liferay (R$ 28/dia, trava R$ 530, até 30/11).
- 13/11 (feito): 2 anúncios da Liferay leads (Case CNP e Canal do Corretor 4x5) ativados e
  entregando, sem reprovação (dia exato de início a confirmar no gráfico diário).
- 15/11 (feito): a campanha de MARCA antiga da Liferay encerrou (término configurado; gasto
  final R$ 6.330,81). Sem reativação.
- 16/11 (feito): criado o 3º anúncio da Liferay leads ("IA no Canal do Corretor", criativo
  azul), sob avaliação do LinkedIn.
- 18/11 (planejado): post da Mariana publicado; o conjunto em inglês (e-book EUA) é impulsionado
  para leads a partir daí.
- 19/11 (planejado, só se a Júlia confirmar): 2ª redução (Financeiras 45, VeeCode 26, Artigos 22).
- 23/11 (planejado): VAIM/material novo entra.
- 30/11 (planejado): a Liferay encerra — gerar o FECHAMENTO (gasto total e leads por criativo)
  para os prints de comprovação.
- 1/12 e 19/12 (planejado): reduções (1/12 Financeiras 30, VeeCode 20, Artigos 20; 19/12
  Financeiras 20). O inglês pode encerrar em 18/12 ou seguir em 20/dia até 31/12 (ver acima).
"""


def liferay_projecao(fim: date = LIFERAY_FIM) -> dict:
    """Projeção do gasto final (bruto) da Liferay vs o teto de R$ 7.200.

    Determinística: a campanha de marca antiga encerrou em 15/11 com valor FIXO
    (LIFERAY_ANTIGA_FINAL) e a nova tem trava total de R$ 530 (12/11-30/11). O pior
    caso = antiga final + trava integral da nova. O `fim` é mantido por compatibilidade."""
    projetado = LIFERAY_ANTIGA_FINAL + LIFERAY_NOVA_TRAVA   # 6860.81 (pior caso)
    pct = projetado / LIFERAY_TETO_TOTAL if LIFERAY_TETO_TOTAL else None
    return {
        "teto": LIFERAY_TETO_TOTAL,
        "gasto_base": LIFERAY_GASTO_BASE,
        "projetado_fim": round(projetado, 2),
        "pct_projetado": pct,
        "estoura": projetado > LIFERAY_TETO_TOTAL,
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
