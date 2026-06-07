"""Browser test fixtures — Playwright + FastAPI server with mock providers.

Starts the web app on a random port with mock-backed engine so browser tests
exercise real HTML, HTMX, and JavaScript without calling real LLM or
transcription APIs.
"""

from __future__ import annotations

import threading
import time

import pytest
import uvicorn

from kbb.engine import KBPEngine
from kbb.llm.base import LLMClient
from kbb.transcribe import TranscriptionClient
from kbb_web.app import create_app
from kbb_web.config import WebConfig
from tests.helpers import MockProvider, MockTranscriptionProvider


@pytest.fixture(scope="session")
def server_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Start the FastAPI app on a random port with mock providers.

    Yields the base URL (e.g. "http://localhost:54321") for the session.
    The server is shut down after all browser tests complete.
    """
    data_dir = tmp_path_factory.mktemp("kbb_browser_data")
    config = WebConfig(data_dir=data_dir, llm_api_key="test")

    app = create_app()

    # Wire mock LLM provider into the engine
    mock_llm = MockProvider()
    engine = KBPEngine(config.to_kbb_config())
    engine._llm = LLMClient(mock_llm)
    app.state.engine = engine
    app.state.web_config = config

    # Wire mock transcription provider into the engine
    mock_transcription = MockTranscriptionProvider(text="transcribed text from mock")
    engine._transcriber = TranscriptionClient(mock_transcription)

    # Find a free port by binding to port 0
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for the server to be ready
    base_url = f"http://127.0.0.1:{port}"
    import httpx

    for _ in range(50):
        try:
            resp = httpx.get(f"{base_url}/", timeout=1)
            if resp.status_code < 500:
                break
        except httpx.ConnectError:
            pass
        time.sleep(0.1)

    yield base_url

    # Shut down the server
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def page(browser, server_url):
    """Provide a Playwright page with the app loaded at the root URL."""
    p = browser.new_page()
    p.goto(server_url)
    yield p
    p.close()


@pytest.fixture
def mock_llm(server_url) -> MockProvider:
    """Provide access to the session-scoped MockProvider for assertion and configuration.

    Because the server uses a session-scoped engine, the MockProvider is shared
    across tests. Callers should check or clear _calls as needed.
    """
    # Access the engine from the running app — we can reach it via the app module
    from kbb_web.app import app

    return app.state.engine._llm._provider


@pytest.fixture
def mock_transcription(server_url) -> MockTranscriptionProvider:
    """Provide access to the session-scoped MockTranscriptionProvider."""
    from kbb_web.app import app

    return app.state.engine._transcriber._provider
