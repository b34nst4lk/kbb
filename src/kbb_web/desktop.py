"""Desktop wrapper using pywebview.

Opens a native window pointing at the local FastAPI server.
Usage: kbb-desktop
"""

from __future__ import annotations

import threading
import time
import webview

from kbb_web.app import create_app
from kbb_web.config import load_config


def _start_server(config):
    """Run uvicorn in a daemon thread."""
    import uvicorn

    app = create_app()
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="info" if config.debug else "warning",
    )


def main():
    config = load_config()

    # Start server in background thread
    server_thread = threading.Thread(
        target=_start_server,
        args=(config,),
        daemon=True,
    )
    server_thread.start()

    # Wait for server to be ready
    url = f"http://{config.host}:{config.port}"
    for _ in range(50):  # wait up to 5 seconds
        try:
            import urllib.request
            urllib.request.urlopen(url)
            break
        except Exception:
            time.sleep(0.1)

    # Open native window
    webview.create_window(
        "Knowledge Base Builder",
        url,
        width=1200,
        height=800,
        min_size=(800, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()