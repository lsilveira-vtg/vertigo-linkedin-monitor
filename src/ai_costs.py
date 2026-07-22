"""Contador de custo da camada de IA (Claude API).

O custo é calculado a partir dos tokens que a própria resposta retorna — não
gera nenhuma chamada extra à API. Cada análise é registrada na aba "Custos IA"
da planilha (a memória do gasto entre execuções, já que o GitLab CI é efêmero).
O rodapé mostra: custo da análise + acumulado do mês vs orçamento de referência.
"""
from datetime import date, timezone, datetime

from . import config, sheets_client

TAB = "Custos IA"
HEADER = ["Data", "Mês", "Modelo", "Tokens entrada", "Tokens saída", "Custo (US$)"]

# Preço por 1M de tokens (Claude Opus 4.8). Ajustar se mudar de modelo.
PRICE_PER_MTOK = {
    "input": 5.0,
    "output": 25.0,
    "cache_read": 0.5,
    "cache_write": 6.25,
}


def cost_from_usage(usage) -> float:
    """Custo em USD a partir do objeto usage da resposta da API."""
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return (
        inp * PRICE_PER_MTOK["input"]
        + out * PRICE_PER_MTOK["output"]
        + cache_read * PRICE_PER_MTOK["cache_read"]
        + cache_write * PRICE_PER_MTOK["cache_write"]
    ) / 1_000_000


def _month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def log_and_summarize(usage, model: str) -> str:
    """Registra o custo na planilha e devolve o rodapé formatado.

    Nunca interrompe a análise: se a planilha falhar, devolve só o custo da chamada.
    """
    custo = cost_from_usage(usage)
    hoje = date.today()
    mes = _month_key(hoje)
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0

    acumulado = custo
    try:
        sheet = sheets_client.open_sheet()
        try:
            ws = sheet.worksheet(TAB)
        except Exception:
            ws = sheet.add_worksheet(title=TAB, rows=1000, cols=len(HEADER))
            ws.update(values=[HEADER], range_name="A1")
        # Soma o que já foi gasto neste mês antes de registrar a chamada atual.
        # Aceita vírgula decimal (formato pt-BR gravado pelo Sheets).
        def _num(s: str) -> float:
            try:
                return float(str(s).replace(".", "").replace(",", ".")) if "," in str(s) else float(s)
            except ValueError:
                return 0.0
        registros = ws.get_all_values()[1:]
        gasto_mes_anterior = sum(
            _num(r[5]) for r in registros
            if len(r) > 5 and r[1] == mes and r[5]
        )
        acumulado = gasto_mes_anterior + custo
        agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        ws.append_row([agora, mes, model, inp, out, round(custo, 4)],
                      value_input_option="USER_ENTERED")
    except Exception as exc:
        print(f"  aviso: não registrei o custo na planilha: {exc}")

    orc = config.ANTHROPIC_MONTHLY_BUDGET_USD
    if orc > 0:
        pct = acumulado / orc * 100
        restante = max(0.0, orc - acumulado)
        return (f"💰 Custo desta análise: US$ {custo:.3f} · "
                f"mês: US$ {acumulado:.2f} / US$ {orc:.2f} ({pct:.0f}%) · "
                f"resta US$ {restante:.2f}")
    return f"💰 Custo desta análise: US$ {custo:.3f} · acumulado no mês: US$ {acumulado:.2f}"
