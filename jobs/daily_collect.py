"""Job diário: coleta dados do LinkedIn Ads e atualiza a planilha.

Coleta de forma incremental: do dia seguinte ao último já salvo na planilha
até ontem. Assim, mesmo sem rodar no fim de semana (o GitLab da Vertigo fica
desligado sáb/dom e antes das 07h), a execução de segunda recupera sexta,
sábado e domingo automaticamente — sem perder dados e sem duplicar.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import linkedin_client, sheets_client
from src.report_builder import RATEIO_CAMPANHAS, RATEIO_FATOR

# "Invest rateado (R$)" no FIM (não desloca colunas existentes): é o gasto com o
# rateio 50/50 da Liferay aplicado, para o Looker/planilha baterem com o dashboard.
CAMP_HEADER = ["Data", "Campanha", "Invest (R$)", "Leads", "CPL (R$)",
               "Impressões", "Cliques", "Reações", "Comentários", "Compartilhamentos",
               "Invest rateado (R$)"]
ADS_HEADER = ["Data", "Anúncio (ID)", "Campanha", "Link", "Invest (R$)", "Impressões",
              "Cliques", "Reações", "Comentários", "Compartilhamentos"]


def _last_collected_date(sheet) -> date | None:
    """Maior data já presente na aba 'Campanhas' (coluna A)."""
    try:
        col = sheet.worksheet("Campanhas").col_values(1)[1:]  # pula o cabeçalho
    except Exception:
        return None
    datas = []
    for v in col:
        try:
            datas.append(date.fromisoformat(v.strip()))
        except (ValueError, AttributeError):
            continue
    return max(datas) if datas else None


def _row_date(row: dict) -> str:
    """Extrai a data (AAAA-MM-DD) do dateRange da linha de analytics."""
    s = row.get("dateRange", {}).get("start", {})
    return date(s["year"], s["month"], s["day"]).isoformat()


def main() -> None:
    yesterday = date.today() - timedelta(days=1)
    sheet = sheets_client.open_sheet()
    last = _last_collected_date(sheet)

    if last and last >= yesterday:
        print(f"Planilha já atualizada até {last}. Nada novo a coletar.")
    else:
        start = (last + timedelta(days=1)) if last else yesterday
        print(f"Coletando de {start} até {yesterday}...")

        campaigns = linkedin_client.get_campaigns()
        names = {str(c["id"]): c.get("name", str(c["id"])) for c in campaigns}

        def _name(urn: str) -> str:
            return names.get(urn.rsplit(":", 1)[-1], urn)

        # Fator de rateio por grupo de anúncios (0.5 nos grupos da campanha Liferay),
        # para gravar a coluna "Invest rateado". Se a API falhar, cai para bruto (1.0).
        try:
            cg_nomes = {str(g["id"]): (g.get("name") or "").lower()
                        for g in linkedin_client.get_campaign_groups()}
        except Exception as exc:
            print(f"  aviso: não carreguei os grupos de campanha (rateio): {exc}")
            cg_nomes = {}

        def _fator(c: dict) -> float:
            gid = str(c.get("campaignGroup") or "").rsplit(":", 1)[-1]
            nome = cg_nomes.get(gid, "")
            return RATEIO_FATOR if any(t in nome for t in RATEIO_CAMPANHAS) else 1.0

        fator_by_id = {str(c["id"]): _fator(c) for c in campaigns}

        analytics = linkedin_client.get_analytics(start, yesterday, pivot="CAMPAIGN")
        ad_analytics = linkedin_client.get_analytics(start, yesterday, pivot="CREATIVE")

        campaign_rows = []
        for row in analytics:
            invest = float(row.get("costInLocalCurrency", 0) or 0)
            leads = int(row.get("oneClickLeads", 0) or 0)
            adid = row.get("pivotValues", [""])[0].rsplit(":", 1)[-1]
            fator = fator_by_id.get(adid, 1.0)
            campaign_rows.append([
                _row_date(row), _name(row.get("pivotValues", [""])[0]),
                invest, leads, round(invest / leads, 2) if leads else "",
                row.get("impressions", 0), row.get("clicks", 0),
                row.get("likes", 0), row.get("comments", 0), row.get("shares", 0),
                round(invest * fator, 2),   # Invest rateado (50/50 na Liferay)
            ])

        creative_cache: dict[str, tuple[str, str]] = {}
        ad_rows = []
        for row in ad_analytics:
            ad_id = row.get("pivotValues", [""])[0].rsplit(":", 1)[-1]
            if ad_id not in creative_cache:
                camp_name, link = "", ""
                try:
                    cr = linkedin_client.get_creative(ad_id)
                    camp_name = names.get(cr.get("campaign", "").rsplit(":", 1)[-1], "")
                    link = linkedin_client.post_url(cr.get("content", {}).get("reference", ""))
                except Exception as exc:
                    print(f"  aviso: não resolvi o anúncio {ad_id}: {exc}")
                creative_cache[ad_id] = (camp_name, link)
            camp_name, link = creative_cache[ad_id]
            ad_rows.append([
                _row_date(row), ad_id, camp_name, link,
                round(float(row.get("costInLocalCurrency", 0) or 0), 2),
                row.get("impressions", 0), row.get("clicks", 0),
                row.get("likes", 0), row.get("comments", 0), row.get("shares", 0),
            ])

        sheets_client.ensure_tabs()
        sheets_client.set_header("Campanhas", CAMP_HEADER)
        sheets_client.set_header("Anúncios", ADS_HEADER)
        if campaign_rows:
            sheets_client.append_rows("Campanhas", campaign_rows)
        if ad_rows:
            sheets_client.append_rows("Anúncios", ad_rows)
        print(f"Coleta concluída: {len(campaign_rows)} linhas de campanha, {len(ad_rows)} de anúncios.")

    # Período do MÊS CORRENTE (mesma regra do dashboard e da análise: reports.period_for),
    # para a planilha, o painel e os textos ficarem sempre com os MESMOS números.
    from src import reports
    m_start, m_end = reports.period_for(None)

    # Atualiza as visualizações organizadas (Resumo + aba por campanha) do mês corrente
    try:
        from src import sheets_views
        period = f"{m_start.strftime('%d/%m')} a {m_end.strftime('%d/%m/%Y')}"
        sheets_views.rebuild_all(period, m_start, m_end)
        print("Visualizações (Resumo + abas por campanha) atualizadas.")
    except Exception as exc:
        print(f"  aviso: falha ao atualizar visualizações: {exc}")

    # Lê o plano da planilha editável e, se Júlia/Vitor mudaram algo desde ontem,
    # avisa por e-mail (um resumo só, e só quando houve mudança). Roda ANTES dos
    # textos do dia, para os snapshots já saírem com o plano atualizado.
    try:
        from src import plano_mudancas
        plano_mudancas.checar_e_avisar()
    except Exception as exc:
        print(f"  aviso: checagem de mudanças do plano falhou: {exc}")

    # Pré-gera e congela os textos do dia (card do painel + relatório parcial). Assim,
    # quando a primeira pessoa abrir o painel, a análise já está pronta e idêntica para
    # todos (single source of truth), sem a "corrida" do primeiro clique.
    try:
        from src.report_builder import collect_campaign_data
        dados = collect_campaign_data(m_start, m_end)
        reports.load_or_build_card(data=dados)
        reports.load_or_build_report(data=dados)
        print("Textos do dia pré-gerados (card + relatório).")
    except Exception as exc:
        print(f"  aviso: não pré-gerei os textos do dia: {exc}")


if __name__ == "__main__":
    main()
