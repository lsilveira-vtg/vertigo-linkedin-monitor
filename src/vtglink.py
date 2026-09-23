"""Publicação de páginas no vtg-link (API de sistemas).

Segue o contrato v1 (documento api-sistemas-guia-integracao.md):
- autentica com chave de API (Bearer), lida de VTG_LINK_KEY (nunca no código);
- base URL de VTG_LINK_BASE (dev: https://vtglink.demo.vtgdev.net);
- publica via multipart/form-data (campo `file`), compartilha via JSON;
- normaliza os 4 envelopes de erro; trata 409 nos dois sentidos (§14.4);
- usa sempre a `url` devolvida pela resposta — nunca uma URL fixa (§11).

A chave NUNCA é impressa; para rastreio, só o prefixo de 16 caracteres.
"""
import os
import time

import requests

BASE = os.getenv("VTG_LINK_BASE", "https://vtglink.demo.vtgdev.net").rstrip("/")


def _key() -> str:
    k = os.getenv("VTG_LINK_KEY", "")
    if not k:
        raise RuntimeError("VTG_LINK_KEY não definido no ambiente.")
    return k


def _auth() -> dict:
    return {"Authorization": f"Bearer {_key()}"}


class VtgLinkError(Exception):
    def __init__(self, status: int, corpo: dict):
        self.status, self.corpo = status, corpo
        super().__init__(f"vtg-link {status}: {self.mensagem}")

    @property
    def transitorio(self) -> bool:
        return self.status == 429 or self.status >= 500

    @property
    def configuracao(self) -> bool:
        return self.status in (401, 403, 501)

    @property
    def mensagem(self) -> str:
        # Normaliza os 4 envelopes de erro (§14.1).
        if "error" in self.corpo:                       # 429
            return str(self.corpo["error"])
        d = self.corpo.get("detail")
        if isinstance(d, dict):                         # 409 duplicata
            return str(d.get("message", d))
        if isinstance(d, list):                         # 422 validação
            return "; ".join(f"{'.'.join(map(str, e.get('loc', [])))}: {e.get('msg')}" for e in d)
        return str(d or self.corpo)


def _checar(r: requests.Response) -> dict:
    if r.ok:
        return r.json() if r.content else {}
    try:
        corpo = r.json()
    except ValueError:
        corpo = {"detail": r.text}
    raise VtgLinkError(r.status_code, corpo)


def _com_retry(fn, tentativas: int = 3):
    """Repete só falhas transitórias (429/5xx) com backoff + jitter."""
    import random
    for i in range(tentativas):
        try:
            return fn()
        except VtgLinkError as e:
            if not e.transitorio or i == tentativas - 1:
                raise
            time.sleep(2 ** i + random.random())


def ensure_full_html(html: str, title: str = "Página") -> str:
    """Garante um documento HTML completo (o vtg-link exige <html> e <body>)."""
    low = html.lower()
    if "<html" in low and "<body" in low:
        return html
    return (f"<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{title}</title></head><body>{html}</body></html>")


def publicar(html: str, filename: str, titulo: str, *, overwrite: bool = True,
             password: str | None = None, visibility: str | None = None) -> dict:
    """Publica um HTML e devolve {id, url, ...}. Usa a url da resposta (§11)."""
    data = {"title": titulo}
    if overwrite:
        data["overwrite"] = "true"
    if password:
        data["password"] = password
    if visibility:
        data["visibility"] = visibility

    def _do():
        r = requests.post(
            f"{BASE}/api/v1/pages",
            headers=_auth(),
            files={"file": (filename, ensure_full_html(html, titulo).encode("utf-8"), "text/html")},
            data=data,
            timeout=60,
        )
        return _checar(r)

    try:
        return _com_retry(_do)
    except VtgLinkError as e:
        # 409 = já existe página com esse nome; republica com overwrite (§14.4).
        if e.status == 409 and not overwrite:
            return publicar(html, filename, titulo, overwrite=True,
                            password=password, visibility=visibility)
        raise


def compartilhar(page_id: str, email: str) -> None:
    """Compartilha com um e-mail da organização. 409 = já tem acesso (sucesso, §14.4)."""
    r = requests.post(
        f"{BASE}/api/v1/pages/{page_id}/shares",
        headers=_auth(), json={"email": email}, timeout=30,
    )
    if r.status_code == 409:
        return
    _checar(r)


def publicar_e_compartilhar(html: str, filename: str, titulo: str,
                            destinatarios: list[str]) -> dict:
    """Publica e restringe à lista. Falha no compartilhamento = falha da operação (§14.5)."""
    pagina = publicar(html, filename, titulo)
    faltaram = []
    for email in destinatarios:
        try:
            _com_retry(lambda: compartilhar(pagina["id"], email))
        except VtgLinkError as exc:
            faltaram.append(f"{email}: {exc.mensagem}")
    if faltaram:
        raise RuntimeError(
            f"Página {pagina['id']} publicada, mas sem acesso para: {faltaram}. "
            f"URL: {pagina.get('url')}"
        )
    print(f"vtg-link: publicado {pagina.get('url')} · compartilhado com {len(destinatarios)}")
    return pagina
