"""Deterministic configuration and seed system.

`load_config()` reads ``configs/default.yaml`` (or a given path) into a
:class:`Config` that supports attribute access. `Config.get_rng(name)`
derives an independent, deterministic child RNG stream from the master
seed plus the stream name, so the same seed always yields identical
draws everywhere.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import yaml

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "configs" / "default.yaml"


class Config:
    """Dataclass-like wrapper over a nested dict with attribute access."""

    def __init__(self, data: dict[str, Any]):
        self._data = data

    def __getattr__(self, name: str) -> Any:
        try:
            value = self._data[name]
        except KeyError as exc:
            raise AttributeError(name) from exc
        if isinstance(value, dict):
            return Config(value)
        return value

    def __getitem__(self, key: str) -> Any:
        value = self._data[key]
        if isinstance(value, dict):
            return Config(value)
        return value

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        value = self._data.get(key, default)
        if isinstance(value, dict):
            return Config(value)
        return value

    def to_dict(self) -> dict[str, Any]:
        return self._data

    def get_rng(self, name: str) -> np.random.Generator:
        """Derive a deterministic, independent RNG stream for `name`."""
        master = int(self._data.get("seed", 0))
        digest = hashlib.sha256(f"{master}:{name}".encode()).digest()
        child_seed = int.from_bytes(digest[:8], "big")
        return np.random.default_rng(child_seed)


def load_config(path: str | Path | None = None) -> Config:
    """Load YAML config from `path` or the repo default."""
    p = Path(path) if path is not None else _DEFAULT_PATH
    with open(p) as f:
        data = yaml.safe_load(f)
    return Config(data)
