"""Lê (e escreve o estado de diff) da planilha EDITÁVEL do plano de mídia.

A planilha é a fonte de verdade do plano quando PLANO_SHEET_ID está configurado.
Júlia/Vitor editam as abas abaixo; o agente lê na coleta diária. O formato aqui é
o mesmo usado por scripts/criar_plano_sheet.py para montar a planilha inicial.

Abas:
- "Conjuntos":  um conjunto de anúncios por linha (o que mais muda).
- "Parâmetros": Liferay (teto/gastos/datas) e tetos mensais, como pares rótulo/valor.
- "Observações": log livre de mudanças (data + texto).
- "Leia-me":    instruções (não é lida pelo agente).
- "_estado":    oculta — o agente guarda aqui o último plano lido, para detectar mudanças.
"""
import re
from datetime import date

from . import sheets_client

TAB_CONJUNTOS = "Conjuntos"
TAB_PARAMETROS = "Parâmetros"
TAB_OBSERVACOES = "Observações"
TAB_LEIAME = "Leia-me"
TAB_ESTADO = "_estado"

HDR_CONJUNTOS = ["Código", "Nome", "Tipo (leads/tráfego/marca)",
                 "Status (ativo/pausado/encerrado)", "Verba/dia (R$)",
                 "Início", "Fim", "Observações"]
HDR_PARAMETROS = ["Parâmetro", "Valor"]
HDR_OBSERVACOES = ["Data", "O que mudou"]


def _open(sheet_id: str):
    return sheets_client._client().open_by_key(sheet_id)


def _num(v) -> float:
    """Converte 'R$ 1.234,56', '1234.56', '28', '' em float (0.0 se vazio/invalido)."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("R$", "").replace(" ", "")
    if not s:
        return 0.0
    # Formato BR "1.234,56" -> remove milhar '.', troca decimal ',' por '.'
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _tipo(v: str) -> str:
    t = (v or "").strip().lower()
    if t.startswith("marca") or t.startswith("brand"):
        return "marca"
    if t.startswith("tráf") or t.startswith("traf"):
        return "tráfego"
    return "leads"


def _status(v: str) -> str:
    s = (v or "").strip().lower()
    for k in ("encerr", "pausad", "ativ"):
        if s.startswith(k):
            return {"encerr": "encerrado", "pausad": "pausado", "ativ": "ativo"}[k]
    return s or "ativo"


def _data(v) -> date | None:
    s = str(v or "").strip()
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _ws(sheet, titulo):
    try:
        return sheet.worksheet(titulo)
    except Exception:
        return None


def ler(sheet_id: str) -> dict:
    """Lê o plano da planilha e devolve o dict no formato de plano.DADOS_PADRAO.
    Levanta exceção se não conseguir abrir (o chamador cai no fallback)."""
    sheet = _open(sheet_id)

    # --- Conjuntos ---
    conjuntos: list[dict] = []
    ws = _ws(sheet, TAB_CONJUNTOS)
    if ws:
        for row in ws.get_all_values()[1:]:
            row = (row + [""] * 8)[:8]
            codigo = row[0].strip()
            nome = row[1].strip()
            if not codigo and not nome:
                continue
            conjuntos.append({
                "codigo": codigo, "nome": nome,
                "tipo": _tipo(row[2]), "status": _status(row[3]),
                "verba_dia": _num(row[4]),
                "inicio": row[5].strip(), "fim": row[6].strip(), "obs": row[7].strip(),
            })

    # --- Parâmetros (Liferay + tetos) ---
    liferay = {"teto": 0.0, "antiga_final": 0.0, "nova_gasto": 0.0, "nova_trava": 0.0,
               "base_data": None, "fim": None}
    tetos: dict[str, float] = {}
    ws = _ws(sheet, TAB_PARAMETROS)
    if ws:
        for row in ws.get_all_values()[1:]:
            if len(row) < 2:
                continue
            rotulo, valor = row[0].strip().lower(), row[1]
            if not rotulo:
                continue
            mes = re.search(r"(20\d\d)[-/](\d{1,2})", rotulo)
            if "teto do mês" in rotulo and mes:
                tetos[f"{mes.group(1)}-{int(mes.group(2)):02d}"] = _num(valor)
            elif "liferay" in rotulo:
                if "teto" in rotulo:
                    liferay["teto"] = _num(valor)
                elif "antiga" in rotulo:
                    liferay["antiga_final"] = _num(valor)
                elif "nova" in rotulo and ("base" in rotulo or "gasto" in rotulo):
                    liferay["nova_gasto"] = _num(valor)
                elif "trava" in rotulo:
                    liferay["nova_trava"] = _num(valor)
                elif "base" in rotulo:
                    liferay["base_data"] = _data(valor)
                elif "encerr" in rotulo or "fim" in rotulo:
                    liferay["fim"] = _data(valor)

    # --- Observações ---
    observacoes: list[dict] = []
    ws = _ws(sheet, TAB_OBSERVACOES)
    if ws:
        for row in ws.get_all_values()[1:]:
            row = (row + ["", ""])[:2]
            texto = row[1].strip()
            if texto:
                observacoes.append({"data": row[0].strip(), "texto": texto})

    return {"conjuntos": conjuntos, "liferay": liferay, "tetos": tetos, "observacoes": observacoes}


def ler_estado(sheet_id: str) -> str:
    """Último snapshot do plano guardado na aba oculta _estado (string JSON) ou ''."""
    sheet = _open(sheet_id)
    ws = _ws(sheet, TAB_ESTADO)
    if not ws:
        return ""
    try:
        return ws.acell("A1").value or ""
    except Exception:
        return ""


def gravar_estado(sheet_id: str, conteudo: str) -> None:
    """Grava o snapshot atual na aba oculta _estado (cria a aba se faltar)."""
    sheet = _open(sheet_id)
    ws = _ws(sheet, TAB_ESTADO)
    if not ws:
        ws = sheet.add_worksheet(title=TAB_ESTADO, rows=10, cols=2)
        try:
            ws.update_tab_color("888888")
        except Exception:
            pass
    ws.update("A1", [[conteudo]])
