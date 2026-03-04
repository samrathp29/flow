"""Configuration loading and validation for flow."""

import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigNotFound(Exception):
    """Raised when config.toml does not exist."""

    def __init__(self):
        super().__init__("Configuration not found. Run `flow init` to set up flow.")


class ConfigValidationError(Exception):
    """Raised when config.toml is missing required fields."""


@dataclass
class FlowConfig:
    llm_provider: str
    llm_model: str
    api_key: str
    data_dir: Path

    CONFIG_PATH: Path = Path.home() / ".config" / "flow" / "config.toml"

    @classmethod
    def load(cls) -> "FlowConfig":
        if not cls.CONFIG_PATH.exists():
            raise ConfigNotFound()

        raw = tomllib.loads(cls.CONFIG_PATH.read_text())

        llm = raw.get("llm", {})
        storage = raw.get("storage", {})

        missing = [
            field
            for field in ("provider", "model", "api_key")
            if not llm.get(field)
        ]
        if missing:
            raise ConfigValidationError(
                f"Missing required config fields in [llm]: {', '.join(missing)}"
            )

        return cls(
            llm_provider=llm["provider"],
            llm_model=llm["model"],
            api_key=llm["api_key"],
            data_dir=Path(storage.get("data_dir", "~/.local/share/flow")).expanduser(),
        )
