"""Flow 6: Daily Logs Browsing — browser tests.

Covers empty list, entries after recording, detail page, date picker, and invalid date.
"""

from __future__ import annotations


class TestDailyLogs:
    """End-to-end browser tests for daily logs browsing."""

    def test_logs_list_empty(self, page, server_url: str) -> None:
        """Logs list page shows empty state when no logs exist."""
        page.goto(server_url + "/daily/logs")
        assert page.locator(".empty-state").is_visible()
        assert "No daily logs" in page.locator(".empty-state").inner_text()

    def test_logs_list_with_entries(self, page, server_url: str) -> None:
        """After recording a response, logs list shows date links."""
        # Set up profile and answer a question
        page.goto(server_url + "/profile")
        page.locator("button", has_text="Set Up Profile").click()
        page.wait_for_selector("#profile-area textarea#raw_text")
        page.locator("#raw_text").fill("I am a tester.")
        page.locator("button", has_text="Save Profile").click()
        page.wait_for_selector("#profile-area .card")
        # Answer a question
        page.goto(server_url + "/daily")
        page.locator("button", has_text="Generate Question").click()
        page.wait_for_selector("#response-textarea")
        page.locator("#response-textarea").fill("My answer.")
        page.locator("button", has_text="Record Response").click()
        page.wait_for_selector("#response-area .alert-success")
        # Check logs list
        page.goto(server_url + "/daily/logs")
        page.wait_for_selector(".list-item")
        assert page.locator(".list-item").is_visible()

    def test_log_detail_page(self, page, server_url: str) -> None:
        """Clicking a date link shows the log detail page."""
        # Set up and answer a question to create a log
        page.goto(server_url + "/profile")
        page.locator("button", has_text="Set Up Profile").click()
        page.wait_for_selector("#profile-area textarea#raw_text")
        page.locator("#raw_text").fill("I am a tester.")
        page.locator("button", has_text="Save Profile").click()
        page.wait_for_selector("#profile-area .card")
        page.goto(server_url + "/daily")
        page.locator("button", has_text="Generate Question").click()
        page.wait_for_selector("#response-textarea")
        page.locator("#response-textarea").fill("My answer.")
        page.locator("button", has_text="Record Response").click()
        page.wait_for_selector("#response-area .alert-success")
        # Navigate to logs and click a date
        page.goto(server_url + "/daily/logs")
        page.wait_for_selector(".list-item a")
        page.locator(".list-item a").first.click()
        # Should show log detail page with heading
        assert page.locator("h1", has_text="Daily Logs").is_visible()

    def test_invalid_date_page(self, page, server_url: str) -> None:
        """Visiting /daily/logs/invalid-date shows error page."""
        page.goto(server_url + "/daily/logs/not-a-date")
        # Should show error page with "Something went wrong" or "Invalid date"
        body_text = page.locator("body").inner_text()
        assert "went wrong" in body_text.lower() or "invalid" in body_text.lower()
