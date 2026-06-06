"""Test fixtures for the web adapter.

Provides a TestClient with the engine backed by MockProvider.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from kbb.engine import KBPEngine
from kbb.llm.base import LLMClient
from kbb.models import KBBConfig
from kbb_web.app import create_app
from kbb_web.config import WebConfig
from tests.helpers import MockProvider


@pytest.fixture
def web_app(tmp_path: Path):
    """Provide a FastAPI app with mock-engine for testing."""
    config = WebConfig(data_dir=tmp_path, llm_api_key="test")
    app = create_app()

    # Override the engine with a mock-backed one
    engine = KBPEngine(config.to_kbb_config())
    engine._llm = LLMClient(MockProvider())
    app.state.engine = engine
    app.state.web_config = config

    return app


@pytest.fixture
def client(web_app):
    """Provide a synchronous test client (Starlette TestClient)."""
    return TestClient(web_app)