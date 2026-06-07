"""Smoke test: verify Playwright browser infrastructure starts and connects."""

from __future__ import annotations


def test_server_fixture_starts(server_url: str) -> None:
    """Server fixture returns a valid http://127.0.0.1:{port} URL."""
    assert server_url.startswith("http://127.0.0.1:")
    assert len(server_url.split(":")) == 3


def test_page_fixture_navigates(page, server_url: str) -> None:
    """Page fixture loads the app's root URL and shows content."""
    # The page fixture navigates to server_url automatically
    assert page.url.startswith(server_url)
    # Dashboard should have some content (even if empty state)
    body_text = page.inner_text("body")
    assert len(body_text) > 0


def test_dashboard_no_profile(page) -> None:
    """Dashboard shows empty state when no profile exists."""
    heading = page.locator("h1, h2, h3").first
    assert heading.is_visible()
