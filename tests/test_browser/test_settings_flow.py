"""Flow 5: Settings Update — browser tests.

Covers settings form rendering, save success, and invalid provider errors.
"""

from __future__ import annotations


class TestSettingsUpdate:
    """End-to-end browser tests for the settings update flow."""

    def test_settings_form_renders(self, page, server_url: str) -> None:
        """Settings page shows form with all config fields."""
        page.goto(server_url + "/settings")
        assert page.locator("#data_dir").is_visible()
        assert page.locator("#llm_provider").is_visible()
        assert page.locator("#llm_model").is_visible()
        assert page.locator("#transcription_provider").is_visible()
        assert page.locator("button", has_text="Save Settings").is_visible()

    def test_save_settings_success(self, page, server_url: str) -> None:
        """Changing a field and saving shows success message."""
        page.goto(server_url + "/settings")
        # Change the model name
        page.locator("#llm_model").fill("test-model-name")
        page.locator("button", has_text="Save Settings").click()
        # Wait for success message
        page.wait_for_selector(".alert-success")
        assert page.locator(".alert-success", has_text="Settings saved").is_visible()

    def test_save_settings_invalid_provider(self, page, server_url: str) -> None:
        """Submitting an invalid LLM provider shows error alert with valid options."""
        page.goto(server_url + "/settings")
        # Override the provider select to an invalid value via JS
        page.evaluate(
            """() => {
            const select = document.getElementById('llm_provider');
            const option = document.createElement('option');
            option.value = 'invalid_provider';
            option.text = 'Invalid Provider';
            select.appendChild(option);
            select.value = 'invalid_provider';
        }"""
        )
        page.locator("button", has_text="Save Settings").click()
        # Wait for error alert
        page.wait_for_selector(".alert-error")
        assert page.locator(".alert-error").is_visible()
        # Should mention valid options
        error_text = page.locator(".alert-error").inner_text()
        assert "anthropic" in error_text.lower() or "Invalid LLM provider" in error_text
