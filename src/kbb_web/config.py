"""Configuration management for the web adapter.

Loads settings from a YAML config file with environment variable overrides.
Config file search order (first found wins):
  1. KBB_CONFIG_FILE env var
  2. ./kbb.yaml
  3. ~/.config/kbb/kbb.yaml
  4. ~/.kbb.yaml
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from kbb.models import KBBConfig, LLMProviderName, TranscriptionProviderName


@dataclass
class WebConfig:
    """Web adapter configuration. Wraps KBBConfig with web-specific settings."""

    data_dir: Path = Path("data")
    llm_provider: LLMProviderName = LLMProviderName.ANTHROPIC
    llm_model: str = "claude-sonnet-4-20250514"
    llm_api_key: str = ""
    llm_base_url: str = ""
    daily_log_time: str = "09:00"
    host: str = "127.0.0.1"
    port: int = 8199
    debug: bool = False
    config_file_path: Path | None = None

    # Transcription settings
    transcription_provider: TranscriptionProviderName = TranscriptionProviderName.FASTER_WHISPER
    transcription_fallback: TranscriptionProviderName | None = None
    whisper_model: str = "base"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"

    def to_kbb_config(self) -> KBBConfig:
        """Convert to core engine config."""
        return KBBConfig(
            data_dir=self.data_dir,
            llm_provider=self.llm_provider,
            llm_model=self.llm_model,
            llm_api_key=self._resolve_api_key(),
            llm_base_url=self.llm_base_url,
            daily_log_time=self.daily_log_time,
            transcription_provider=self.transcription_provider,
            transcription_fallback=self.transcription_fallback,
            whisper_model=self.whisper_model,
            whisper_device=self.whisper_device,
            whisper_compute_type=self.whisper_compute_type,
        )

    def _resolve_api_key(self) -> str:
        """Use config file value; fall back to env var."""
        if self.llm_api_key:
            return self.llm_api_key
        env_keys = {
            LLMProviderName.ANTHROPIC: ["ANTHROPIC_API_KEY"],
            LLMProviderName.OPENAI: ["OPENAI_API_KEY"],
            LLMProviderName.OLLAMA: [],
        }
        for key in env_keys.get(self.llm_provider, []):
            val = os.getenv(key, "")
            if val:
                return val
        return os.getenv("KBB_API_KEY", "")

    @classmethod
    def from_dict(cls, d: dict) -> WebConfig:
        """Parse from YAML dict with env var overrides."""
        llm = d.get("llm", {})
        web = d.get("web", {})
        transcription = d.get("transcription", {})
        provider_str = os.getenv("KBB_LLM_PROVIDER", llm.get("provider", "anthropic"))
        trans_provider_str = os.getenv(
            "KBB_TRANSCRIPTION_PROVIDER", transcription.get("provider", "faster-whisper")
        )
        trans_fallback_str = os.getenv(
            "KBB_TRANSCRIPTION_FALLBACK", transcription.get("fallback", "")
        )
        return cls(
            data_dir=Path(os.getenv("KBB_DATA_DIR", d.get("data_dir", "data"))).expanduser(),
            llm_provider=LLMProviderName(provider_str),
            llm_model=os.getenv("KBB_LLM_MODEL", llm.get("model", "claude-sonnet-4-20250514")),
            llm_api_key=llm.get("api_key", ""),
            llm_base_url=os.getenv("KBB_LLM_BASE_URL", llm.get("base_url", "")),
            daily_log_time=d.get("daily_log_time", "09:00"),
            host=web.get("host", "127.0.0.1"),
            port=int(web.get("port", 8199)),
            debug=web.get("debug", False),
            transcription_provider=TranscriptionProviderName(trans_provider_str),
            transcription_fallback=TranscriptionProviderName(trans_fallback_str)
            if trans_fallback_str
            else None,
            whisper_model=os.getenv(
                "KBB_WHISPER_MODEL", transcription.get("whisper_model", "base")
            ),
            whisper_device=os.getenv(
                "KBB_WHISPER_DEVICE", transcription.get("whisper_device", "auto")
            ),
            whisper_compute_type=os.getenv(
                "KBB_WHISPER_COMPUTE_TYPE", transcription.get("whisper_compute_type", "auto")
            ),
        )

    def to_dict(self) -> dict:
        """Serialize for saving. API key is never written to file."""
        return {
            "data_dir": str(self.data_dir),
            "llm": {
                "provider": self.llm_provider.value,
                "model": self.llm_model,
                "api_key": "",  # never write API key to file
                "base_url": self.llm_base_url,
            },
            "daily_log_time": self.daily_log_time,
            "transcription": {
                "provider": self.transcription_provider.value,
                "fallback": self.transcription_fallback.value
                if self.transcription_fallback
                else "",
                "whisper_model": self.whisper_model,
                "whisper_device": self.whisper_device,
                "whisper_compute_type": self.whisper_compute_type,
            },
            "web": {
                "host": self.host,
                "port": self.port,
                "debug": self.debug,
            },
        }


def _find_config_file() -> Path | None:
    """Search for config file in standard locations."""
    explicit = os.getenv("KBB_CONFIG_FILE")
    if explicit:
        p = Path(explicit).expanduser()
        if p.exists():
            return p
    for path_str in ["./kbb.yaml", "~/.config/kbb/kbb.yaml", "~/.kbb.yaml"]:
        p = Path(path_str).expanduser()
        if p.exists():
            return p
    return None


def load_config() -> WebConfig:
    """Load config from YAML file or environment defaults.

    Resolves data_dir to an absolute path at load time (relative to CWD
    if not already absolute), so the engine always uses a consistent
    directory regardless of later CWD changes.
    """
    config_path = _find_config_file()
    if config_path:
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        cfg = WebConfig.from_dict(data)
        cfg.config_file_path = config_path
    else:
        # No config file — build from env vars with defaults
        data_dir = os.getenv("KBB_DATA_DIR", "data")
        cfg = WebConfig(data_dir=Path(data_dir).expanduser())

    # Always resolve data_dir to absolute (relative to CWD at load time)
    if not cfg.data_dir.is_absolute():
        cfg.data_dir = cfg.data_dir.resolve()

    return cfg


def save_config(config: WebConfig) -> Path:
    """Save config to YAML file. Creates directory if needed."""
    target = config.config_file_path
    if target is None:
        target = Path("~/.config/kbb/kbb.yaml").expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w") as f:
        yaml.dump(config.to_dict(), f, default_flow_style=False)
    config.config_file_path = target
    return target
