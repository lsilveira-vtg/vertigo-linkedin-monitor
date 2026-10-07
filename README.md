# 📊 Vertigo LinkedIn Monitor

Agente automatizado de monitoramento de mídia paga no LinkedIn da Vertigo. Coleta dados de campanhas, analisa performance, recomenda ações mediante aprovação, e envia reports semanal e mensal por e-mail.

> 🟢 **EM PRODUÇÃO.** Painel oficial: **https://midiapaga-api.vtgdev.net** (login `@vertigo.com.br`). Esse é o ambiente de produção final (não há ambiente de testes separado — todo push na `main` entra em produção). Relatórios semanal e mensal saem por e-mail e publicam versão online no vtg-link (`link.vertigo.com.br`).
>
> 📖 **Documentação completa (funcionalidades + lógica de análise e relatórios):** [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md). O dashboard evoluiu de Looker Studio para um **painel web próprio** (ver a documentação). O log abaixo mantém o histórico das etapas.

---

## Pipeline

```
LinkedIn Marketing API
            ↓
    Coleta diária (Python, incremental)
            ↓
    Google Sheets  →  Painel web (midiapaga-api.vtgdev.net)  +  Looker (legado)
            ↓
    Análise e recomendações do agente (motor de regras + IA)
            ↓
    Painel web  +  Reports por e-mail (semanal/mensal)  +  Discord
```

> O agente é **consultivo**: recomenda ações, mas **não executa** nada no LinkedIn (a decisão é sempre humana).

---

## Acesso do time

| Necessidade | Onde |
|---|---|
| Ver dados e usar o agente | **Painel web:** https://midiapaga-api.vtgdev.net (login `@vertigo.com.br`) — KPIs, gráficos, chat ao vivo e relatório em PDF. Planilha Google Sheets e Looker como apoio. |
| Reports | E-mail (acumulado semanal toda segunda; fechamento mensal no 1º dia útil) |
| Comandos | Bot no Discord (`/report`, `/status`, `/budget`) |

---

## Estrutura do código

```
src/
  config.py           # variáveis de ambiente
  linkedin_client.py  # LinkedIn Advertising API (coleta + ações)
  sheets_client.py    # Google Sheets (conexão e formatação)
  sheets_views.py     # aba "Resumo" + uma aba por campanha
  mailer.py           # envio de e-mail (SMTP / Senha de App)
  report.py           # formatação do report padrão Vertigo
  report_builder.py   # monta o report a partir dos dados coletados
  recommendations.py  # lógica de recomendação de ações
  budget.py           # regras de orçamento (teto, overrides, sub-limites)
  analyst.py          # análise do agente — motor próprio de regras
  analyst_ai.py       # camada opcional de análise por IA (Claude API)
jobs/
  daily_collect.py    # coleta diária (+ atualiza as visualizações)
  weekly_report.py    # report semanal
  monthly_report.py   # report mensal
bot/
  discord_bot.py      # bot do Discord (comandos do time)
scripts/
  setup_sheet.py      # setup inicial das abas
  backfill.py         # backfill de histórico
.gitlab-ci.yml        # pipeline (coleta e reports) no GitLab CI
```

---

## Configuração

1. Copie `.env.example` para `.env` e preencha as credenciais
2. No GitLab, cadastre as mesmas variáveis em **Settings → CI/CD → Variables**
3. Compartilhe a planilha Google Sheets com o e-mail da Service Account

**Importante:** nunca commitar `.env` ou `service_account.json` (já estão no `.gitignore`).

**Variáveis principais:** `LINKEDIN_*`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_SHEET_ID`, `GMAIL_SENDER`, `GMAIL_APP_PASSWORD`, `REPORT_RECIPIENTS`, `CAMPAIGN_CONFIG_JSON`, `BUDGET_RULES_JSON`, `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `DISCORD_GUILD_ID`, `DISCORD_APPROVER_IDS`, e opcional `ANTHROPIC_API_KEY` (ativa a análise por IA).

---

## Log de progresso

### ✅ Etapa 1 — App criado no LinkedIn Developers *(08/06/2026)*
Criado o app **"Monitoramento de Mídia Paga Vertigo"** no LinkedIn Developers com Client ID `78llookt0ujwzb`. O app foi vinculado à página da Vertigo e a company association foi verificada.

### ✅ Etapa 2 — Solicitação de acesso à Advertising API *(08/06/2026)*
Formulário de acesso à LinkedIn Advertising API (Development Tier) submetido. Use cases: Campaign Management e Reporting & ROI. Prazo estimado: 2–5 dias úteis.

