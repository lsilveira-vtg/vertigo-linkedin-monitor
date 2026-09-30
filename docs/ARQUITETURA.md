# Documentação — Agente de Mídia Paga (LinkedIn Ads)

Documento de referência do projeto. Explica **o que o agente faz** (visão funcional,
para o time de marketing) e **como ele foi construído** (visão técnica, para quem
mexe no código). Mantido junto ao código, em `docs/`.

> Repositório: `git@gitlab.vertigo-devops.com:Silveira/vertigo-linkedin-monitor.git`
> Painel ao vivo: `https://midiapaga-api.vtgdev.net` (acesso restrito a contas `@vertigo.com.br`).

---

# Parte 1 — Visão funcional (para o time)

## 1.1. O que é

Um agente automatizado que **monitora as campanhas de mídia paga da Vertigo no
LinkedIn**, organiza os números, gera análise e recomendações como um analista
sênior, e entrega tudo em três lugares: um **painel web**, **relatórios por e-mail**
(semanal e mensal) e o **Discord**. Ele é **consultivo**: recomenda, mas nunca executa
ações nas campanhas — a decisão é sempre humana.

## 1.2. Vocabulário importante (evita confusão)

- **Grupo de anúncios**: cada linha que o painel mostra. É o que a API do LinkedIn
  chama de "campaign", mas na prática é um *ad group* dentro de uma campanha maior.
- **Campanha**: o âmbito maior que agrupa vários grupos de anúncios (ex.: a campanha
  "Liferay").
- **Leads**: são **formulários do LinkedIn** (Lead Gen Forms). A qualidade real do
  lead (MQL) é confirmada no **CRM** e pode divergir — o agente sempre deixa isso claro.

## 1.3. O que o agente faz

- Acompanha os grupos de anúncios e mostra **investimento, leads, CPL, CPC, CTR,
  impressões e consumo do teto** de verba.
- Gera **análise e recomendações** priorizadas, sempre mirando **leads qualificados
  com CPL baixo** (não só alcance/impressões).
- Mostra **gráficos**: gasto x teto ao longo do mês, CPL por grupo e distribuição do gasto.
- Responde **perguntas ao vivo no chat**, com **memória da conversa** (entende
  "e o outro grupo?", "por quê?").
- Guarda o **histórico das últimas 20 conversas** do chat, compartilhado com o time.
- Permite **consultar meses anteriores** por um seletor de período.
- Gera um **relatório completo em PDF** (ver 1.6).
- Envia **relatórios por e-mail** (acumulado semanal + fechamento mensal) e guarda
  tudo na **planilha**.

## 1.4. O que o agente NÃO faz

- **Não executa ações** no LinkedIn (não pausa, não edita, não cria). Só recomenda.
- **Não fala de outros assuntos**: responde só sobre mídia paga; recusa segurança da
  informação, temas aleatórios e tentativas de "burlar" as instruções.
- **Não substitui o CRM**: "leads" aqui são formulários; o MQL vem do CRM.
- **Não inventa números**: se faltar dado, ele diz que não é possível responder.

## 1.5. Como o agente lê e interpreta os dados

O agente não olha um número "cru" — ele julga cada grupo pelo **papel** dele e por
**benchmarks reais da Vertigo**:

- **Grupos de LEADS**: avaliados pelo **CPL**. Régua calibrada com o histórico real:
  bom até ~R$ 40; CPL médio (blended) da conta ~R$ 104; acima disso, abaixo do
  potencial. O foco é sempre **baixar (ou manter baixo) o CPL de leads qualificados**.
- **Grupos de TRÁFEGO/branding** (ex.: "Artigos - Bruno"): o objetivo é alcance e
  engajamento, **não** leads. São avaliados por **CTR, CPC e impressões** — "0 leads"
  aqui **não** é problema, e eles não entram no cálculo de CPL da conta.
- **Rateio 50/50 da Liferay**: a campanha Liferay é um patrocínio em que a Vertigo
  banca **metade**. Por isso o gasto dos grupos dela entra no painel **já dividido
  por 2** (o custo real da Vertigo), em todos os lugares: KPIs, tabela, gráficos e
  análise.
