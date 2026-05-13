from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from stable_coin_trader.models import ResearchSignal


def _research_signals_path(path: str | os.PathLike[str]) -> Path:
    raw_path = os.fspath(path).strip()
    if not raw_path:
        raise ValueError("research signals path cannot be blank")
    if os.path.normpath(raw_path) == ".":
        raise ValueError("research signals path cannot be the current directory")

    research_signals_path = Path(raw_path)
    if research_signals_path.is_dir():
        raise ValueError("research signals path must be a file")
    return research_signals_path


def _load_json_list(path: Path) -> list[Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("research signal fixture must contain valid JSON") from exc

    if not isinstance(data, list):
        raise ValueError("research signal fixture must be a JSON list")
    return data


def load_active_research_signals(
    path: str | os.PathLike[str],
    now: datetime | None = None,
) -> list[ResearchSignal]:
    data = _load_json_list(_research_signals_path(path))
    signals = [_validate_signal(item, index) for index, item in enumerate(data)]

    return [signal for signal in signals if not signal.is_expired(now)]


def _validate_signal(item: Any, index: int) -> ResearchSignal:
    try:
        return ResearchSignal.model_validate(item)
    except ValidationError as exc:
        raise ValueError(f"research signal at index {index} is invalid") from exc
