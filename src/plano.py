"""Plano de mídia paga da Vertigo — Q4 2026 (fonte única).

Definido por Júlia e Vitor. O Vitor executa no Campaign Manager; cada mudança
precisa ser conhecida pelo agente para os relatórios considerarem.

A FONTE dos dados do plano é uma PLANILHA editável (PLANO_SHEET_ID), lida pelo
`plano_sheet`. Assim Júlia/Vitor mudam verba, status, datas e observações direto
na planilha, sem mexer no código nem acionar ninguém — o agente lê na próxima
coleta. Se a planilha não estiver configurada ou acessível, o agente usa o
DADOS_PADRAO abaixo (o plano de hoje), então nada quebra enquanto a planilha não
existe.

Partes FIXAS (regras de como avaliar) ficam no código, abaixo. Partes que MUDAM
(verbas, status, datas, tetos, observações) vêm da planilha.
"""
from datetime import date
from time import time

# ----------------------------------------------------------------------------
# DADOS DO PLANO (fallback). Mesma forma que o `plano_sheet` devolve ao ler a
# planilha. Situação em 16/11/2026 (relatório do Vitor).
# ----------------------------------------------------------------------------
DADOS_PADRAO: dict = {
    # Um item por CONJUNTO de anúncios (o que a API chama "campaign"=sponsoredCampaign).
    # tipo: "leads" | "tráfego" | "marca".  status: "ativo" | "pausado" | "encerrado".
    "conjuntos": [
        {"codigo": "276543063", "nome": "Materiais Ricos - Segmentos (Financeiras)",
         "tipo": "leads", "status": "ativo", "verba_dia": 56.0, "inicio": "", "fim": "",
         "obs": "Reduções planejadas: 45 em 19/11 (só se a Júlia confirmar), 30 em 1/12, 20 em 19/12."},
        {"codigo": "296725553", "nome": "VeeCode - Materiais Ricos",
         "tipo": "leads", "status": "ativo", "verba_dia": 32.0, "inicio": "", "fim": "",
         "obs": "Reduções: 26 em 19/11 (se confirmado), 20 em 1/12."},
        {"codigo": "377232663", "nome": "Artigos - Bruno",
         "tipo": "tráfego", "status": "ativo", "verba_dia": 28.0, "inicio": "", "fim": "",
         "obs": "Tráfego/engajamento (avaliar por CPC/CTR). Reduções: 22 em 19/11 (se confirmado), 20 em 1/12."},
        {"codigo": "902105083", "nome": "Liferay - Leads - Canal do Corretor + Case CNP",
         "tipo": "leads", "status": "ativo", "verba_dia": 28.0, "inicio": "12/11", "fim": "30/11",
         "obs": "Campanha NOVA de leads da Liferay (trava R$ 530). 3 anúncios dentro do conjunto: "
                "Case CNP, Canal do Corretor 4x5 e IA no Canal azul (criado 16/11, sob avaliação)."},
        {"codigo": "902243203", "nome": "EUA - FSI Florida - E-book AI Gateway (EN)",
         "tipo": "leads", "status": "pausado", "verba_dia": 25.0, "inicio": "", "fim": "",
         "obs": "Inglês. Em rascunho/pausado em 16/11 — AINDA NÃO no ar. Entra ~18/11 (após post da "
                "Mariana). Pode seguir 20/dia até 31/12 se o CPL do e-book ficar < R$ 150 em 14/12."},
        {"codigo": "775502383", "nome": "Impulsionamento - IA no Canal do Corretor",
         "tipo": "marca", "status": "encerrado", "verba_dia": 0.0, "inicio": "", "fim": "15/11",
         "obs": "Marca antiga da Liferay (alcance). ENCERRADA em 15/11."},
        {"codigo": "810057963", "nome": "Darkpost - Case CNP Seguradora",
         "tipo": "marca", "status": "encerrado", "verba_dia": 0.0, "inicio": "", "fim": "15/11",
         "obs": "Marca antiga da Liferay (alcance). ENCERRADA em 15/11."},
    ],
    # Patrocínio Liferay (50/50). Valores brutos. base_data/fim são date.
    "liferay": {
        "teto": 7200.00,
        "antiga_final": 6330.81,   # campanha de marca encerrada em 15/11 (valor final fixo)
        "nova_gasto": 114.98,      # gasto da campanha nova de leads até a data base
        "nova_trava": 530.00,      # trava total da campanha nova (12/11-30/11)
        "base_data": date(2026, 11, 16),
        "fim": date(2026, 11, 30),
    },
    # Tetos mensais da conta (já com Liferay a 50% + conjunto em inglês).
    "tetos": {"2026-11": 4600.00, "2026-12": 2750.00},
    # Log livre de mudanças / cronograma (texto; o agente usa como contexto).
    "observacoes": [
        {"data": "12/11", "texto": "1ª redução de verba (Financeiras 56, VeeCode 32, Artigos 28), só o "
                                   "diário, sem pausar. Criada a campanha nova de leads da Liferay."},
        {"data": "13/11", "texto": "2 anúncios da Liferay leads (Case CNP e Canal do Corretor 4x5) "
                                   "ativados e entregando."},
        {"data": "15/11", "texto": "Campanha de marca antiga da Liferay encerrou (gasto final R$ 6.330,81)."},
        {"data": "16/11", "texto": "3º anúncio da Liferay leads (IA no Canal azul) criado, sob avaliação."},
        {"data": "plano", "texto": "18/11 post da Mariana + inglês entra; 19/11 2ª redução (se a Júlia "
                                   "confirmar); 23/11 VAIM/material novo; 30/11 Liferay encerra "
                                   "(gerar fechamento p/ prints); 1/12 e 19/12 reduções."},
    ],
}

