"""Persistência keyed dos textos do agente (card do painel e relatório formal).

Regra central (single source of truth): cada texto é gerado UMA vez, congelado e
guardado (analysis_store). Todos que leem, painel, PDF, e-mail ou qualquer pessoa,
recebem o MESMO conteúdo do período. A chave define a cadência de renovação:
  - mês corrente: chave por DIA  -> renova 1x/dia
  - mês passado:  chave por MÊS  -> imutável (o dado já é final)

Este módulo é usado tanto pela API (leitura sob demanda) quanto pelos jobs
agendados (pré-geração no daily_collect e fechamento no monthly_report), então
não existe divergência entre quem gera e quem lê.
"""
import calendar
import re
from datetime import date, datetime, timedelta, timezone

from . import analysis_store, dashboard_data
from .report_builder import collect_campaign_data

BRT = timezone(timedelta(hours=-3))


def current_month() -> str:
    return date.today().strftime("%Y-%m")


def period_for(month: str | None):
    """Intervalo do mês. Mês corrente = o mês de HOJE (dia 1 até ontem; no 1º dia,
    o range é o próprio dia 1). Mês passado vai até o fim do mês."""
    today = date.today()
    if not month:
        start = today.replace(day=1)              # mês corrente (o de hoje)
        return start, max(start, today - timedelta(days=1))
    y, m = (int(x) for x in month.split("-"))
    start = date(y, m, 1)
    last = date(y, m, calendar.monthrange(y, m)[1])
    end = min(last, today - timedelta(days=1))
    return start, max(start, end)


def _now_stamp() -> str:
    return datetime.now(BRT).strftime("%d/%m %H:%M")


def _get_stored(key: str, cache: dict | None):
    """Procura na memória e depois na planilha (fonte durável)."""
    if cache is not None and key in cache:
        return cache[key]
    try:
        stored = analysis_store.get(key)
    except Exception as exc:
        print(f"  aviso: não li ({key}): {exc}")
        return None
    if stored and cache is not None:
        cache[key] = stored
    return stored


def _save(key: str, payload: dict, cache: dict | None) -> None:
    try:
        analysis_store.save(key, payload.get("gerada_em", ""), payload)
    except Exception as exc:
        print(f"  aviso: não persisti ({key}): {exc}")
    if cache is not None:
        cache[key] = payload


# Versão da chave do card. Bump invalida os snapshots antigos (ex.: os gerados
# antes do rateio 50/50 e do modo retrospectivo de mês fechado), forçando 1
# regeneração com a lógica atual. Não afeta o relatório (chaves RPT-...).
_CARD_VER = "4"
_RPT_VER = "2"     # versão da chave do relatório do mês corrente (bump = regenera hoje)


def load_or_build_card(month: str | None = None, data: list | None = None,
                       force: bool = False, cache: dict | None = None) -> dict:
    """Card de análise do painel (resumo + ações). Estável por dia no mês corrente,
    fixo nos meses passados. Mês passado usa tom retrospectivo (fechado=True)."""
    mk = month or current_month()
    fechado = mk != current_month()
    base = datetime.now(BRT).date().isoformat() if not fechado else "M" + mk
    key = f"A{_CARD_VER}-{base}"
    if not force:
        got = _get_stored(key, cache)
        if got:
            return got
    start, end = period_for(month)
    inicio_mes = (not fechado) and end.day <= 7      # primeira semana do mês corrente
    if data is None:
        data = collect_campaign_data(start, end)
    analise = dashboard_data.build_analysis_ia(start, end, ref_date=end, data=data,
                                               fechado=fechado, inicio_mes=inicio_mes)
    analise["gerada_em"] = _now_stamp()
    _save(key, analise, cache)
    return analise


def load_or_build_report(month: str | None = None, data: list | None = None,
                         force: bool = False, cache: dict | None = None) -> dict:
    """Relatório formal (7 seções). Mês corrente = parcial (renova 1x/dia); mês
    passado = fechamento (imutável). Congela sob a chave RPT-... na planilha."""
    mk = month or current_month()
    fechado = mk != current_month()
    # Mês corrente versionado (_RPT_VER): bump invalida o relatório de hoje quando a
    # lógica muda (ex.: correção do período). Mês passado = fixo (fechamento imutável).
    key = ("RPT-M" + mk) if fechado else (f"RPT{_RPT_VER}-" + datetime.now(BRT).date().isoformat())
    if not force:
        got = _get_stored(key, cache)
        if got:
            return got
    start, end = period_for(month)
    inicio_mes = (not fechado) and end.day <= 7      # primeira semana do mês corrente
    if data is None:
        data = collect_campaign_data(start, end)
    rel = dashboard_data.build_report_analysis(start, end, ref_date=end, data=data,
                                               fechado=fechado, inicio_mes=inicio_mes)
    rel["gerada_em"] = _now_stamp()
    rel["modo"] = "fechamento" if fechado else "parcial"
    rel["mes"] = mk
    _save(key, rel, cache)
    return rel


def _sem_md(t: str) -> str:
    """Tira o markdown de negrito para o corpo de e-mail em texto plano."""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", t or "").replace("**", "").strip()


def to_text(rel: dict) -> str:
    """Renderiza o relatório robusto (7 seções) em texto plano para o e-mail."""
    fechamento = rel.get("modo") == "fechamento"
    L: list[str] = ["RELATÓRIO DE FECHAMENTO (MÊS ENCERRADO)" if fechamento
                    else "RELATÓRIO PARCIAL (MÊS EM CURSO)"]
    if rel.get("contexto"):
        L += ["", _sem_md(rel["contexto"])]

    def sec(titulo: str, texto: str) -> None:
        if texto:
            L.extend(["", titulo, _sem_md(texto)])

    sec("RESUMO EXECUTIVO", rel.get("resumo_executivo", ""))
    sec("ORÇAMENTO E RITMO", rel.get("orcamento_ritmo", ""))

    grupos = rel.get("por_grupo") or []
    if grupos:
        L += ["", "DESEMPENHO POR GRUPO DE ANÚNCIOS"]
        for g in grupos:
            L.append(f"- {g.get('nome', '')}: {_sem_md(g.get('texto', ''))}")

    sec("APRENDIZADOS E OPORTUNIDADES" if fechamento else "RISCOS E OPORTUNIDADES",
        rel.get("riscos_oportunidades", ""))

    recs = rel.get("recomendacoes") or []
    if recs:
        L += ["", "RECOMENDAÇÕES PRIORITÁRIAS"]
        L += [f"{i}. {_sem_md(a)}" for i, a in enumerate(recs, 1)]

    passos = rel.get("proximos_passos") or []
    if passos:
        L += ["", "RECOMENDAÇÕES PARA O PRÓXIMO CICLO" if fechamento else "PRÓXIMOS PASSOS"]
        L += [f"{i}. {_sem_md(a)}" for i, a in enumerate(passos, 1)]

    return "\n".join(L)
