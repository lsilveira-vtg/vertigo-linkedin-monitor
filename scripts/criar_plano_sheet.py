"""Cria a PLANILHA EDITÁVEL do plano de mídia, já com o plano de hoje.

Roda UMA vez, no GitLab CI (onde a conta de serviço tem as credenciais). A conta
de serviço do agente cria e passa a ser dona da planilha (então o agente já lê sem
precisar de compartilhamento extra), compartilha edição com os e-mails de
PLANO_EDITORS e imprime o ID da planilha no final.

Depois de rodar:
  1. Copie o ID impresso e cadastre em CI/CD > Variables como PLANO_SHEET_ID.
  2. (Opcional) Cadastre PLANO_CHANGE_RECIPIENTS com os e-mails do aviso de mudança.
  3. A partir daí o agente lê o plano da planilha na coleta diária.

Variáveis usadas: GOOGLE_SERVICE_ACCOUNT_JSON, PLANO_EDITORS (e-mails separados por
vírgula), PLANO_FOLDER_ID (pasta do Drive; padrão = pasta do projeto). Reexecução:
protegida — defina FORCE_CRIAR=1 para criar outra mesmo com PLANO_SHEET_ID já setado.
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
    [f"Planilha criada em {date.today().strftime('%d/%m/%Y')} com o plano vigente."],
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


def _preencher(ws, header: list[str], rows: list[list]) -> None:
    ws.update([header] + rows, "A1")
    ws.format(f"A1:{chr(ord('A') + len(header) - 1)}1",
              {"textFormat": {"bold": True},
               "backgroundColor": {"red": 0.13, "green": 0.13, "blue": 0.13},
               "horizontalAlignment": "CENTER"})
    ws.format(f"A1:{chr(ord('A') + len(header) - 1)}1",
              {"textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True}})
    ws.freeze(rows=1)


def main() -> None:
    if config.PLANO_SHEET_ID and os.getenv("FORCE_CRIAR") != "1":
        print(f"PLANO_SHEET_ID já configurado ({config.PLANO_SHEET_ID}). "
              "Nada a fazer. Use FORCE_CRIAR=1 para criar outra mesmo assim.")
        return

    creds, sa_email = _creds()
    gc = gspread.authorize(creds)
    dados = plano.DADOS_PADRAO
    titulo = "Plano de Mídia Paga — Vertigo (editável)"
    folder = config.PLANO_FOLDER_ID or None

    try:
        sh = gc.create(titulo, folder_id=folder)
        print(f"Planilha criada na pasta {folder}.")
    except Exception as exc:
        print(f"  aviso: não criei dentro da pasta ({exc}); criando fora e seguindo.")
        sh = gc.create(titulo)

    # Abas
    leiame = sh.sheet1
    leiame.update_title(plano_sheet.TAB_LEIAME)
    leiame.update(LEIAME, "A1")
    leiame.format("A1", {"textFormat": {"bold": True, "fontSize": 13}})

    conj = sh.add_worksheet(title=plano_sheet.TAB_CONJUNTOS, rows=50, cols=len(plano_sheet.HDR_CONJUNTOS))
    conj_rows = [[c["codigo"], c["nome"], c["tipo"], c["status"], c["verba_dia"],
                  c.get("inicio", ""), c.get("fim", ""), c.get("obs", "")] for c in dados["conjuntos"]]
    _preencher(conj, plano_sheet.HDR_CONJUNTOS, conj_rows)

    par = sh.add_worksheet(title=plano_sheet.TAB_PARAMETROS, rows=30, cols=2)
    _preencher(par, plano_sheet.HDR_PARAMETROS, _parametros_rows(dados))

    obs = sh.add_worksheet(title=plano_sheet.TAB_OBSERVACOES, rows=100, cols=2)
    obs_rows = [[o.get("data", ""), o.get("texto", "")] for o in dados.get("observacoes", [])]
    _preencher(obs, plano_sheet.HDR_OBSERVACOES, obs_rows)

    est = sh.add_worksheet(title=plano_sheet.TAB_ESTADO, rows=5, cols=2)
    try:
        est.update_tab_color("888888")
        sh.batch_update({"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": est.id, "hidden": True}, "fields": "hidden"}}]})
    except Exception:
        pass

    # Compartilha edição
    editores = config.PLANO_EDITORS
    for email in editores:
        try:
            sh.share(email, perm_type="user", role="writer", notify=True,
                     email_message="Planilha do plano de mídia do agente — edite aqui que o agente aplica sozinho.")
            print(f"  compartilhado (edição) com {email}")
        except Exception as exc:
            print(f"  aviso: não compartilhei com {email}: {exc}")
    if not editores:
        print("  aviso: PLANO_EDITORS vazio — ninguém recebeu acesso de edição ainda.")

    print("\n================ PRONTO ================")
    print(f"Dona (conta de serviço): {sa_email}")
    print(f"PLANO_SHEET_ID = {sh.id}")
    print(f"URL: https://docs.google.com/spreadsheets/d/{sh.id}")
    print("Cadastre o PLANO_SHEET_ID em CI/CD > Variables para o agente passar a ler o plano da planilha.")


if __name__ == "__main__":
    main()
