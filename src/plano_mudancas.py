"""Detecta mudanças no plano (planilha) entre execuções e avisa por e-mail.

Rodado uma vez por dia (coleta diária): compara o plano lido hoje com o último
guardado na aba oculta _estado. Se mudou algo, manda UM e-mail resumindo as
mudanças para PLANO_CHANGE_RECIPIENTS (Júlia/Vitor/Leandro). Como só roda uma vez
por dia, nunca vira spam — no máximo um aviso por dia, e só quando houve mudança.
"""
import json
from datetime import date

from . import config, mailer, plano, plano_sheet


def _snapshot(dados: dict) -> dict:
    """Versão normalizada e serializável do plano, para comparar entre dias."""
    lf = dict(dados.get("liferay", {}))
    for k in ("base_data", "fim"):
        if isinstance(lf.get(k), date):
            lf[k] = lf[k].isoformat()
    conj = {}
    for c in dados.get("conjuntos", []):
        conj[str(c.get("codigo") or c.get("nome"))] = {
            "nome": c.get("nome", ""), "tipo": c.get("tipo", ""),
            "status": c.get("status", ""), "verba_dia": c.get("verba_dia", 0),
            "inicio": c.get("inicio", ""), "fim": c.get("fim", ""), "obs": c.get("obs", ""),
        }
    obs = [f"{o.get('data', '')}|{o.get('texto', '')}" for o in dados.get("observacoes", [])]
    return {"conjuntos": conj, "liferay": lf, "tetos": dict(dados.get("tetos", {})), "observacoes": obs}


def _brl(v) -> str:
    try:
        return f"R$ {float(v):.0f}"
    except (TypeError, ValueError):
        return str(v)


_ROTULO = {"verba_dia": "verba/dia", "status": "status", "tipo": "tipo",
           "nome": "nome", "inicio": "início", "fim": "fim", "obs": "observação"}


def diff(antigo: dict, novo: dict) -> list[str]:
    """Lista de mudanças em português entre dois snapshots."""
    msgs: list[str] = []
    ca, cn = antigo.get("conjuntos", {}), novo.get("conjuntos", {})
    for cod, c in cn.items():
        if cod not in ca:
            msgs.append(f"➕ Novo conjunto: {c.get('nome', cod)} ({c.get('status')}, {_brl(c.get('verba_dia'))}/dia).")
            continue
        a = ca[cod]
        for campo in ("nome", "tipo", "status", "verba_dia", "inicio", "fim", "obs"):
            if str(a.get(campo, "")) != str(c.get(campo, "")):
                rot = _ROTULO.get(campo, campo)
                nome = c.get("nome", cod)
                if campo == "verba_dia":
                    msgs.append(f"• {nome}: {rot} {_brl(a.get(campo))} → {_brl(c.get(campo))}.")
                elif campo == "obs":
                    msgs.append(f"• {nome}: observação atualizada.")
                else:
                    msgs.append(f"• {nome}: {rot} \"{a.get(campo)}\" → \"{c.get(campo)}\".")
    for cod, a in ca.items():
        if cod not in cn:
            msgs.append(f"➖ Conjunto removido da planilha: {a.get('nome', cod)}.")

    # Liferay / tetos
    la, ln = antigo.get("liferay", {}), novo.get("liferay", {})
    for campo in ("teto", "antiga_final", "nova_gasto", "nova_trava", "base_data", "fim"):
        if str(la.get(campo, "")) != str(ln.get(campo, "")):
            msgs.append(f"• Liferay ({campo}): \"{la.get(campo)}\" → \"{ln.get(campo)}\".")
    ta, tn = antigo.get("tetos", {}), novo.get("tetos", {})
    for mes in sorted(set(ta) | set(tn)):
        if str(ta.get(mes, "")) != str(tn.get(mes, "")):
            msgs.append(f"• Teto {mes}: {_brl(ta.get(mes)) if mes in ta else '—'} → {_brl(tn.get(mes)) if mes in tn else '—'}.")

    novas_obs = [o for o in novo.get("observacoes", []) if o not in antigo.get("observacoes", [])]
    for o in novas_obs:
        data, _, texto = o.partition("|")
        msgs.append(f"📝 Nova observação ({data}): {texto}" if data else f"📝 Nova observação: {texto}")
    return msgs


def _corpo(mudancas: list[str]) -> str:
    hoje = date.today().strftime("%d/%m/%Y")
    linhas = [
        f"O agente leu a planilha do plano de mídia hoje ({hoje}) e detectou mudanças. "
        "Elas já estão valendo nas análises do agente a partir desta atualização.",
        "",
        "O que mudou:",
        *mudancas,
        "",
        "— Aviso automático do agente de mídia paga. Para mudar o plano, edite a planilha "
        "(o agente aplica na próxima coleta diária).",
    ]
    return "\n".join(linhas)


def checar_e_avisar() -> None:
    """Lê o plano da planilha, compara com o último estado e, se mudou, manda e-mail.
    Silencioso e seguro: sem planilha configurada ou em qualquer erro, não faz nada."""
    sid = getattr(config, "PLANO_SHEET_ID", "")
    if not sid:
        return
    try:
        dados = plano.carregar(force=True)
        if plano.fonte() != "planilha":
            print("  aviso: plano não veio da planilha (fallback) — sem aviso de mudança.")
            return
        novo = _snapshot(dados)
        novo_json = json.dumps(novo, ensure_ascii=False, sort_keys=True)
        antigo_txt = plano_sheet.ler_estado(sid)
        if not antigo_txt:
            plano_sheet.gravar_estado(sid, novo_json)   # primeira vez: só registra a linha de base
            print("Plano: linha de base registrada (sem aviso na primeira leitura).")
            return
        if antigo_txt == novo_json:
            print("Plano: sem mudanças desde a última leitura.")
            return
        mudancas = diff(json.loads(antigo_txt), novo)
        if not mudancas:
            plano_sheet.gravar_estado(sid, novo_json)
            return
        destinatarios = config.PLANO_CHANGE_RECIPIENTS or config.REPORT_RECIPIENTS
        if destinatarios:
            mailer.send_email("📋 Plano de mídia atualizado (via planilha)", _corpo(mudancas), destinatarios)
            print(f"Plano: {len(mudancas)} mudança(s) — e-mail enviado para {', '.join(destinatarios)}.")
        else:
            print(f"Plano: {len(mudancas)} mudança(s), mas sem destinatários configurados (PLANO_CHANGE_RECIPIENTS).")
        plano_sheet.gravar_estado(sid, novo_json)
    except Exception as exc:
        print(f"  aviso: falha ao checar mudanças do plano: {exc}")
