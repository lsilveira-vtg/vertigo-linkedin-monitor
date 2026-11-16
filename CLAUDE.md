# Vertigo LinkedIn Monitor (agente de mídia paga)

Agente que coleta dados do LinkedIn Ads da Vertigo, analisa a performance, recomenda ações e envia relatórios. Documentação completa em `README.md` e `docs/ARQUITETURA.md`. Leia esses dois antes de mudanças grandes.

## ATENÇÃO: não existe ambiente de testes

O painel `https://midiapaga-api.vtgdev.net` é produção final. **Todo push na `main` entra em produção** (o job `deploy-bot` do `.gitlab-ci.yml` faz SSH na EC2 e roda `docker compose`). Faça o trabalho em branch, revise antes de mesclar na `main` e peça confirmação antes de qualquer push.

## Repositórios

- `origin`: GitLab da Vertigo (`gitlab.vertigo-devops.com:Silveira/vertigo-linkedin-monitor`). É onde roda o pipeline (coleta diária, relatórios, deploy).
- `github`: backup no GitHub (`lsilveira-vtg/vertigo-linkedin-monitor`). Actions desativado.

## Estrutura

- `src/`: lógica principal. `linkedin_client.py` (API do LinkedIn), `sheets_client.py` e `sheets_views.py` (Google Sheets), `analyst.py` (motor de regras), `analyst_ai.py` (camada de IA com Claude), `budget.py` (tetos de orçamento), `plano.py` (plano de mídia vigente), `report_builder.py`, `report_html.py`, `reports.py`, `dashboard_data.py`, `mailer.py`.
- `api/`: API FastAPI (`main.py`) e frontend do painel (`api/static/`). O frontend é servido por volume, então mudanças nele não exigem rebuild.
- `jobs/`: `daily_collect.py`, `weekly_report.py`, `monthly_report.py`.
- `bot/`: bot do Discord (`/report`, `/status`, `/budget`).
- `scripts/`: setup da planilha e backfill.

## Regras do projeto

- O agente é **consultivo**: só recomenda. Não executa nada no LinkedIn; o token é somente leitura.
- **Nunca** commitar `.env` nem `service_account.json`. Chaves e senhas ficam só nas variáveis do GitLab CI/CD. Nunca colar chaves no chat.
- Tetos de orçamento e o plano de mídia vigente ficam em `src/budget.py` e `src/plano.py`. Quando a equipe de mídia mudar a estratégia, é lá que se atualiza.
- Texto para o usuário: português do Brasil, sem travessão ("—"), sem anglicismos de status. Usar "acima do teto" em vez de "estourado".
- Um "grupo de anúncios" é o que a API do LinkedIn chama de `campaign`. "Campanha" é o nível acima (`campaignGroup`).
- Campanhas de tráfego e de marca não são avaliadas por leads nem CPL. A classificação fica em `report_builder.py`.
- Quando a lógica de análise mudar, aumentar `_CARD_VER` e `_RPT_VER` em `reports.py` para regenerar os resultados congelados do dia.

## Ao terminar uma entrega

Atualizar o `README.md` (seção de próximas etapas) e o Project Board junto com o código, sem esperar pedido.

## Rodar localmente

Copie `.env.example` para `.env` e preencha as credenciais. Detalhes de deploy e variáveis estão no `README.md`.