- **Tetos de verba por mês**: cada mês tem um teto (definido no código). O agente
  mostra o **consumo do teto** e projeta o fim do mês, alertando quando o ritmo pede
  ajuste. Ao recomendar orçamento, ele considera o **total da campanha** e como está
  distribuído entre os grupos.
- **Tom**: técnico, consultivo e **não agressivo**. Aponta problemas com fatos e
  números, sem dramatizar. Prioriza **otimizar antes de pausar** (pausar é último recurso).

## 1.6. Os relatórios e a consistência

O agente produz textos em vários pontos, e todos seguem **uma regra de ouro de
consistência**: cada análise é **gerada uma vez, congelada e lida por todos** — não é
gerada "na hora" por pessoa nem por clique. Assim, se você, a Julia e o Vitor abrirem
o mesmo período, veem **o conteúdo idêntico**.

- **Card do painel** ("Análise & recomendações"): a leitura do dia. Renova **1x por
  dia** no mês corrente; fixa nos meses passados.
- **Relatório em PDF** (botão "Gerar relatório completo"): documento formal em **7
  seções** (contexto, resumo executivo, orçamento e ritmo, recomendações, desempenho
  por grupo, riscos/aprendizados, próximos passos). Tem **dois modos**:
  - **Parcial** (mês em curso): operacional, com **projeção** e ajustes para agir agora.
  - **Fechamento** (mês encerrado): retrospectivo, **sem projeção**, com **aprendizados**
    e recomendações para o próximo ciclo. Um selo no topo indica qual é.
  - Sai sempre do **período selecionado** no painel.
- **E-mail semanal** (segunda): o **acumulado do mês** até ontem.
- **E-mail mensal** (1º dia útil): o **fechamento** do mês anterior — o **mesmo**
  relatório robusto do PDF, gerado e enviado automaticamente.
- **Discord**: reports e comandos (`/report`, `/status`, `/budget`).

### Por que os números e a análise têm ritmos diferentes

- Os **números** (KPIs, tabela) atualizam a cada ~10 minutos — devem estar sempre atuais.
- A **análise escrita** fica congelada (1x/dia no mês corrente) — para todos verem a
  mesma leitura e o texto não "dançar" a cada refresh. Por isso o relatório é sempre
  **datado** ("gerada em ...").

---

# Parte 2 — Visão técnica (para devs)

## 2.1. Arquitetura e fluxo de dados

```
LinkedIn Marketing API
        │  (coleta diária incremental, token com auto-renovação)
        ▼
Google Sheets  ──────────────►  Looker (aba "Campanhas" bruta, legado)
  abas: Campanhas (bruta), 📊 Resumo, uma por campanha,
        Análise do Dia, Histórico Chat, Custos IA
        │
        ▼
API FastAPI (container na EC2, atrás do nginx HTTPS)
   /  /report              -> páginas (painel e relatório)
   /api/dashboard,/analysis,/report-analysis,/ask,/months,/history
        │
        ▼
Painel web (HTML/JS puro)  +  Relatórios por e-mail  +  Bot Discord
```

Fonte da verdade dos **números**: a planilha (alimentada pela coleta) e a própria API
(que reconsulta o LinkedIn e agrega o mês). Fonte da verdade dos **textos**: os
snapshots congelados na aba "Análise do Dia" (ver 2.4).

## 2.2. Estrutura do código

```
src/
  config.py           # variáveis de ambiente (inclui PUBLIC_BASE_URL)
  linkedin_client.py  # LinkedIn API: get_campaigns (grupos), get_campaign_groups
                      #   (campanhas), get_analytics; _request() renova token no 401
  sheets_client.py    # conexão/format. Google Sheets (Service Account)
  sheets_views.py     # aba "📊 Resumo" + uma aba por campanha
  report_builder.py   # collect_campaign_data() agrega o mês; aplica RATEIO 50/50
  budget.py           # tetos por mês (código tem prioridade sobre BUDGET_RULES_JSON)
  analyst.py          # análise — MOTOR DE REGRAS (grátis)
  analyst_ai.py       # análise — camada IA (Claude); relatório robusto; chat
  dashboard_data.py   # monta o JSON do painel; série diária dos gráficos; fallback
  reports.py          # FONTE ÚNICA keyed: card + relatório, geração+persistência
  analysis_store.py   # persiste os snapshots na aba "Análise do Dia"
  chat_history.py     # histórico do chat na aba "Histórico Chat" (por conversa)
  mailer.py           # e-mail (SMTP + Senha de App)
  report_html.py      # HTML dos relatórios de e-mail/vtg-link
  ai_costs.py         # registra custo da IA (aba "Custos IA")
jobs/
  daily_collect.py    # coleta diária + PRÉ-GERA card e relatório do dia
  weekly_report.py    # e-mail semanal (acumulado do mês)
  monthly_report.py   # 1º dia útil: congela o fechamento e envia por e-mail
api/
  main.py             # FastAPI: rotas, auth, caches; delega textos a src/reports.py
  static/index.html   # painel (KPIs, gráficos SVG, chat, histórico, FAQ)
  static/report.html  # relatório em PDF (7 seções, selo parcial/fechamento)
bot/discord_bot.py    # bot do Discord (comandos do time)
.gitlab-ci.yml        # pipeline: coleta, reports, deploy
```

