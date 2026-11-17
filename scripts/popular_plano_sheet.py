"""Preenche e FORMATA a planilha editável do plano com o plano de hoje.

Conta de serviço NÃO pode criar/ser dona de arquivos (sem cota no Drive). Fluxo:
  1. Leandro CRIA a planilha em branco e COMPARTILHA (Editor) com a conta de serviço.
  2. Cadastra o ID em CI/CD > Variables como PLANO_SHEET_ID.
  3. Roda este job: preenche as abas (se vazias) e aplica a formatação visual.

Seguro para re-rodar: a FORMATAÇÃO sempre é reaplicada (não toca em valores); os
VALORES só são (re)escritos se a aba 'Conjuntos' estiver vazia ou com FORCE_POPULAR=1.
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import gspread
from google.oauth2.service_account import Credentials

from src import config, plano, plano_sheet

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# Paleta
NAVY = {"red": 0.11, "green": 0.22, "blue": 0.40}
WHITE = {"red": 1, "green": 1, "blue": 1}
BAND2 = {"red": 0.95, "green": 0.96, "blue": 0.99}
GREEN = {"red": 0.85, "green": 0.93, "blue": 0.83}
AMBER = {"red": 1.0, "green": 0.95, "blue": 0.80}
GREY = {"red": 0.91, "green": 0.91, "blue": 0.91}
GREY_TXT = {"red": 0.5, "green": 0.5, "blue": 0.5}

LEIAME = [
    ["📋 PLANO DE MÍDIA PAGA — VERTIGO (planilha editável)"],
    [""],
    ["Esta planilha é a FONTE do plano que o agente de mídia paga usa nas análises."],
    ["Edite aqui e o agente aplica sozinho na próxima coleta diária (de manhã)."],
    ["Quando você muda algo, o agente manda um e-mail curto avisando o que mudou."],
    [""],
    ["COMO EDITAR"],
    ["• Aba 'Conjuntos': um conjunto de anúncios por linha. Mude a verba, o status"],
    ["  (ativo / pausado / encerrado) ou as datas. Para um conjunto novo, adicione uma"],
    ["  linha nova com o código e o nome exatos do Campaign Manager."],
    ["• Aba 'Parâmetros': teto e gastos da Liferay e os tetos mensais da conta."],
    ["• Aba 'Observações': escreva com suas palavras o que não cabe num número"],
    ["  (mudança de público, de estratégia, de criativo, etc.)."],
    [""],
    ["IMPORTANTE"],
    ["Editar aqui AVISA o agente, mas NÃO mexe no LinkedIn. Quem pausa, cria ou muda"],
    ["público continua sendo o time no Campaign Manager. A planilha só mantém o agente"],
    ["informado para a análise bater com a realidade."],
    [""],
    ["Não mexa na aba '_estado' (uso interno do agente)."],
    [f"Preenchida em {date.today().strftime('%d/%m/%Y')} com o plano vigente."],
]
# Linhas (1-based) do Leia-me que são títulos/destaque
LEIAME_TITULO = 1
LEIAME_SECOES = (7, 15)


def _creds():
    info = json.loads(config.GOOGLE_SERVICE_ACCOUNT_JSON)
    return Credentials.from_service_account_info(info, scopes=SCOPES), info.get("client_email", "?")


def _fmt_data(d) -> str:
    return d.strftime("%d/%m/%Y") if isinstance(d, date) else str(d or "")


def _parametros_rows(dados: dict) -> list[list]:
    lf = dados["liferay"]
    rows = [
        ["Liferay — teto total (R$)", lf["teto"]],
        ["Liferay — gasto da campanha antiga, encerrada (R$)", lf["antiga_final"]],
        ["Liferay — gasto da campanha nova até a data base (R$)", lf["nova_gasto"]],
        ["Liferay — trava da campanha nova (R$)", lf["nova_trava"]],
        ["Liferay — data base (dd/mm/aaaa)", _fmt_data(lf["base_data"])],
        ["Liferay — data de encerramento (dd/mm/aaaa)", _fmt_data(lf["fim"])],
    ]
    for mes, val in sorted(dados.get("tetos", {}).items()):
        rows.append([f"Teto do mês ({mes}) (R$)", val])
    return rows


def _get_or_create(sh, titulo, rows, cols):
    try:
        return sh.worksheet(titulo)
    except Exception:
        return sh.add_worksheet(title=titulo, rows=rows, cols=cols)


# ---- construtores de requests da Sheets API --------------------------------
def _dim(sid, dim, start, end, px):
    return {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": dim,
            "startIndex": start, "endIndex": end}, "properties": {"pixelSize": px}, "fields": "pixelSize"}}


def _rep(sid, r0, r1, c0, c1, fmt, fields):
    return {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
            "startColumnIndex": c0, "endColumnIndex": c1}, "cell": {"userEnteredFormat": fmt},
            "fields": "userEnteredFormat(" + fields + ")"}}


def _header(sid, ncols):
    return _rep(sid, 0, 1, 0, ncols, {"backgroundColor": NAVY, "verticalAlignment": "MIDDLE",
               "horizontalAlignment": "CENTER", "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 10}},
               "backgroundColor,horizontalAlignment,verticalAlignment,textFormat")


def _freeze(sid, rows=1, cols=0):
    return {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties":
            {"frozenRowCount": rows, "frozenColumnCount": cols}}, "fields":
            "gridProperties(frozenRowCount,frozenColumnCount)"}}


def _dv(sid, c0, c1, valores):
    return {"setDataValidation": {"range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 1000,
            "startColumnIndex": c0, "endColumnIndex": c1}, "rule": {"condition": {"type": "ONE_OF_LIST",
            "values": [{"userEnteredValue": v} for v in valores]}, "showCustomUi": True, "strict": False}}}


def _cf(sid, c0, c1, texto, bg, strike=False):
    fmt = {"backgroundColor": bg}
    if strike:
        fmt["textFormat"] = {"foregroundColor": GREY_TXT, "strikethrough": True}
    return {"addConditionalFormatRule": {"rule": {"ranges": [{"sheetId": sid, "startRowIndex": 1,
            "endRowIndex": 1000, "startColumnIndex": c0, "endColumnIndex": c1}], "booleanRule":
            {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": texto}]}, "format": fmt}}, "index": 0}}


def _band(sid, ncols):
    return {"addBanding": {"bandedRange": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1000,
            "startColumnIndex": 0, "endColumnIndex": ncols}, "rowProperties": {"headerColor": NAVY,
            "firstBandColor": WHITE, "secondBandColor": BAND2}}}}


def _send(sh, reqs, rotulo):
    if not reqs:
        return
    try:
        sh.batch_update({"requests": reqs})
    except Exception as exc:
        print(f"  aviso: formatação '{rotulo}' falhou (segue sem ela): {exc}")


def _limpar_bandas_e_cf(sh):
    """Remove bandings e regras de formatação condicional existentes (re-run limpo)."""
    reqs = []
    try:
        meta = sh.fetch_sheet_metadata()
    except Exception:
        return
    for s in meta.get("sheets", []):
        sid = s["properties"]["sheetId"]
        for b in s.get("bandedRanges", []) or []:
            reqs.append({"deleteBanding": {"bandedRangeId": b["bandedRangeId"]}})
        cfs = s.get("conditionalFormats", []) or []
        for i in range(len(cfs) - 1, -1, -1):
            reqs.append({"deleteConditionalFormatRule": {"sheetId": sid, "index": i}})
    _send(sh, reqs, "limpeza")


def _estilizar(sh, conj, par, obs, leiame):
    _limpar_bandas_e_cf(sh)

    # --- Conjuntos ---
    sid = conj.id
    larg = [85, 290, 100, 115, 100, 72, 72, 560]
    base = [_dim(sid, "COLUMNS", i, i + 1, w) for i, w in enumerate(larg)]
    base += [_dim(sid, "ROWS", 0, 1, 34), _freeze(sid, 1, 1), _header(sid, 8),
             _rep(sid, 1, 1000, 1, 2, {"wrapStrategy": "WRAP", "verticalAlignment": "MIDDLE"}, "wrapStrategy,verticalAlignment"),
             _rep(sid, 1, 1000, 7, 8, {"wrapStrategy": "WRAP", "verticalAlignment": "MIDDLE"}, "wrapStrategy,verticalAlignment"),
             _rep(sid, 1, 1000, 2, 7, {"horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"}, "horizontalAlignment,verticalAlignment"),
             _rep(sid, 1, 1000, 4, 5, {"numberFormat": {"type": "CURRENCY", "pattern": '"R$" #,##0'}}, "numberFormat")]
    _send(sh, base, "conjuntos-base")
    _send(sh, [_band(sid, 8)], "conjuntos-zebra")
    _send(sh, [_dv(sid, 2, 3, ["leads", "tráfego", "marca"]),
               _dv(sid, 3, 4, ["ativo", "pausado", "encerrado"])], "conjuntos-dropdowns")
    _send(sh, [_cf(sid, 3, 4, "ativo", GREEN), _cf(sid, 3, 4, "pausado", AMBER),
               _cf(sid, 3, 4, "encerrado", GREY, strike=True)], "conjuntos-cores")

    # --- Parâmetros ---
    sid = par.id
    _send(sh, [_dim(sid, "COLUMNS", 0, 1, 380), _dim(sid, "COLUMNS", 1, 2, 150),
               _dim(sid, "ROWS", 0, 1, 34), _freeze(sid, 1, 0), _header(sid, 2),
               _rep(sid, 1, 200, 1, 2, {"numberFormat": {"type": "CURRENCY", "pattern": '"R$" #,##0.00'},
                    "horizontalAlignment": "RIGHT"}, "numberFormat,horizontalAlignment")], "parametros-base")
    _send(sh, [_band(sid, 2)], "parametros-zebra")

    # --- Observações ---
    sid = obs.id
    _send(sh, [_dim(sid, "COLUMNS", 0, 1, 90), _dim(sid, "COLUMNS", 1, 2, 850),
               _dim(sid, "ROWS", 0, 1, 34), _freeze(sid, 1, 0), _header(sid, 2),
               _rep(sid, 1, 1000, 0, 1, {"horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"}, "horizontalAlignment,verticalAlignment"),
               _rep(sid, 1, 1000, 1, 2, {"wrapStrategy": "WRAP", "verticalAlignment": "MIDDLE"}, "wrapStrategy,verticalAlignment")], "observacoes-base")
    _send(sh, [_band(sid, 2)], "observacoes-zebra")

    # --- Leia-me ---
    sid = leiame.id
    reqs = [_dim(sid, "COLUMNS", 0, 1, 780),
            _rep(sid, 0, 1, 0, 1, {"backgroundColor": NAVY, "verticalAlignment": "MIDDLE",
                 "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 14}}, "backgroundColor,verticalAlignment,textFormat"),
            _dim(sid, "ROWS", 0, 1, 40),
            _rep(sid, 1, 200, 0, 1, {"wrapStrategy": "WRAP"}, "wrapStrategy")]
    for linha in LEIAME_SECOES:
        reqs.append(_rep(sid, linha - 1, linha, 0, 1, {"textFormat": {"bold": True, "fontSize": 11,
                    "foregroundColor": NAVY}}, "textFormat"))
    _send(sh, reqs, "leiame")


def main() -> None:
    sid = config.PLANO_SHEET_ID
    creds, sa_email = _creds()
    print(f"Conta de serviço do agente: {sa_email}")
    if not sid:
        print("\nERRO: PLANO_SHEET_ID não está configurado.\n"
              f"Crie a planilha, compartilhe (Editor) com {sa_email}, cadastre PLANO_SHEET_ID e rode de novo.")
        sys.exit(1)

    gc = gspread.authorize(creds)
    try:
        sh = gc.open_by_key(sid)
    except Exception as exc:
        print(f"\nERRO: não consegui abrir a planilha {sid}: {exc}\n"
              f"Confirme que foi COMPARTILHADA (Editor) com {sa_email}.")
        sys.exit(1)
    print(f"Planilha aberta: {sh.title}")

    dados = plano.DADOS_PADRAO
    leiame = _get_or_create(sh, plano_sheet.TAB_LEIAME, 30, 1)
    conj = _get_or_create(sh, plano_sheet.TAB_CONJUNTOS, 60, len(plano_sheet.HDR_CONJUNTOS))
    par = _get_or_create(sh, plano_sheet.TAB_PARAMETROS, 30, 2)
    obs = _get_or_create(sh, plano_sheet.TAB_OBSERVACOES, 100, 2)
    _get_or_create(sh, plano_sheet.TAB_ESTADO, 5, 2)

    # (Re)escreve VALORES só se 'Conjuntos' estiver vazia ou com FORCE_POPULAR=1
    tem_dados = len(conj.get_all_values()) > 1
    if not tem_dados or os.getenv("FORCE_POPULAR") == "1":
        leiame.clear(); leiame.update(LEIAME, "A1")
        conj.clear(); conj.update([plano_sheet.HDR_CONJUNTOS] +
            [[c["codigo"], c["nome"], c["tipo"], c["status"], c["verba_dia"],
              c.get("inicio", ""), c.get("fim", ""), c.get("obs", "")] for c in dados["conjuntos"]], "A1")
        par.clear(); par.update([plano_sheet.HDR_PARAMETROS] + _parametros_rows(dados), "A1")
        obs.clear(); obs.update([plano_sheet.HDR_OBSERVACOES] +
            [[o.get("data", ""), o.get("texto", "")] for o in dados.get("observacoes", [])], "A1")
        print("Valores (re)escritos a partir do plano padrão.")
    else:
        print("Aba 'Conjuntos' já tem dados — mantenho os valores e só reaplico a formatação.")

    # Oculta a aba _estado
    try:
        est = sh.worksheet(plano_sheet.TAB_ESTADO)
        est.update_tab_color("888888")
        sh.batch_update({"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": est.id, "hidden": True}, "fields": "hidden"}}]})
    except Exception:
        pass

    # Remove abas padrão vazias que sobraram
    nossas = {plano_sheet.TAB_LEIAME, plano_sheet.TAB_CONJUNTOS, plano_sheet.TAB_PARAMETROS,
              plano_sheet.TAB_OBSERVACOES, plano_sheet.TAB_ESTADO}
    for ws in sh.worksheets():
        if ws.title not in nossas:
            try:
                sh.del_worksheet(ws)
            except Exception:
                pass

    _estilizar(sh, conj, par, obs, leiame)

    for email in config.PLANO_EDITORS:
        try:
            sh.share(email, perm_type="user", role="writer", notify=False)
            print(f"  compartilhado (edição) com {email}")
        except Exception as exc:
            print(f"  aviso: não compartilhei com {email} (faça pela interface): {exc}")

    print("\n================ PRONTO ================")
    print(f"Planilha formatada: https://docs.google.com/spreadsheets/d/{sh.id}")


if __name__ == "__main__":
    main()