### ⏳ Etapa 3 — Aguardando aprovação da LinkedIn API
Etapas com dados reais ficam bloqueadas até a aprovação.

### ✅ Etapa 4 — Estrutura do código *(11/06/2026)*
Criados os módulos de coleta, planilha, e-mail, reports e recomendações, além dos workflows de agendamento no GitHub Actions.

### ✅ Etapa 5 — Planilha Google Sheets *(12/06/2026)*
Planilha criada no Drive do time com 6 abas formatadas. Coluna de CPL automática e períodos início/fim nos históricos (ajustes da coordenação aplicados).

### ✅ Etapa 6 — Service Account no Google Cloud *(12/06/2026)*
Projeto `vertigo-linkedin-monitor` criado na organização vertigo.com.br, com Sheets API e Gmail API ativadas. Chave da Service Account cadastrada nos Secrets do GitHub e conexão com a planilha testada com sucesso.

### ✅ Etapa 7 — Dashboard no Looker/Data Studio *(12/06/2026)*
Relatório "Vertigo · Monitor LinkedIn Ads" conectado à planilha, com cartões de resumo (Invest, Leads, Impressões, Cliques), série temporal e tabela por campanha.

### ✅ Etapa 8 — Bot do Discord *(12/06/2026)*
Código do bot pronto (comandos /report, /pendentes, /aprovar, /rejeitar). App criado no Discord Developer Portal e link de convite enviado à infra.

### ✅ Etapa 9 — Aprovação da API e integração real *(24/06/2026)*
LinkedIn Advertising API aprovada. Acesso direto à conta de anúncios `506583089` (sem depender da Plico). Token de leitura gerado e testado: 225 campanhas e métricas coletadas com sucesso. Coleta diária e reports validados com dados reais.

### ✅ Etapa 10 — Migração para o GitLab da Vertigo *(25/06/2026)*
Projeto migrado para o GitLab corporativo (origin) como fonte principal; GitHub vira backup. Pipeline `.gitlab-ci.yml` (runner `dind`) para coleta diária e reports. Variáveis de credenciais cadastradas em CI/CD. Envio de e-mail via SMTP (Senha de App do `marketing@`), sem depender do admin do Workspace.

### ✅ Etapa 11 — Análise, planilha organizada e regras de orçamento *(02–03/07/2026)*
- **Análise do agente**: motor próprio de regras (benchmarks B2B de CPL/CTR/engajamento) como padrão, sem custo; camada opcional por IA (Claude API) ativável via `ANTHROPIC_API_KEY`.
- **Planilha reorganizada**: aba "📊 Resumo" consolidada (totais, status, saúde 🟢🟡🔴, diagnóstico, orçamento) + uma aba por campanha; aba "Campanhas" bruta alimenta o dashboard.
- **Regras de orçamento**: teto mensal da conta (R$ 2.636,37), override por mês (Jul/2026 R$ 2.534,44) e sub-limite da Liferay (R$ 1.200/mês, pausar após nov/2026), via `BUDGET_RULES_JSON`.
- **Bot ampliado**: comandos `/status` e `/budget`; `/report` traz report + análise. Testado ao vivo no servidor de teste.

### ✅ Etapa 12 — Painel web, chat e relatórios (V2) *(set/2026)*
- **Painel web próprio** em `https://midiapaga-api.vtgdev.net` (FastAPI + HTML/JS), interface principal no lugar do Looker: KPIs, gráficos (gasto x teto, CPL por grupo, distribuição), tabela filtrável e **análise do agente**. Login **Google** restrito a `@vertigo.com.br` (o backend valida o domínio).
- **Chat ao vivo** com o agente (escopo travado só em mídia paga, com **memória da conversa**) e **histórico** compartilhado do time (últimas 20 conversas).
- **Relatório completo em PDF** (7 seções), com modos **parcial** (mês em curso, com projeção) e **fechamento** (mês encerrado, retrospectivo). Consistente entre quem emite ("gera 1x, lê muitas").
- **Análise estável**: gerada 1x/dia e congelada (todos veem a mesma leitura), pré-gerada na coleta diária e no fechamento mensal.
- **Ajustes de negócio** (revisão Julia/Vitor): terminologia "grupo de anúncios", **rateio 50/50** da Liferay, **tetos por mês**, coluna de impressões, e-mail semanal com o acumulado do mês.
- **Deploy automático** a cada push na `main` (SSH na EC2 + `docker compose`).
- **Documentação** completa em [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md).

