"""Histórico compartilhado do chat do painel, PERSISTIDO na planilha.

Sobrevive a reinícios e deploys (ao contrário de memória). Guarda as consultas
do time numa aba própria; o painel mostra as N mais recentes e permite deletar
uma consulta. Leituras têm cache curto para não bater na planilha a cada acesso.
"""
import time
import uuid

TAB = "Histórico Chat"
HEADER = ["ID", "Data", "Usuário", "Pergunta", "Resposta"]
VISIBLE = 20            # quantas consultas o painel mostra
_TTL = 60               # cache de leitura (segundos)
_cache: dict = {"ts": 0, "list": None}


def _ws():
    from .sheets_client import open_sheet
    sh = open_sheet()
    try:
        return sh.worksheet(TAB)
    except Exception:
        ws = sh.add_worksheet(title=TAB, rows=100, cols=len(HEADER))
        ws.append_row(HEADER, value_input_option="RAW")
        return ws


def add(question: str, answer: str, by: str, ts_label: str) -> str:
    """Registra uma consulta e devolve o id gerado."""
    rid = uuid.uuid4().hex[:12]
    _ws().append_row([rid, ts_label, by, question, answer], value_input_option="RAW")
    _cache["list"] = None
    return rid


def last(n: int = VISIBLE, force: bool = False) -> list[dict]:
    """As N consultas mais recentes (mais antiga -> mais nova)."""
    if not force and _cache["list"] is not None and (time.time() - _cache["ts"] < _TTL):
        return _cache["list"]
    ws = _ws()
    total = len(ws.col_values(1))          # inclui o cabeçalho
    if total <= 1:
        _cache.update(ts=time.time(), list=[])
        return []
    start = max(2, total - n + 1)
    out = []
    for r in ws.get(f"A{start}:E{total}"):
        r = (list(r) + ["", "", "", "", ""])[:5]
        if not r[0]:
            continue
        out.append({"id": r[0], "ts": r[1], "by": r[2], "q": r[3], "a": r[4]})
    _cache.update(ts=time.time(), list=out)
    return out


def delete(rid: str) -> bool:
    """Remove uma consulta pelo id."""
    ws = _ws()
    try:
        cell = ws.find(str(rid), in_column=1)
    except Exception:
        cell = None
    if cell:
        ws.delete_rows(cell.row)
    _cache["list"] = None
    return True
