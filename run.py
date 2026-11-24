"""Start Surplus or Bust: python run.py  ->  http://localhost:8000

If port 8000 is busy, the next free port from 8001 to 8010 is used. To choose a port yourself:
    python run.py --port 8001        (or set the PORT environment variable)
"""

from __future__ import annotations

import argparse
import os
import socket
import threading
import webbrowser

import uvicorn

from backend.env import fallback_config, load_env

HOST, DEFAULT_PORT = "127.0.0.1", 8000


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, port))
            return True
        except OSError:
            return False


def pick_port(requested: int | None) -> int:
    if requested:
        return requested
    for port in range(DEFAULT_PORT, DEFAULT_PORT + 11):
        if port_free(port):
            return port
    raise SystemExit("Ports 8000 to 8010 are all busy. Choose one with: python run.py --port <number>")


def main() -> None:
    ap = argparse.ArgumentParser(description="Start Surplus or Bust")
    ap.add_argument("--port", type=int, default=int(os.environ["PORT"]) if os.environ.get("PORT", "").isdigit() else None)
    port = pick_port(ap.parse_args().port)

    status = load_env()
    if status.key_found:
        backup = ", with OpenAI as the fallback" if fallback_config() else ""
        print(f"{status.key_name} found ({status.key_source}); using {status.provider}{backup}.")
    else:
        print("No PORTKEY_API_KEY or OPENAI_API_KEY found. The game runs, but the AI colleagues are offline.")
    if port != DEFAULT_PORT:
        print(f"Port {DEFAULT_PORT} is busy or not chosen, so using port {port}.")
    url = f"http://localhost:{port}"
    print(f"Opening {url}  (Ctrl+C to stop)", flush=True)
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("backend.main:app", host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
