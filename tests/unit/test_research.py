import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from stable_coin_trader.research import load_active_research_signals


def signal_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "id": "signal-1",
        "observed_at": "2026-05-13T12:00:00Z",
        "published_at": "2026-05-13T11:59:00Z",
        "source": "fixture",
        "source_url": "https://example.com/signal-1",
        "source_quality": 0.8,
        "affected_assets": ["USDC"],
        "affected_venues": ["coinbase"],
        "event_type": "venue_outage",
        "direction": "risk_increase",
        "severity": 3,
        "confidence": 0.8,
        "ttl_seconds": 3600,
        "summary": "Active signal",
    }
    values.update(overrides)
    return values


def write_signals(path, signals: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(signals), encoding="utf-8")


def test_load_active_research_signals_filters_expired(tmp_path) -> None:
    path = tmp_path / "signals.json"
    write_signals(
        path,
        [
            signal_payload(id="active"),
            signal_payload(
                id="expired",
                observed_at="2026-05-13T10:00:00Z",
                published_at="2026-05-13T09:59:00Z",
                ttl_seconds=60,
                summary="Expired signal",
            ),
        ],
    )

    active = load_active_research_signals(
        path,
        now=datetime(2026, 5, 13, 12, 30, tzinfo=timezone.utc),
    )

    assert [signal.id for signal in active] == ["active"]


def test_load_active_research_signals_keeps_ttl_boundary_active(tmp_path) -> None:
    path = tmp_path / "signals.json"
    write_signals(path, [signal_payload(id="boundary", ttl_seconds=3600)])

    active = load_active_research_signals(
        path,
        now=datetime(2026, 5, 13, 13, 0, tzinfo=timezone.utc),
    )

    assert [signal.id for signal in active] == ["boundary"]


def test_load_active_research_signals_uses_timezone_aware_expiration(tmp_path) -> None:
    path = tmp_path / "signals.json"
    write_signals(
        path,
        [
            signal_payload(
                id="offset-active",
                observed_at="2026-05-13T08:00:00-04:00",
                published_at="2026-05-13T07:59:00-04:00",
                ttl_seconds=3600,
            ),
            signal_payload(
                id="offset-expired",
                observed_at="2026-05-13T07:58:59-04:00",
                published_at="2026-05-13T07:58:00-04:00",
                ttl_seconds=3600,
            ),
        ],
    )

    active = load_active_research_signals(
        path,
        now=datetime(2026, 5, 13, 9, 0, tzinfo=timezone(timedelta(hours=-4))),
    )

    assert [signal.id for signal in active] == ["offset-active"]
    assert active[0].observed_at == datetime(2026, 5, 13, 12, 0, tzinfo=timezone.utc)


def test_load_active_research_signals_treats_naive_now_as_utc(tmp_path) -> None:
    path = tmp_path / "signals.json"
    write_signals(path, [signal_payload(id="naive-now", ttl_seconds=3600)])

    active = load_active_research_signals(
        path,
        now=datetime(2026, 5, 13, 13, 0),
    )

    assert [signal.id for signal in active] == ["naive-now"]


def test_load_shipped_research_signals_fixture() -> None:
    path = "data/fixtures/research_signals.json"

    active = load_active_research_signals(
        path,
        now=datetime(2026, 5, 13, 12, 30, tzinfo=timezone.utc),
    )

    assert [signal.id for signal in active] == ["fixture-soft-warning"]
    assert active[0].affected_assets == ["USDC"]


@pytest.mark.parametrize("path", ["", " ", ".", "./"])
def test_load_active_research_signals_rejects_unsafe_paths(path) -> None:
    with pytest.raises(ValueError, match="path"):
        load_active_research_signals(path)


def test_load_active_research_signals_rejects_directory_path(tmp_path) -> None:
    with pytest.raises(ValueError, match="file"):
        load_active_research_signals(tmp_path)


def test_load_active_research_signals_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_active_research_signals(tmp_path / "missing.json")


def test_load_active_research_signals_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "signals.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="valid JSON"):
        load_active_research_signals(path)


def test_load_active_research_signals_rejects_non_list_json(tmp_path) -> None:
    path = tmp_path / "signals.json"
    path.write_text(json.dumps({"signals": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="list"):
        load_active_research_signals(path)


def test_load_active_research_signals_rejects_invalid_signal(tmp_path) -> None:
    path = tmp_path / "signals.json"
    write_signals(path, [signal_payload(direction="buy_now")])

    with pytest.raises(ValidationError):
        load_active_research_signals(path)
