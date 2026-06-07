"""Flow 7: Transcription — browser tests.

Covers voice recorder button presence, audio upload input presence,
and API endpoint behavior. Browser-level recording/upload testing requires
microphone access and is outside scope; we verify DOM structure and API.
"""

from __future__ import annotations

from pathlib import Path

import httpx


class TestTranscription:
    """Browser tests for transcription UI and API."""

    def test_voice_recorder_button_present(self, page, server_url: str) -> None:
        """Question card shows a button with data-voice-recorder attribute."""
        # Set up profile and generate a question
        page.goto(server_url + "/profile")
        page.locator("button", has_text="Set Up Profile").click()
        page.wait_for_selector("#profile-area textarea#raw_text")
        page.locator("#raw_text").fill("I am a tester.")
        page.locator("button", has_text="Save Profile").click()
        page.wait_for_selector("#profile-area .card")
        page.goto(server_url + "/daily")
        page.locator("button", has_text="Generate Question").click()
        page.wait_for_selector("#response-textarea")
        # Should have a voice recorder button
        assert page.locator("[data-voice-recorder]").is_visible()

    def test_audio_upload_input_present(self, page, server_url: str) -> None:
        """Question card shows a file input for audio upload."""
        page.goto(server_url + "/profile")
        page.locator("button", has_text="Set Up Profile").click()
        page.wait_for_selector("#profile-area textarea#raw_text")
        page.locator("#raw_text").fill("I am a tester.")
        page.locator("button", has_text="Save Profile").click()
        page.wait_for_selector("#profile-area .card")
        page.goto(server_url + "/daily")
        page.locator("button", has_text="Generate Question").click()
        page.wait_for_selector("#response-textarea")
        # Should have an audio upload file input (hidden via CSS but present in DOM)
        assert page.locator("#audio-upload").count() == 1

    def test_transcribe_api_endpoint(self, server_url: str) -> None:
        """POST /api/transcribe with a valid audio file returns transcription."""
        # Create a minimal WAV file for testing
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # Minimal WAV header (44 bytes) + silence
            f.write(b"RIFF" + b"\x24\x00\x00\x00" + b"WAVE" + b"fmt " + b"\x10\x00\x00\x00")
            f.write(b"\x01\x00" + b"\x01\x00" + b"\x44\xac\x00\x00" + b"\x88X\x01\x00")
            f.write(b"\x02\x00" + b"\x10\x00" + b"data" + b"\x00\x00\x00\x00")
            wav_path = Path(f.name)

        try:
            with open(wav_path, "rb") as f:
                resp = httpx.post(
                    f"{server_url}/api/transcribe",
                    files={"file": ("test.wav", f, "audio/wav")},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert "text" in data
            assert data["text"] == "transcribed text from mock"
        finally:
            wav_path.unlink(missing_ok=True)

    def test_transcribe_api_no_file(self, server_url: str) -> None:
        """POST /api/transcribe without a file returns 422 (validation error)."""
        resp = httpx.post(f"{server_url}/api/transcribe")
        assert resp.status_code == 422

    def test_transcribe_api_unsupported_format(self, server_url: str) -> None:
        """POST /api/transcribe with a .txt file returns 400."""
        resp = httpx.post(
            f"{server_url}/api/transcribe",
            files={"file": ("test.txt", b"not audio", "text/plain")},
        )
        assert resp.status_code == 400
