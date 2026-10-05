"""Read ``.env`` into the environment."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env_file(path: Path | str | None = None) -> list[str]:
    env_path = Path(path) if path else DEFAULT_ENV_FILE
    if not env_path.is_file():
        return []
    applied = []
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value
            applied.append(key)
    return applied

