"""Settings, read from environment variables (and an optional .env file)."""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MODEL = "gemini-3.5-flash"
CONFIRM_MODES = ("always", "sensitive", "never")


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so python-dotenv isn't required. Existing env vars win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    api_key: str | None = None
    model: str = DEFAULT_MODEL
    vision_model: str = DEFAULT_MODEL
    dry_run: bool = False
    confirm: str = "sensitive"
    max_steps: int = 25
    contacts_file: Path = Path("contacts.json")
    blender_path: str = "blender"
    whatsapp_mode: str = "auto"  # auto | desktop | web
    os_name: str = field(default_factory=platform.system)  # "Darwin", "Windows", "Linux"

    def __post_init__(self) -> None:
        if self.confirm not in CONFIRM_MODES:
            raise ValueError(f"confirm must be one of {CONFIRM_MODES}, got {self.confirm!r}")

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> "Config":
        _load_dotenv(Path(env_file))
        env = os.environ
        return cls(
            api_key=env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY"),
            model=env.get("JARVIS_MODEL", DEFAULT_MODEL),
            vision_model=env.get("JARVIS_VISION_MODEL") or env.get("JARVIS_MODEL", DEFAULT_MODEL),
            dry_run=_bool(env.get("JARVIS_DRY_RUN")),
            confirm=env.get("JARVIS_CONFIRM", "sensitive"),
            max_steps=int(env.get("JARVIS_MAX_STEPS", "25")),
            contacts_file=Path(env.get("JARVIS_CONTACTS", "contacts.json")),
            blender_path=env.get("JARVIS_BLENDER", "blender"),
            whatsapp_mode=env.get("JARVIS_WHATSAPP", "auto"),
        )

    def load_contacts(self) -> dict[str, dict[str, str]]:
        if not self.contacts_file.is_file():
            return {}
        data = json.loads(self.contacts_file.read_text(encoding="utf-8"))
        return {name.lower(): info for name, info in data.items()}
