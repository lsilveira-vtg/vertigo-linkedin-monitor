# 📊 Vertigo LinkedIn Monitor

Agente automatizado de monitoramento de mídia paga no LinkedIn da Vertigo. Coleta dados de campanhas, analisa performance, recomenda ações mediante aprovação, e envia reports semanal e mensal por e-mail.

---

## Pipeline

```
LinkedIn Advertising API
            ↓
    Coleta de dados (Python, diária)
            ↓
    Google Sheets → Dashboard Looker Studio
            ↓
    Análise e recomendações de ações
            ↓
    Aprovação (e-mail / Discord) → Execução via API
            ↓
    Reports semanal e mensal por e-mail
```

---

## Acesso do time

| Necessidade | Onde |
|---|---|
| Ver dados | Dashboard Looker Studio / planilha Google Sheets |
| Reports | E-mail (semanal toda segunda, mensal no 1º dia útil) |
| Comandos e aprovações | Canal `Projeto Agente Mídia Paga` no Discord |

---

## Estrutura do código

```
src/
  config.py           # variáveis de ambiente
  linkedin_client.py  # LinkedIn Advertising API (coleta + ações)
  sheets_client.py    # Google Sheets
  mailer.py           # envio de e-mail (Gmail API)
  report.py           # formatação do report padrão Vertigo
  report_builder.py   # monta o report a partir dos dados coletados
  recommendations.py  # lógica de recomendação de ações
jobs/
  daily_collect.py    # coleta diária
  weekly_report.py    # report semanal
  monthly_report.py   # report mensal
.github/workflows/    # agendamento automático (GitHub Actions)
```

---

## Configuração

1. Copie `.env.example` para `.env` e preencha as credenciais
2. No GitHub, cadastre as mesmas variáveis em **Settings → Secrets and variables → Actions**
3. Compartilhe a planilha Google Sheets com o e-mail da Service Account

**Importante:** nunca commitar `.env` ou `service_account.json` (já estão no `.gitignore`).

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
Código do bot pronto (comandos /report, /pendentes, /aprovar, /rejeitar com lista de aprovadores). App criado no Discord Developer Portal, token nos Secrets e link de convite enviado à infra — aguardando autorização do admin.

---

## Próximas etapas

Acompanhe no [Project Board](https://github.com/users/lsilveira-vtg/projects/1).

- [x] Criar app no LinkedIn Developers e configurar OAuth
- [x] Solicitar acesso à LinkedIn Advertising API
- [x] Estrutura do código e workflows de agendamento
- [x] Estruturar planilha Google Sheets
- [x] Criar Service Account no Google Cloud
- [x] Dashboard Looker/Data Studio
- [x] Bot do Discord — código e app prontos (aguardando admin autorizar no servidor)
- [ ] Aprovação da LinkedIn Advertising API (aguardando LinkedIn)
- [ ] Acesso à conta de anúncios 506583089 (aguardando Plico)
- [ ] Delegação do Gmail para envio de e-mails (aguardando admin Workspace)
- [ ] Definir aprovadores de ações (alinhamento com coordenação)
- [ ] Preencher `CAMPAIGN_CONFIG` com os IDs reais das campanhas
- [ ] Testar com dados reais
- [ ] Documentar e entregar

> GA4 e Search Console entram em fases futuras.

---

## Referências

- [LinkedIn Marketing API Docs](https://learn.microsoft.com/en-us/linkedin/marketing/)
- [Google Sheets API Docs](https://developers.google.com/sheets/api)
- [Gmail API Docs](https://developers.google.com/gmail/api)
- [Looker Studio](https://lookerstudio.google.com/)