# ----------------------------------------------------------------------------
# Parte FIXA do contexto (regras de COMO avaliar). Não muda com a planilha.
# ----------------------------------------------------------------------------
_REGRAS = """== PLANO DE MÍDIA PAGA — Q4 2026 (AUTORIDADE MÁXIMA, use SEMPRE) ==
Plano definido por Júlia e Vitor para usar a verba até o fim de 2026. O Vitor executa no
Campaign Manager; os valores e o estado de cada conjunto vêm da planilha do plano (abaixo).
Estas regras e valores TÊM PRIORIDADE sobre qualquer estrutura/teto genérico citado antes.

REGRAS GERAIS (seguir sempre):
- NUNCA recomende PAUSAR nenhum conjunto de anúncios até 31/12/2026 — pausar reinicia o
  aprendizado. A ÚNICA alavanca de corte é REDUZIR a verba aos poucos (cerca de 20% por vez),
  até o PISO de R$ 20/dia por conjunto. Não sugira pausa em hipótese alguma.
- O orçamento diário é por CONJUNTO. Trate e reporte cada conjunto SEPARADO, num relatório único.
- Use os valores de orçamento DESTE plano. IGNORE tetos antigos (ex.: R$ 1.500) e não os cite.
- Porte desejado dos leads: empresas com 200+ funcionários.
- Reporte leads TOTAIS e o CPL de CADA conjunto. NÃO classifique leads por nível (A/B/C/D) nem
  comente cargo do lead — está desligado por ora.
- Conjuntos de tipo "marca" (alcance): avalie por alcance/impressões/engajamento (CPC/CTR),
  NUNCA por leads/CPL, e não os compare com os de leads.
- APRENDIZADO: conjuntos recém-criados ou recém-ativados ficam ~7 dias calibrando. NÃO trate o
  resultado deles como definitivo na 1ª semana — contextualize."""


