from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.adapters import places


@pytest.fixture(autouse=True)
def _tmp_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(places, "CACHE_PATH", tmp_path / "places.json")
    monkeypatch.setattr("src.settings.settings.meta_user_access_token", "test-token")
    monkeypatch.setattr("src.settings.settings.meta_graph_api_version", "v21.0")
    return tmp_path


def _resp(data: list[dict]) -> Mock:
    return Mock(ok=True, status_code=200, json=lambda: {"data": data})


def test_resolve_picks_first_with_location() -> None:
    with patch("src.adapters.places.requests.get") as g:
        g.return_value = _resp(
            [
                {"id": "111", "name": "Abstract Concept", "location": {}},
                {
                    "id": "222",
                    "name": "Bali Beach",
                    "location": {"latitude": -8.4, "longitude": 115.2},
                },
                {
                    "id": "333",
                    "name": "Another",
                    "location": {"latitude": 1.0, "longitude": 2.0},
                },
            ]
        )
        result = places.resolve_location_id("Bali Beach")
    assert result == "222"


def test_resolve_returns_none_on_empty() -> None:
    with patch("src.adapters.places.requests.get") as g:
        g.return_value = _resp([])
        assert places.resolve_location_id("Nowhereland") is None


def test_resolve_returns_none_on_403() -> None:
    with patch("src.adapters.places.requests.get") as g:
        g.return_value = Mock(ok=False, status_code=403, text="denied")
        assert places.resolve_location_id("Bali") is None


def test_resolve_returns_none_on_empty_query() -> None:
    assert places.resolve_location_id("") is None


def test_resolve_returns_none_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.settings.settings.meta_user_access_token", "")
    assert places.resolve_location_id("Bali") is None


def test_resolve_uses_cache_on_second_call() -> None:
    with patch("src.adapters.places.requests.get") as g:
        g.return_value = _resp(
            [
                {
                    "id": "222",
                    "name": "Bali",
                    "location": {"latitude": -8.4, "longitude": 115.2},
                }
            ]
        )
        first = places.resolve_location_id("Bali")
        second = places.resolve_location_id("Bali")
    assert first == "222" == second
    assert g.call_count == 1


def test_invalidate_drops_cache_entry() -> None:
    with patch("src.adapters.places.requests.get") as g:
        g.return_value = _resp(
            [
                {
                    "id": "222",
                    "name": "Bali",
                    "location": {"latitude": -8.4, "longitude": 115.2},
                }
            ]
        )
        places.resolve_location_id("Bali")
        places.invalidate("Bali")
        places.resolve_location_id("Bali")
    assert g.call_count == 2
