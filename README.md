# 📊 Vertigo LinkedIn Monitor

Agente automatizado de monitoramento de mídia paga no LinkedIn da Vertigo. Coleta dados de campanhas, analisa performance, recomenda e executa pausas mediante confirmação, e envia report semanal por e-mail.

---

## Pipeline

```
LinkedIn Advertising API + GA4 API
            ↓
    Coleta de dados (Python)
            ↓
    Processamento e agregação
            ↓
    Google Sheets (dashboard)
            ↓
    Análise e recomendações de pausas
            ↓
    Ação (pausar campanha) + Report semanal por e-mail
```

---

## Funcionalidades

- Coleta diária de métricas por campanha (invest, leads, CPL, CTR, impressões, engajamento)
- Dados de site via GA4 (sessões, eventos, top páginas)
- Comparativo automático com período anterior (semana vs semana, MTD)
- Recomendação de pausas com justificativa baseada em thresholds de CPL e CTR
- Execução de pausa mediante confirmação do usuário
- Report semanal por e-mail no formato padronizado da Vertigo

---

## Stack

| Ferramenta | Uso |
|---|---|
| Python | Script principal de coleta e processamento |
| LinkedIn Advertising API | Dados de campanhas, anúncios, gasto e leads |
| Google Analytics 4 API | Sessões, eventos e páginas do site |
| Google Sheets API | Armazenamento e dashboard dos dados |
| Gmail API | Envio do report semanal |
| GitHub Actions | Agendamento automático diário |

---

## Log de progresso

### ✅ Etapa 1 — App criado no LinkedIn Developers *(08/06/2026)*
Criado o app **"Monitoramento de Mídia Paga Vertigo"** no LinkedIn Developers com Client ID `78llookt0ujwzb`. O app foi vinculado à página da Vertigo e a company association foi verificada, habilitando o acesso à Advertising API.

### ✅ Etapa 2 — Solicitação de acesso à Advertising API *(08/06/2026)*
Formulário de acesso à LinkedIn Advertising API (Development Tier) submetido. Caso de uso declarado: monitoramento interno de campanhas com exportação para Google Sheets. Use cases selecionados: Campaign Management e Reporting & ROI. Aguardando aprovação do LinkedIn (prazo estimado: 2–5 dias úteis).

### ⏳ Etapa 3 — Aguardando aprovação da LinkedIn API
Sem essa aprovação as etapas de desenvolvimento com dados reais ficam bloqueadas. Em paralelo, as etapas 4 e 5 podem ser executadas.

### 🔄 Etapa 4 — Estrutura da planilha Google Sheets *(próxima)*
Montar as abas e colunas da planilha que o agente vai preencher automaticamente. Não depende da aprovação da API.

---

## Próximas etapas

- [x] Criar app no LinkedIn Developers e configurar OAuth
- [x] Solicitar acesso à LinkedIn Advertising API
- [ ] Estruturar planilha Google Sheets
- [ ] Configurar acesso à GA4 API
- [ ] Criar Service Account no Google Cloud
- [ ] Desenvolver script de coleta (LinkedIn + GA4 → Python)
- [ ] Desenvolver script de exportação (Python → Sheets)
- [ ] Implementar lógica de recomendação de pausas
- [ ] Desenvolver gerador do report semanal por e-mail
- [ ] Testar com dados reais
- [ ] Configurar agendamento automático (GitHub Actions)
- [ ] Documentar e entregar

---

## Configuração

> Instruções de instalação e variáveis de ambiente serão adicionadas conforme o desenvolvimento avança.

---

## Referências

- [LinkedIn Marketing API Docs](https://learn.microsoft.com/en-us/linkedin/marketing/)
- [Google Analytics Data API](https://developers.google.com/analytics/devguides/reporting/data/v1)
- [Google Sheets API Docs](https://developers.google.com/sheets/api)
- [Gmail API Docs](https://developers.google.com/gmail/api)
