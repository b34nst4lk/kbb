"""Flow 3: Profile Editing — browser tests.

Covers edit, save, refresh structured view, and error states.
"""

from __future__ import annotations


class TestProfileEditing:
    """End-to-end browser tests for the profile editing flow."""

    def _setup_profile(self, page, server_url: str) -> None:
        """Helper: set up a profile so editing tests have data."""
        page.goto(server_url + "/profile")
        page.locator("button", has_text="Set Up Profile").click()
        page.wait_for_selector("#profile-area textarea#raw_text")
        page.locator("#raw_text").fill("I am a software engineer interested in testing.")
        page.locator("button", has_text="Save Profile").click()
        page.wait_for_selector("#profile-area .card")

    def test_profile_view_shows_structured_data(self, page, server_url: str) -> None:
        """After saving a profile, /profile shows structured data."""
        self._setup_profile(page, server_url)
        # Navigate to fresh profile page to get full-page render
        page.goto(server_url + "/profile")
        page.wait_for_selector("#profile-area .card")
        # Should show "Structured Data" section (CSS may uppercase)
        headers = page.locator("#profile-area .card-header").all_inner_texts()
        assert "Structured Data" in headers or "STRUCTURED DATA" in headers
        # Should show the mock profile name
        assert page.locator("#profile-area", has_text="Test User").is_visible()

    def test_edit_profile_button(self, page, server_url: str) -> None:
        """Clicking 'Edit Profile' swaps #profile-area with editor containing current text."""
        self._setup_profile(page, server_url)
        page.locator("button", has_text="Edit Profile").click()
        page.wait_for_selector("#profile-area textarea#raw_text")
        # Textarea should contain the previously saved text
        textarea = page.locator("#raw_text")
        assert "software engineer" in textarea.input_value().lower()

    def test_save_edited_profile(self, page, server_url: str) -> None:
        """Editing text and saving returns to profile view with updated content."""
        self._setup_profile(page, server_url)
        page.locator("button", has_text="Edit Profile").click()
        page.wait_for_selector("#profile-area textarea#raw_text")
        textarea = page.locator("#raw_text")
        textarea.fill("I am a data scientist who loves machine learning and Python.")
        page.locator("button", has_text="Save Profile").click()
        # Wait for success message
        page.wait_for_selector(".alert-success")
        assert page.locator(".alert-success", has_text="Profile saved").is_visible()

    def test_refresh_structured_view(self, page, server_url: str) -> None:
        """Clicking 'Refresh Structured View' re-parses profile via LLM and updates view."""
        self._setup_profile(page, server_url)
        page.locator("button", has_text="Refresh Structured View").click()
        # Wait for the view to reload
        page.wait_for_selector("#profile-area .card")
        # Should still show profile (refreshed)
        assert page.locator("#profile-area .card", has_text="Profile").is_visible()

    def test_refresh_structured_view_error(self, page, server_url: str, mock_llm) -> None:
        """When LLM raises on profile refresh, an error alert appears."""
        self._setup_profile(page, server_url)
        # The profile system prompt contains "self-description"
        mock_llm._raise_on["self-description"] = RuntimeError("LLM unavailable")
        page.locator("button", has_text="Refresh Structured View").click()
        # Should show error alert
        page.wait_for_selector(".alert-error")
        assert page.locator(".alert-error").is_visible()
