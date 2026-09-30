"""Histórico do chat do painel, PERSISTIDO na planilha e agrupado por CONVERSA.

Cada linha é uma troca (pergunta+resposta) e carrega o id da conversa. O painel
mostra UMA entrada por conversa (como uma sessão de chat): abre uma nova só
quando é uma conversa nova, não a cada mensagem. Compartilhado com o time e
resistente a reinícios/deploys. Leitura com cache curto.
"""
import time

TAB = "Histórico Chat"
HEADER = ["Conversa", "Data", "Usuário", "Pergunta", "Resposta"]
VISIBLE = 20            # nº de CONVERSAS mostradas
_WINDOW = 400           # nº de linhas lidas da planilha (o suficiente p/ as recentes)
_TTL = 60               # cache de leitura (segundos)
_cache: dict = {"ts": 0, "list": None}


def _ws():
    from .sheets_client import open_sheet
    sh = open_sheet()
    try:
        return sh.worksheet(TAB)
    except Exception:
        ws = sh.add_worksheet(title=TAB, rows=200, cols=len(HEADER))
        ws.append_row(HEADER, value_input_option="RAW")
        return ws


def add(conv_id: str, question: str, answer: str, by: str, ts_label: str) -> None:
    """Registra uma troca dentro de uma conversa (texto puro, sem markdown)."""
    from .analyst import _strip_md          # tira ** / travessão para a planilha ficar limpa
    _ws().append_row([conv_id, ts_label, by, _strip_md(question), _strip_md(answer)],
                     value_input_option="RAW")
    _cache["list"] = None


def last(n: int = VISIBLE, force: bool = False) -> list[dict]:
    """As `n` conversas mais recentes (mais recente primeiro). Cada conversa:
    {id, ts, by, title, count, msgs:[{q,a,ts}, ...]}."""
    if not force and _cache["list"] is not None and (time.time() - _cache["ts"] < _TTL):
        return _cache["list"]
    ws = _ws()
    total = len(ws.col_values(1))
    if total <= 1:
        _cache.update(ts=time.time(), list=[])
        return []
    start = max(2, total - _WINDOW + 1)
    convs: dict[str, dict] = {}
    order: list[str] = []
    for r in ws.get(f"A{start}:E{total}"):
        r = (list(r) + ["", "", "", "", ""])[:5]
        cid, ts, by, q, a = r
        if not cid:
            continue
        if cid not in convs:
            convs[cid] = {"id": cid, "ts": ts, "by": by, "title": q, "count": 0, "msgs": []}
            order.append(cid)
        convs[cid]["msgs"].append({"q": q, "a": a, "ts": ts})
        convs[cid]["count"] += 1
        convs[cid]["ts"] = ts          # última atividade da conversa
    # mais recente primeiro (pela ordem em que aparecem, a última é a mais nova)
    ordered = [convs[c] for c in reversed(order)][:n]
    _cache.update(ts=time.time(), list=ordered)
    return ordered


def delete(conv_id: str) -> bool:
    """Apaga uma conversa inteira (todas as linhas com aquele id)."""
    ws = _ws()
    col = ws.col_values(1)
    rows = [i for i in range(len(col), 1, -1) if col[i - 1] == str(conv_id)]  # de baixo p/ cima
    for i in rows:
        ws.delete_rows(i)
    _cache["list"] = None
    return True
