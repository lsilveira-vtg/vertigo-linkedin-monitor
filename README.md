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

---

## Próximas etapas

Acompanhe no [Project Board](https://github.com/users/lsilveira-vtg/projects/1).

- [x] Criar app no LinkedIn Developers e configurar OAuth
- [x] Solicitar acesso à LinkedIn Advertising API
- [x] Estrutura do código e workflows de agendamento
- [ ] Estruturar planilha Google Sheets
- [ ] Criar Service Account no Google Cloud
- [ ] Dashboard Looker Studio
- [ ] Bot do Discord (comandos e aprovações)
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