## 2.3. Lógica de análise

Duas implementações que produzem **a mesma estrutura** (`Analysis`):

- **`analyst.py` (motor de regras, custo zero)**: aplica benchmarks (CPL bom ≤ R$ 40,
  blended ~R$ 104; tráfego por CTR/CPC), classifica a saúde (🟢 boa / 🟡 atenção /
  🔴 requer ação) e gera resumo + ações. É o padrão e o **fallback**.
- **`analyst_ai.py` (Claude, opcional — ativa com `ANTHROPIC_API_KEY`)**: análise
  contextual mais rica. `run_analysis()` escolhe IA quando há chave, senão as regras.

Pontos-chave em `analyst_ai.py`:

- **`SYSTEM_PROMPT`**: define o comportamento sênior — princípio do CPL qualificado,
  teto por grupo considerando o total da campanha, tráfego x leads, tom suave,
  terminologia "grupo de anúncios".
- **`build_report_analysis()` + `REPORT_SCHEMA`**: gera o **relatório robusto de 7
  seções**. Recebe `fechado` (bool) e injeta `_MODO_PARCIAL` ou `_MODO_FECHAMENTO`
  no prompt (com/sem projeção, foco em ajuste agora vs aprendizados).
- **`answer_question(history=...)`**: chat multi-turn. Reconstrói a conversa
  (últimas ~8 trocas) para responder follow-ups.
- **`_limpar()`**: sanitizador que **garante as regras de escrita** mesmo se o modelo
  escorregar — remove travessão "—", troca "estourou/estourado" por "acima do teto",
  suaviza termos duros, corrige anglicismos e status em inglês.
- **Trava do chat**: `_bloqueado_por_seguranca()` (regex) recusa temas de
  segurança/hacking **antes** de chamar a IA; `ASK_SYSTEM` restringe o chat só a
  mídia paga e resiste a injeção de instruções.

**Rateio 50/50** (`report_builder.py`): `_fator_rateio()` aplica `0.5` ao gasto dos
grupos cuja **campanha** (campaign group) contém "liferay" no nome; marca `rateio_5050`
no dado. Se a API não retornar o campaign group, o fallback é o valor bruto (seguro).

**Tetos** (`budget.py`): `_DEFAULT_RULES` no código, mesclado de forma que o **código
tem prioridade** sobre `BUDGET_RULES_JSON` (env) nos meses definidos.

## 2.4. Lógica dos relatórios — fonte única de verdade

Toda a geração+persistência de texto vive em **`src/reports.py`**, usada tanto pela
API quanto pelos jobs. Princípio: **"gera 1x, lê muitas"**. A consistência vem de
**congelar a saída** (não de tentar deixar a IA determinística).

- **Chave = cadência de renovação**:
  - Card: `AAAA-MM-DD` (dia) no mês corrente; `M<AAAA-MM>` (fixo) nos meses passados.
  - Relatório: `RPT-<AAAA-MM-DD>` (dia) no corrente; `RPT-M<AAAA-MM>` (fixo/imutável)
    nos passados.
- **Fluxo `load_or_build_*`**: procura em memória → planilha (`analysis_store`) →
  se não existir, **gera (IA), carimba, salva e cacheia**. A primeira leitura do
  período congela; as demais leem o snapshot.
- **Modos**: `fechado = (mês != mês corrente)`. Mês passado gera **fechamento**
  (retrospectivo, sem projeção); corrente gera **parcial**.
