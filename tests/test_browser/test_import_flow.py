"""Flow 4: Knowledge Import — browser tests.

Covers import form rendering and submit success.
Error handling for import is covered by HTTP-level tests in test_partials.py.
"""

from __future__ import annotations


class TestKnowledgeImport:
    """End-to-end browser tests for the knowledge import flow."""

    def test_import_form_renders(self, page, server_url: str) -> None:
        """Import form shows title, topic select, content textarea, and submit button."""
        page.goto(server_url + "/knowledge/import")
        assert page.locator("#title").is_visible()
        assert page.locator("#topic").is_visible()
        assert page.locator("#content").is_visible()
        assert page.locator("button", has_text="Import").is_visible()

    def test_import_submit_success(self, page, server_url: str) -> None:
        """Filling all fields and clicking Import shows knowledge card."""
        page.goto(server_url + "/knowledge/import")
        page.locator("#title").fill("My Testing Philosophy")
        page.locator("#topic").select_option("skill")
        page.locator("#content").fill("I believe pytest is the best testing framework.")
        page.locator("button", has_text="Import").click()
        # Wait for result to appear
        page.wait_for_selector("#import-result .list-item")
        # Should show the knowledge card with title
        assert page.locator("#import-result", has_text="My Testing Philosophy").is_visible()
