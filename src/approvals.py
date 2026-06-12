"""Registro e controle de aprovacoes de acoes recomendadas.

As recomendacoes pendentes ficam na aba "Recomendações" da planilha,
que funciona como fila e log de auditoria ao mesmo tempo.
Status possiveis: PENDENTE -> APROVADA/REJEITADA -> EXECUTADA.
"""
from datetime import datetime, timezone

from . import linkedin_client, sheets_client
from .recommendations import Recommendation

TAB = "Recomendações"

# Indices das colunas na aba (A=0): Data, Campanha, Acao, Motivo, Status, Aprovado por, Executado em
COL_STATUS = 4
COL_APPROVER = 5
COL_EXECUTED = 6


def log_recommendation(rec: Recommendation) -> None:
    """Grava uma recomendacao nova com status PENDENTE."""
    sheets_client.append_rows(TAB, [[
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        rec.campaign_name,
        f"{rec.action}: {rec.current_value} → {rec.proposed_value} [{rec.campaign_id}]",
        rec.reason,
        "PENDENTE",
        "",
        "",
    ]])


def list_pending() -> list[dict]:
    """Retorna recomendacoes pendentes com o numero da linha na planilha."""
    ws = sheets_client.open_sheet().worksheet(TAB)
    rows = ws.get_all_values()
    pending = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) > COL_STATUS and row[COL_STATUS] == "PENDENTE":
            pending.append({
                "row": i,
                "date": row[0],
                "campaign": row[1],
                "action": row[2],
                "reason": row[3],
            })
    return pending


def _parse_action(action_text: str) -> tuple[str, str, str]:
    """Extrai (acao, valor_proposto, campaign_id) do texto da coluna Acao."""
    action = action_text.split(":", 1)[0].strip()
    campaign_id = action_text.rsplit("[", 1)[1].rstrip("]") if "[" in action_text else ""
    proposed = action_text.split("→", 1)[1].rsplit("[", 1)[0].strip() if "→" in action_text else ""
    return action, proposed, campaign_id


def approve(row: int, approver: str) -> str:
    """Aprova e executa a recomendacao da linha indicada. Retorna descricao do resultado."""
    ws = sheets_client.open_sheet().worksheet(TAB)
    values = ws.row_values(row)
    if len(values) <= COL_STATUS or values[COL_STATUS] != "PENDENTE":
        return "Recomendação não está pendente."

    action, proposed, campaign_id = _parse_action(values[2])

    if action == "PAUSE":
        linkedin_client.pause_campaign(campaign_id)
    elif action == "REACTIVATE":
        linkedin_client.activate_campaign(campaign_id)
    elif action in ("REDUCE_BUDGET", "INCREASE_BUDGET"):
        amount = float(proposed.replace("R$", "").replace("/dia", "").replace(",", ".").strip())
        linkedin_client.set_daily_budget(campaign_id, amount)
    elif action == "ADJUST_BID":
        return "Ajuste de lance requer revisão manual — marcada como aprovada sem execução automática."
    else:
        return f"Ação desconhecida: {action}"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    ws.update_cell(row, COL_STATUS + 1, "EXECUTADA")
    ws.update_cell(row, COL_APPROVER + 1, approver)
    ws.update_cell(row, COL_EXECUTED + 1, now)
    return f"Ação {action} executada na campanha {values[1]}."


def reject(row: int, approver: str) -> str:
    ws = sheets_client.open_sheet().worksheet(TAB)
    values = ws.row_values(row)
    if len(values) <= COL_STATUS or values[COL_STATUS] != "PENDENTE":
        return "Recomendação não está pendente."
    ws.update_cell(row, COL_STATUS + 1, "REJEITADA")
    ws.update_cell(row, COL_APPROVER + 1, approver)
    return f"Recomendação rejeitada para a campanha {values[1]}."
