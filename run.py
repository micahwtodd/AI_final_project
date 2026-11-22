"""Start Risk Desk: python run.py  ->  http://localhost:8000"""

from __future__ import annotations

import threading
import webbrowser

import uvicorn

from backend.env import load_env

HOST, PORT = "127.0.0.1", 8000


def main() -> None:
    status = load_env()
    if status.key_found:
        print(f"{status.key_name} found ({status.key_source}); using {status.provider}.")
    else:
        print("No PORTKEY_API_KEY or OPENAI_API_KEY found. The game runs, but the AI colleagues are offline.")
    url = f"http://localhost:{PORT}"
    print(f"Opening {url}  (Ctrl+C to stop)")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("backend.main:app", host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