def _fmt_brl(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(v)


def _fmt_data(d) -> str:
    return d.strftime("%d/%m") if isinstance(d, date) else str(d or "")


def liferay_projecao(dados: dict | None = None) -> dict:
    """Projeção do gasto final (bruto) da Liferay vs o teto.

    Determinística: a campanha de marca antiga encerrou com valor FIXO (antiga_final)
    e a nova tem trava total (nova_trava). Pior caso = antiga_final + trava integral."""
    lf = (dados or carregar())["liferay"]
    base = round(lf["antiga_final"] + lf["nova_gasto"], 2)
    projetado = round(lf["antiga_final"] + lf["nova_trava"], 2)
    teto = lf["teto"]
    return {
        "teto": teto,
        "gasto_base": base,
        "projetado_fim": projetado,
        "pct_projetado": (projetado / teto) if teto else None,
        "estoura": projetado > teto,
        "fim": lf["fim"].isoformat() if isinstance(lf["fim"], date) else str(lf["fim"]),
    }


def liferay_resumo(ref: date | None = None, dados: dict | None = None) -> dict | None:
    """Dados do banner do patrocínio Liferay no painel. Relevante só no mês de
    encerramento da campanha (o mês de `fim`). Fora disso retorna None."""
    dados = dados or carregar()
    lf = dados["liferay"]
    fim = lf["fim"] if isinstance(lf["fim"], date) else date.fromisoformat(str(lf["fim"]))
    ref = ref or date.today()
    if not (ref.year == fim.year and ref.month == fim.month):
        return None
    proj = liferay_projecao(dados)
    base = proj["gasto_base"]
    teto = lf["teto"]
    return {
        "teto": teto,
        "gasto_base": base,
        "base_data": _fmt_data(lf["base_data"]),
        "restante": round(teto - base, 2),
        "projetado_fim": proj["projetado_fim"],
        "pct_base": (base / teto) if teto else None,
        "pct_projetado": proj["pct_projetado"],
        "fim": _fmt_data(fim),
        "estoura": proj["estoura"],
    }


def tetos(dados: dict | None = None) -> dict:
    """Tetos mensais {AAAA-MM: valor} do plano."""
    return dict((dados or carregar()).get("tetos", {}))


def montar_contexto(dados: dict) -> str:
    """Renderiza o bloco de CONTEXTO (texto autoritativo) a partir dos dados do plano."""
    linhas = [_REGRAS, "", "CONJUNTOS DE ANÚNCIOS (estado atual — nomes/códigos exatos do Campaign Manager):"]
    for c in dados["conjuntos"]:
        vig = ""
        if c.get("inicio") or c.get("fim"):
            vig = f" [vigência {c.get('inicio') or '...'}–{c.get('fim') or '...'}]"
        verba = f"R$ {c['verba_dia']:.0f}/dia" if c.get("verba_dia") else "sem verba ativa"
        obs = f" — {c['obs']}" if c.get("obs") else ""
        linhas.append(
            f"- {c['nome']} (cód. {c['codigo']} — tipo: {c['tipo']}; status: {c['status']}; {verba}){vig}{obs}"
        )

    lf = dados["liferay"]
    proj = liferay_projecao(dados)
    linhas += [
        "",
        "LIFERAY (patrocínio 50/50 — a Vertigo paga tudo e a Liferay reembolsa 50%):",
        f"- Teto TOTAL do patrocínio: {_fmt_brl(lf['teto'])} (R$ 3.600 de cada lado), somando TUDO da Liferay.",
        f"- A campanha de MARCA antiga encerrou com gasto final de {_fmt_brl(lf['antiga_final'])} (fixo, sem reativação).",
        f"- A campanha NOVA de leads tem trava total de {_fmt_brl(lf['nova_trava'])}; gasto até "
        f"{_fmt_data(lf['base_data'])} = {_fmt_brl(lf['nova_gasto'])}.",
        f"- Gasto Liferay acumulado (bruto) até {_fmt_data(lf['base_data'])}: {_fmt_brl(proj['gasto_base'])}. "
        f"Projeção até {_fmt_data(lf['fim'])}: no MÁXIMO {_fmt_brl(proj['projetado_fim'])} "
        f"({(proj['pct_projetado'] or 0) * 100:.0f}% do teto; {'ESTOURA' if proj['estoura'] else 'não estoura'}). "
        f"Só alerte se o combinado projetar passar do teto.",
    ]

    if dados.get("tetos"):
        tet = "; ".join(f"{m} = {_fmt_brl(v)}" for m, v in sorted(dados["tetos"].items()))
        linhas += ["", f"TETOS MENSAIS DE REFERÊNCIA (já com Liferay a 50% + inglês): {tet}."]

    if dados.get("observacoes"):
        linhas += ["", "OBSERVAÇÕES / MUDANÇAS (considerar conforme a data do período do relatório):"]
        for o in dados["observacoes"]:
            d = o.get("data")
            prefixo = f"{d}: " if d and d not in ("plano", "—", "") else ""
            linhas.append(f"- {prefixo}{o.get('texto', '')}")

    return "\n\n" + "\n".join(linhas) + "\n"


# ----------------------------------------------------------------------------
# Carregamento com cache (planilha -> fallback). Cache por processo com TTL curto,
# para o painel/chat não baterem na planilha a cada requisição.
# ----------------------------------------------------------------------------
_CACHE: dict = {"dados": None, "ts": 0.0, "fonte": "padrão"}
_TTL = 600  # segundos


def carregar(force: bool = False) -> dict:
    """Dados do plano: da planilha (PLANO_SHEET_ID) se configurada e legível,
    senão o DADOS_PADRAO (plano de hoje). Resultado cacheado por `_TTL`s."""
    agora = time()
    if not force and _CACHE["dados"] is not None and (agora - _CACHE["ts"]) < _TTL:
        return _CACHE["dados"]
    dados, fonte = DADOS_PADRAO, "padrão"
    try:
        from . import config
        if getattr(config, "PLANO_SHEET_ID", ""):
            from . import plano_sheet
            lido = plano_sheet.ler(config.PLANO_SHEET_ID)
            if lido and lido.get("conjuntos"):
                dados, fonte = lido, "planilha"
    except Exception as exc:  # qualquer falha -> fallback seguro
        print(f"  aviso: não li o plano da planilha, usando o padrão do código: {exc}")
    _CACHE.update(dados=dados, ts=agora, fonte=fonte)
    return dados


def fonte() -> str:
    """'planilha' ou 'padrão' — de onde veio o plano carregado por último."""
    return _CACHE.get("fonte", "padrão")


def contexto() -> str:
    """Bloco de CONTEXTO (texto autoritativo) com os dados atuais do plano."""
    return montar_contexto(carregar())
