"""Teste de conexão com o vtg-link.

Publica uma página simples e compartilha com um e-mail, para validar que a
chave (VTG_LINK_KEY) e o ambiente (VTG_LINK_BASE) estão corretos. Não altera
nada da operação normal do agente.
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src import vtglink

DESTINO = "lsilveira@vertigo.com.br"

HTML = f"""
<h1 style="font-family:system-ui">Agente de Mídia Paga — teste do vtg-link</h1>
<p style="font-family:system-ui;color:#444">
  Se você está vendo esta página, a integração do agente com o vtg-link funciona.
</p>
<p style="font-family:system-ui;color:#888;font-size:13px">
  Publicado em {datetime.now().strftime('%d/%m/%Y %H:%M')} (BRT) · ambiente de testes.
</p>
"""


def main() -> None:
    print(f"Ambiente (VTG_LINK_BASE): {vtglink.BASE}")
    pagina = vtglink.publicar_e_compartilhar(
        HTML, "teste-agente.html", "Teste vtg-link — Agente Mídia Paga", [DESTINO]
    )
    print("URL:", pagina.get("url"))
    print(f"Abra a URL logado com a conta {DESTINO} para ver a página.")


if __name__ == "__main__":
    main()
