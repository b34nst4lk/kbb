"""Browser test fixtures — Playwright + FastAPI server with mock providers.

Starts the web app on a random port with mock-backed engine so browser tests
exercise real HTML, HTMX, and JavaScript without calling real LLM or
transcription APIs.
"""

from __future__ import annotations

import shutil
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from kbb.engine import KBPEngine
from kbb.llm.base import LLMClient
from kbb.transcribe import TranscriptionClient
from kbb_web.app import create_app
from kbb_web.config import WebConfig
from tests.helpers import MockProvider, MockTranscriptionProvider

# Module-level references so fixtures can access the running app's state.
_test_app = None
_mock_llm = None
_mock_transcription = None


@pytest.fixture(scope="session")
def server_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Start the FastAPI app on a random port with mock providers.

    Yields the base URL (e.g. "http://localhost:54321") for the session.
    The server is shut down after all browser tests complete.
    """
    global _test_app, _mock_llm, _mock_transcription  # noqa: PLW0603
    data_dir = tmp_path_factory.mktemp("kbb_browser_data")
    config = WebConfig(data_dir=data_dir, llm_api_key="test")

    app = create_app()

    # Create mock-backed engine BEFORE server starts
    mock_llm = MockProvider()
    mock_transcription = MockTranscriptionProvider(text="transcribed text from mock")
    engine = KBPEngine(config.to_kbb_config())
    engine._llm = LLMClient(mock_llm)
    engine._transcriber = TranscriptionClient(mock_transcription)

    # Set app state before lifespan runs — the lifespan handler will
    # overwrite engine and web_config, so we need to re-inject after startup.
    app.state.engine = engine
    app.state.web_config = config

    # Find a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for the server to be ready
    base_url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            resp = httpx.get(f"{base_url}/", timeout=1)
            if resp.status_code < 500:
                break
        except httpx.ConnectError:
            pass
        time.sleep(0.1)

    # Re-inject mock-backed engine (lifespan may have replaced it)
    app.state.engine = engine
    app.state.web_config = config

    _test_app = app
    _mock_llm = mock_llm
    _mock_transcription = mock_transcription

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
    """Provide access to the session-scoped MockProvider for assertion and configuration."""
    assert _mock_llm is not None, "Server fixture must run before mock_llm"
    return _mock_llm


@pytest.fixture
def mock_transcription(server_url) -> MockTranscriptionProvider:
    """Provide access to the session-scoped MockTranscriptionProvider."""
    assert _mock_transcription is not None, "Server fixture must run before mock_transcription"
    return _mock_transcription


@pytest.fixture(autouse=True)
def _reset_engine_state(server_url):
    """Reset engine storage between tests so state doesn't leak.

    Clears profile, knowledge entries, daily logs, and pending questions
    from the temp data dir. Also resets mock provider call history.
    """
    assert _test_app is not None
    engine: KBPEngine = _test_app.state.engine
    data_dir: Path = engine._config.data_dir

    # Clear all persisted data by deleting files/subdirs in the data dir
    for item in data_dir.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)

    # Re-create directory structure so the store doesn't break
    engine._store._ensure_dirs()

    # Reset mock provider call history, responses, and exception overrides
    _mock_llm._calls.clear()
    _mock_llm._responses.clear()
    _mock_llm._raise_on.clear()

    yield

    # No teardown needed — next test's reset will clean up
