"""Inicializa o Cognix numa porta disponivel e abre o navegador ao responder."""

from __future__ import annotations

import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
START_PORT = 8000
END_PORT = 8100


def choose_port(start: int = START_PORT, end: int = END_PORT) -> int:
    """Verifica a disponibilidade com bind real, nao com connect_ex."""
    if not (0 < start <= end <= 65535):
        raise ValueError("Intervalo de portas invalido")
    last_error: OSError | None = None
    for port in range(start, end + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind((HOST, port))
            return port
        except OSError as exc:
            last_error = exc
    raise RuntimeError(
        f"Nenhuma porta disponivel entre {start} e {end}."
    ) from last_error


def open_browser_when_ready(url: str) -> None:
    """Abre a pagina somente apos o servidor responder com sucesso."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(100):
        try:
            with opener.open(url, timeout=1.5) as response:
                if response.status == 200:
                    if not webbrowser.open(url, new=2):
                        print(f"Abra manualmente no navegador: {url}", flush=True)
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    print(f"O navegador nao abriu automaticamente. Acesse: {url}", flush=True)


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import uvicorn

    try:
        port = choose_port()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERRO AO VERIFICAR AS PORTAS: {exc}", file=sys.stderr, flush=True)
        return 1

    url = f"http://{HOST}:{port}/"
    print(f"Endereco do Cognix: {url}", flush=True)
    if port != START_PORT:
        print(f"AVISO: porta 8000 indisponivel; usando {port}.", flush=True)
    threading.Thread(
        target=open_browser_when_ready, args=(url,), daemon=True
    ).start()
    uvicorn.run("backend.main:app", host=HOST, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
