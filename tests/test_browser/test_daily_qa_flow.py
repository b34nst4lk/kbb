"""Flow 2: Daily Question & Answer — browser tests.

Covers question generation, response submission, auto-focus after swap,
and error states.
"""

from __future__ import annotations


class TestDailyQA:
    """End-to-end browser tests for the daily Q&A flow."""

    def _setup_profile(self, page, server_url: str) -> None:
        """Helper: set up a profile so question generation works."""
        page.goto(server_url + "/profile")
        page.locator("button", has_text="Set Up Profile").click()
        page.wait_for_selector("#profile-area textarea#raw_text")
        page.locator("#raw_text").fill("I am a software engineer interested in testing.")
        page.locator("button", has_text="Save Profile").click()
        page.wait_for_selector(".alert-success")

    def test_daily_page_no_pending_question(self, page, server_url: str) -> None:
        """Daily page shows 'Generate Question' button when no pending question."""
        page.goto(server_url + "/daily")
        btn = page.locator("button", has_text="Generate Question")
        assert btn.is_visible()
        assert page.locator("#question-area").is_visible()

    def test_generate_question(self, page, server_url: str) -> None:
        """Clicking 'Generate Question' swaps question card into #question-area."""
        self._setup_profile(page, server_url)
        page.goto(server_url + "/daily")
        page.locator("button", has_text="Generate Question").click()
        # Wait for the question card to appear
        page.wait_for_selector("#question-area .card")
        assert page.locator("#question-area .card-header", has_text="Today's Question").is_visible()

    def test_question_card_shows_fields(self, page, server_url: str) -> None:
        """Question card displays question text, topic, and response textarea."""
        self._setup_profile(page, server_url)
        page.goto(server_url + "/daily")
        page.locator("button", has_text="Generate Question").click()
        page.wait_for_selector("#response-textarea")
        # Should have topic and rationale meta
        assert page.locator("#question-area .list-item-meta").is_visible()
        # Should have response textarea
        assert page.locator("#response-textarea").is_visible()

    def test_submit_response(self, page, server_url: str) -> None:
        """Filling response and clicking 'Record Response' shows success result."""
        self._setup_profile(page, server_url)
        page.goto(server_url + "/daily")
        page.locator("button", has_text="Generate Question").click()
        page.wait_for_selector("#response-textarea")
        page.locator("#response-textarea").fill("I prefer pytest for its Pythonic approach.")
        page.locator("button", has_text="Record Response").click()
        # Wait for response result
        page.wait_for_selector("#response-area .alert-success")
        assert page.locator(".alert-success", has_text="Recorded").is_visible()
        # Should show "Recorded Knowledge" card
        assert page.locator("#response-area .card", has_text="Recorded Knowledge").is_visible()

    def test_response_result_links(self, page, server_url: str) -> None:
        """Success result shows links to answer another question and view logs."""
        self._setup_profile(page, server_url)
        page.goto(server_url + "/daily")
        page.locator("button", has_text="Generate Question").click()
        page.wait_for_selector("#response-textarea")
        page.locator("#response-textarea").fill("My testing approach.")
        page.locator("button", has_text="Record Response").click()
        page.wait_for_selector("#response-area .alert-success")
        # Should have "Answer Another Question" link
        assert page.locator("a[href='/daily']", has_text="Answer Another Question").is_visible()
        # Should have "View Today's Logs" link
        assert page.locator("a[href*='/daily/logs/']", has_text="View Today's Logs").is_visible()

    def test_auto_focus_after_swap(self, page, server_url: str) -> None:
        """After question card swaps in, the response textarea receives focus."""
        self._setup_profile(page, server_url)
        page.goto(server_url + "/daily")
        page.locator("button", has_text="Generate Question").click()
        page.wait_for_selector("#response-textarea")
        # The textarea should be focused (kbb.js auto-focuses after HTMX swap)
        assert page.locator("#response-textarea").evaluate("el => el === document.activeElement")

    def test_generate_question_no_profile(self, page, server_url: str) -> None:
        """When no profile exists, generating a question shows an error alert."""
        page.goto(server_url + "/daily")
        page.locator("button", has_text="Generate Question").click()
        # Should show an error alert (no profile)
        page.wait_for_selector("#question-area .alert-error")
        assert page.locator("#question-area .alert-error").is_visible()

    def test_response_submission_error(self, page, server_url: str, mock_llm) -> None:
        """When LLM raises on response recording, an error alert appears."""
        self._setup_profile(page, server_url)
        page.goto(server_url + "/daily")
        page.locator("button", has_text="Generate Question").click()
        page.wait_for_selector("#response-textarea")
        # Make the mock raise an exception when recording a response
        mock_llm._raise_on["knowledge recorder"] = RuntimeError("LLM unavailable")
        page.locator("#response-textarea").fill("My response.")
        page.locator("button", has_text="Record Response").click()
        # Should show an error in the response area
        page.wait_for_selector("#response-area .alert-error")
        assert page.locator("#response-area .alert-error").is_visible()