### ✅ Etapa 13 — Produção, consistência e inteligência de período (set–out/2026)
- **Em produção**: confirmado que `midiapaga-api.vtgdev.net` é o ambiente **oficial e único** (não há "testes" separado).
- **Revisão de 10 pontos (Julia/Vitor)**: e-mail semanal com acumulado do mês, "grupo de anúncios" na nomenclatura, **rateio 50/50 da Liferay**, teto por grupo, **tetos mensais**, coluna de impressões, **chat com memória**, princípio do CPL qualificado.
- **Fonte única do período** (`reports.period_for`): dashboard, planilha, Discord e e-mail usam a mesma regra; o mês corrente é ancorado em **hoje** (corrige o 1º dia do mês).
- **Modo início de mês** (1ª semana): leitura leve, sem alarme de teto, com **paralelo ao mês anterior** e plano para o mês; atalho no painel para o fechamento anterior.
- **Relatório em PDF robusto** (7 seções) com modos **parcial** e **fechamento**; **análise estável** (1x/dia, igual para todos) e **pré-geração** agendada.
- **CPL consolidado** (histórico) no dashboard, planilha, PDF e Discord, ao lado do CPL do mês. Na tabela de grupos, cada linha mostra também o **CPL histórico do próprio grupo** (sublinha "hist.") como referência frente ao CPL do mês.
- **Planilha repaginada**: fechamentos por mês, aba "🔗 Anúncios" com link clicável, abas por campanha formatadas, feeds brutos ocultos; coluna "Invest rateado" para o Looker.
- **vtg-link em produção**: relatórios semanal e mensal publicam a versão online em `link.vertigo.com.br` automaticamente (chave de sistema no GitLab).
- **Acesso restrito** a `@vertigo.com.br` e **chat travado** ao escopo de mídia paga.

---

## Próximas etapas

- [x] Criar app no LinkedIn Developers e configurar OAuth
- [x] Solicitar e obter aprovação da LinkedIn Advertising API
- [x] Estrutura do código e agendamento (GitLab CI)
- [x] Estruturar planilha Google Sheets (+ aba Resumo e abas por campanha)
- [x] Criar Service Account no Google Cloud
- [x] Dashboard Looker/Data Studio
- [x] Bot do Discord (código + comandos /report /status /budget /pendentes /aprovar /rejeitar)
- [x] Migrar para o GitLab da Vertigo
- [x] Envio de e-mail (SMTP com Senha de App)
- [x] Análise do agente (motor próprio + camada IA opcional)
- [x] Regras de orçamento (teto, override, sub-limites)
- [x] Testar coleta e reports com dados reais
- [x] Hospedar o bot em host sempre-ligado (EC2/VM) — `/report` `/status` `/budget` no ar
- [x] Cadastrar variáveis no GitLab (`BUDGET_RULES_JSON`, `DISCORD_CHANNEL_ID` etc.); `CAMPAIGN_CONFIG_JSON` passou a ter default no código
- [x] Configurar Pipeline Schedules no GitLab (coleta diária, report semanal/mensal)
- [x] **Painel web** com KPIs, gráficos, chat ao vivo e relatório em PDF (`midiapaga-api.vtgdev.net`)
- [x] Ajustes de negócio: terminologia "grupo de anúncios", rateio 50/50 Liferay, tetos por mês, impressões
- [x] Documentar e entregar (ver [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md))
- [x] **Entrar em produção** (painel oficial `midiapaga-api.vtgdev.net`)
- [x] Revisão de 10 pontos (Julia/Vitor): rateio 50/50, tetos mensais, chat com memória, impressões etc.
- [x] Consistência entre superfícies (período único) + modo início de mês + CPL consolidado
- [x] Relatórios publicando a versão online no **vtg-link de produção** (`link.vertigo.com.br`)

### Fases futuras (não priorizadas)
- [ ] **Execução automática** de ações (pausar / ajustar budget) — exige token `rw_ads` e fluxo de aprovadores. **Por decisão, o agente é consultivo (só recomenda)**; execução fica para uma fase futura, se o time quiser.
- [ ] GA4 e Search Console.
- [ ] Rede de segurança: limite de gasto (US$ 5/mês) no console da Anthropic.

---

## Referências

- [LinkedIn Marketing API Docs](https://learn.microsoft.com/en-us/linkedin/marketing/)
- [Google Sheets API Docs](https://developers.google.com/sheets/api)
- [Gmail API Docs](https://developers.google.com/gmail/api)
- [Looker Studio](https://lookerstudio.google.com/)
