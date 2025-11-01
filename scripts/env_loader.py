"""Lightweight .env loader for the Reading Archive project.

This avoids adding external dependencies while still allowing environment
variables to be managed from a `.env` file at the repository root.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Optional[Path] = None, *, override: bool = False) -> None:
    """Load environment variables from a `.env` file.

    Parameters
    ----------
    path:
        Optional custom path. Defaults to `<repo>/.env`.
    override:
        When True, values from the file overwrite existing os.environ values.
    """

    env_path = path or (ROOT / ".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        value = value.replace("\\n", "\n")
        if override or key not in os.environ:
            os.environ[key] = value
