"""Preenche a PLANILHA EDITÁVEL do plano com o plano de hoje (uma vez).

Conta de serviço NÃO pode criar/ser dona de arquivos (não tem cota no Drive).
Então o fluxo é:
  1. Leandro CRIA uma planilha em branco (na pasta do projeto), como ele mesmo.
  2. COMPARTILHA ela (Editor) com a conta de serviço do agente e com o time.
  3. Cadastra o ID em CI/CD > Variables como PLANO_SHEET_ID.
  4. Roda este job (popular_plano_sheet): o agente preenche as abas do plano.

Usa só a API de Sheets (funciona numa planilha compartilhada com a conta de
serviço). Seguro: NÃO sobrescreve se a aba 'Conjuntos' já tiver dados (proteção
contra apagar edições do time) — use FORCE_POPULAR=1 para forçar mesmo assim.
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import gspread
from google.oauth2.service_account import Credentials

from src import config, plano, plano_sheet

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

LEIAME = [
    ["PLANO DE MÍDIA PAGA — VERTIGO (planilha editável)"],
    [""],
    ["Esta planilha é a FONTE do plano que o agente de mídia paga usa nas análises."],
    ["Edite aqui e o agente aplica sozinho na próxima coleta diária (de manhã)."],
    ["Quando você muda algo, o agente manda um e-mail curto avisando o que mudou."],
    [""],
    ["COMO EDITAR:"],
    ["• Aba 'Conjuntos': um conjunto de anúncios por linha. Mude a verba, o status"],
    ["  (ativo / pausado / encerrado) ou as datas. Para um conjunto novo, adicione"],
    ["  uma linha nova com o código e o nome exatos do Campaign Manager."],
    ["• Aba 'Parâmetros': teto e gastos da Liferay e os tetos mensais da conta."],
    ["• Aba 'Observações': escreva com suas palavras o que não cabe num número"],
    ["  (mudança de público, de estratégia, de criativo, etc.)."],
    [""],
    ["IMPORTANTE: editar aqui AVISA o agente, mas NÃO mexe no LinkedIn. Quem pausa,"],
    ["cria ou muda público continua sendo o time no Campaign Manager. A planilha só"],
    ["mantém o agente informado para a análise bater com a realidade."],
    [""],
    ["Não mexa na aba '_estado' (uso interno do agente)."],
    [f"Preenchida em {date.today().strftime('%d/%m/%Y')} com o plano vigente."],
]


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


def _ws(sh, titulo, rows, cols):
    """Pega a aba pelo título ou cria. Limpa o conteúdo para reescrever."""
    try:
        ws = sh.worksheet(titulo)
        ws.clear()
        return ws
    except Exception:
        return sh.add_worksheet(title=titulo, rows=rows, cols=cols)


def _preencher(ws, header, rows):
    ws.update([header] + rows, "A1")
    ult = chr(ord("A") + len(header) - 1)
    ws.format(f"A1:{ult}1", {"textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                             "backgroundColor": {"red": 0.13, "green": 0.13, "blue": 0.13},
                             "horizontalAlignment": "CENTER"})
    ws.freeze(rows=1)


def main() -> None:
    sid = config.PLANO_SHEET_ID
    creds, sa_email = _creds()
    print(f"Conta de serviço do agente: {sa_email}")
    if not sid:
        print("\nERRO: PLANO_SHEET_ID não está configurado.\n"
              "1) Crie uma planilha em branco no Drive (na pasta do projeto).\n"
              f"2) Compartilhe (Editor) com: {sa_email}  (e com o time).\n"
              "3) Cadastre o ID da planilha em CI/CD > Variables como PLANO_SHEET_ID.\n"
              "4) Rode este job de novo.")
        sys.exit(1)

    gc = gspread.authorize(creds)
    try:
        sh = gc.open_by_key(sid)
    except Exception as exc:
        print(f"\nERRO: não consegui abrir a planilha {sid}: {exc}\n"
              f"Confirme que ela foi COMPARTILHADA (Editor) com {sa_email}.")
        sys.exit(1)
    print(f"Planilha aberta: {sh.title}")

    # Proteção: não sobrescrever edições do time
    try:
        conj_existente = sh.worksheet(plano_sheet.TAB_CONJUNTOS).get_all_values()
        if len(conj_existente) > 1 and __import__("os").getenv("FORCE_POPULAR") != "1":
            print("A aba 'Conjuntos' já tem dados — NÃO vou sobrescrever. "
                  "Use FORCE_POPULAR=1 se quiser repreencher do zero.")
            return
    except Exception:
        pass

    dados = plano.DADOS_PADRAO

    leiame = _ws(sh, plano_sheet.TAB_LEIAME, 30, 1)
    leiame.update(LEIAME, "A1")
    leiame.format("A1", {"textFormat": {"bold": True, "fontSize": 13}})

    conj = _ws(sh, plano_sheet.TAB_CONJUNTOS, 50, len(plano_sheet.HDR_CONJUNTOS))
    _preencher(conj, plano_sheet.HDR_CONJUNTOS,
               [[c["codigo"], c["nome"], c["tipo"], c["status"], c["verba_dia"],
                 c.get("inicio", ""), c.get("fim", ""), c.get("obs", "")] for c in dados["conjuntos"]])

    par = _ws(sh, plano_sheet.TAB_PARAMETROS, 30, 2)
    _preencher(par, plano_sheet.HDR_PARAMETROS, _parametros_rows(dados))

    obs = _ws(sh, plano_sheet.TAB_OBSERVACOES, 100, 2)
    _preencher(obs, plano_sheet.HDR_OBSERVACOES,
               [[o.get("data", ""), o.get("texto", "")] for o in dados.get("observacoes", [])])

    est = _ws(sh, plano_sheet.TAB_ESTADO, 5, 2)
    try:
        est.update_tab_color("888888")
        sh.batch_update({"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": est.id, "hidden": True}, "fields": "hidden"}}]})
    except Exception:
        pass

    # Remove a aba padrão vazia ("Sheet1"/"Página1"), se sobrou
    nossas = {plano_sheet.TAB_LEIAME, plano_sheet.TAB_CONJUNTOS, plano_sheet.TAB_PARAMETROS,
              plano_sheet.TAB_OBSERVACOES, plano_sheet.TAB_ESTADO}
    for ws in sh.worksheets():
        if ws.title not in nossas:
            try:
                sh.del_worksheet(ws)
            except Exception:
                pass

    # Compartilha edição com o time (best-effort; se falhar, compartilhe pela interface)
    for email in config.PLANO_EDITORS:
        try:
            sh.share(email, perm_type="user", role="writer", notify=False)
            print(f"  compartilhado (edição) com {email}")
        except Exception as exc:
            print(f"  aviso: não compartilhei com {email} (compartilhe pela interface): {exc}")

    print("\n================ PRONTO ================")
    print(f"Planilha preenchida: https://docs.google.com/spreadsheets/d/{sh.id}")
    print("O agente já vai ler o plano desta planilha na próxima coleta diária.")


if __name__ == "__main__":
    main()
