"""Flow 1: First-Time Setup — browser tests.

Covers the journey from empty dashboard to saved profile, including
error recovery and profile editor interactions.
"""

from __future__ import annotations


class TestFirstTimeSetup:
    """End-to-end browser tests for the first-time profile setup flow."""

    def test_dashboard_no_profile(self, page, server_url: str) -> None:
        """Dashboard shows 'Get Started' card when no profile exists."""
        page.goto(server_url + "/")
        card = page.locator(".card", has_text="Get Started")
        assert card.is_visible()
        link = card.locator("a[href='/profile']")
        assert link.is_visible()

    def test_profile_page_empty_state(self, page, server_url: str) -> None:
        """Profile page shows empty state when no profile exists."""
        page.goto(server_url + "/profile")
        empty = page.locator(".empty-state")
        assert empty.is_visible()
        assert "No profile yet" in empty.inner_text()
        btn = page.locator("button", has_text="Set Up Profile")
        assert btn.is_visible()

    def test_profile_editor_loads(self, page, server_url: str) -> None:
        """Clicking 'Set Up Profile' loads the profile editor via HTMX."""
        page.goto(server_url + "/profile")
        btn = page.locator("button", has_text="Set Up Profile")
        btn.click()
        page.wait_for_selector("#profile-area textarea#raw_text")
        textarea = page.locator("#raw_text")
        assert textarea.is_visible()
        assert page.locator("button", has_text="Save Profile").is_visible()
        assert page.locator("button", has_text="Cancel").is_visible()

    def test_profile_editor_cancel(self, page, server_url: str) -> None:
        """Clicking Cancel in editor returns to profile view with empty state."""
        page.goto(server_url + "/profile")
        page.locator("button", has_text="Set Up Profile").click()
        page.wait_for_selector("#profile-area textarea#raw_text")
        page.locator("button", has_text="Cancel").click()
        page.wait_for_selector(".empty-state")
        assert page.locator(".empty-state").is_visible()

    def test_profile_editor_save(self, page, server_url: str) -> None:
        """Filling textarea and saving shows profile view with content."""
        page.goto(server_url + "/profile")
        page.locator("button", has_text="Set Up Profile").click()
        page.wait_for_selector("#profile-area textarea#raw_text")
        textarea = page.locator("#raw_text")
        textarea.fill("I am a software engineer who loves Python and AI.")
        page.locator("button", has_text="Save Profile").click()
        # Wait for profile view to appear — success alert and profile card
        page.wait_for_selector(".alert-success")
        # Should show "Profile saved" success alert
        assert page.locator(".alert-success", has_text="Profile saved").is_visible()
        # Should show the profile card
        profile_card = page.locator("#profile-area .card").first
        assert profile_card.is_visible()
        # Should show structured data with the mock profile name
        assert page.locator("#profile-area", has_text="Test User").is_visible()

    def test_profile_editor_error_preserves_text(self, page, server_url: str, mock_llm) -> None:
        """When LLM raises on profile save, editor re-renders with user text preserved."""
        # Make the mock provider return invalid JSON so parsing fails
        mock_llm._responses["profile"] = "not valid json {{{"
        page.goto(server_url + "/profile")
        page.locator("button", has_text="Set Up Profile").click()
        page.wait_for_selector("#profile-area textarea#raw_text")
        textarea = page.locator("#raw_text")
        test_text = "This is my unique profile text that should be preserved."
        textarea.fill(test_text)
        page.locator("button", has_text="Save Profile").click()
        # Wait for the error response — editor should re-render with the error
        page.wait_for_selector("#profile-area .alert-error")
        assert page.locator(".alert-error").is_visible()
        # The textarea should still have the user's text
        assert page.locator("#raw_text").input_value() == test_text

    def test_dashboard_after_profile_setup(self, page, server_url: str) -> None:
        """After setting up a profile, dashboard shows 'Next Step' instead of 'Get Started'."""
        # First set up a profile
        page.goto(server_url + "/profile")
        page.locator("button", has_text="Set Up Profile").click()
        page.wait_for_selector("#profile-area textarea#raw_text")
        page.locator("#raw_text").fill("I am a tester.")
        page.locator("button", has_text="Save Profile").click()
        page.wait_for_selector("#profile-area .card")
        # Now go to dashboard
        page.goto(server_url + "/")
        card = page.locator(".card", has_text="Next Step")
        assert card.is_visible()
        assert page.locator("a[href='/daily']", has_text="Daily Question").is_visible()