- **`to_text(rel)`**: renderiza o relatório de 7 seções em texto plano para o e-mail.
- **API** (`api/main.py`): `_load_analise_ia` e `_load_report_analise` **delegam** a
  `reports.py`. Endpoints: `/api/analysis` (card) e `/api/report-analysis` (relatório),
  ambos aceitam `?month=`.
- **Pré-geração (elimina a "corrida do 1º clique")**:
  - `daily_collect.py`: após a coleta, chama `load_or_build_card()` e
    `load_or_build_report()` → o dia já nasce congelado.
  - `monthly_report.py`: no 1º dia útil, `load_or_build_report(month=mês anterior)`
    congela o **fechamento** e usa o **mesmo** documento no e-mail (`to_text`), com
    link para `/report?month=`. `FORCE_MONTHLY=1` permite teste manual fora do dia útil.

## 2.5. Caches e estabilidade

- `_data_cache` (API): números por mês, TTL 10 min.
- Snapshots de texto: card por dia / relatório por dia (corrente) ou fixos (passados),
  em memória + planilha. Sobrevivem a restart (a planilha é durável).
- `chat_history`: persistido na aba "Histórico Chat" (cache de leitura ~60 s).
- `index.html` servido com `Cache-Control: no-cache` (o browser revalida via ETag →
  toda atualização aparece na hora).

## 2.6. Agendamentos (GitLab CI)

`.gitlab-ci.yml`, timezone America/Sao_Paulo. Jobs escolhidos pela variável
`SCHEDULE_JOB`:

| Job | Schedule | Usa IA? |
|---|---|---|
| `coleta_diaria` | 08h seg–sex | pré-gera card+relatório (sim, ~2 chamadas) |
| `report_semanal` | segunda 08h | sim |
| `report_mensal` | 1º dia útil | sim (congela o fechamento) |

A máquina (runner/EC2) fica **desligada fora do horário comercial e nos fins de
semana**. Por isso `daily_collect.py` é **incremental** (coleta do último dia salvo
até ontem, recupera fim de semana sem duplicar).

## 2.7. Deploy

Job `deploy-bot` roda a **cada push na `main`**: SSH na EC2 → `git pull --ff-only` +
`docker compose up -d --build --wait`. O frontend é servido por **volume**
(`./api/static`), então mudanças de HTML/JS entram no `git pull`; mudanças de Python
entram no rebuild do container. Se a máquina estiver desligada no push, o deploy falha
→ reexecutar o pipeline quando ligar.

## 2.8. Segurança

- **Acesso restrito a `@vertigo.com.br`** em duas camadas: backend (`api/main.py`
  valida o ID token do Google e o domínio, 403 caso contrário — é o portão real) e
  frontend (recusa e-mail pessoal já no login).
- **Trava do chat**: só mídia paga; recusa segurança/hacking e injeção de instruções.
- **Segredos**: nunca no código nem no chat — só em GitLab CI/CD Variables (e no `.env`
  da VM). `.env` e `service_account.json` estão no `.gitignore`.

## 2.9. Variáveis de ambiente principais

`LINKEDIN_*` (client/secret/refresh token, account id), `GOOGLE_SERVICE_ACCOUNT_JSON`,
`GOOGLE_SHEET_ID`, `GMAIL_SENDER`, `GMAIL_APP_PASSWORD`, `REPORT_RECIPIENTS`,
`ANTHROPIC_API_KEY` (ativa a IA), `GOOGLE_OAUTH_CLIENT_ID`, `ALLOWED_EMAIL_DOMAIN`,
`PUBLIC_BASE_URL`, `BUDGET_RULES_JSON`, `CAMPAIGN_CONFIG_JSON`, `DISCORD_*`.

## 2.10. Custos de IA

Modelo Opus (`config.ANALYST_MODEL`). Custo histórico ~US$ 1–2/mês (coleta diária
pré-gera os textos + reports). Cada pergunta no chat ~US$ 0,05–0,10. Registrado na aba
"Custos IA" (horário de Brasília). Opção de corte: apontar o chat para um modelo mais
barato mantendo Opus na análise/reports.

---

*Para o histórico detalhado de decisões e datas, ver o `README.md` (log de progresso)
e as mensagens de commit.*
