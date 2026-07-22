"""Envio de mensagens para o Discord via Webhook (sem bot / sem host 24/7).

O job de report chama post_report() e a mensagem aparece no canal configurado.
Só age se DISCORD_WEBHOOK_URL estiver definido — caso contrário, não faz nada
(assim o report por e-mail continua funcionando mesmo sem Discord).
"""
import time

import requests

from . import config

LIMIT = 1900  # limite do Discord é 2000; margem para as marcações de bloco


def _chunks(text: str) -> list[str]:
    """Quebra o texto em partes <= LIMIT, sem cortar linhas no meio quando dá."""
    partes: list[str] = []
    for linha in text.split("\n"):
        if partes and len(partes[-1]) + len(linha) + 1 <= LIMIT:
            partes[-1] += "\n" + linha
        else:
            while len(linha) > LIMIT:
                partes.append(linha[:LIMIT])
                linha = linha[LIMIT:]
            partes.append(linha)
    return partes


def post_report(title: str, body: str) -> None:
    """Posta o report no canal do Discord. Nunca interrompe o job em caso de erro."""
    url = config.DISCORD_WEBHOOK_URL
    if not url:
        return
    try:
        # Cabeçalho em destaque, depois o corpo em blocos de código (monoespaçado).
        requests.post(url, json={"content": f"📊 **{title}**"}, timeout=15).raise_for_status()
        for parte in _chunks(body):
            requests.post(url, json={"content": f"```\n{parte}\n```"}, timeout=15).raise_for_status()
            time.sleep(0.5)  # respeita o rate limit do Discord
        print("Report publicado no Discord (webhook).")
    except Exception as exc:
        print(f"  aviso: não publiquei no Discord: {exc}")
