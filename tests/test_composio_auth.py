"""Tests for Composio connected account ID resolver."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.publisher.composio_auth import _looks_like_composio_id, resolve_connected_account_id


class TestLooksLikeComposioId:
    def test_valid_uuid(self) -> None:
        assert _looks_like_composio_id("550e8400-e29b-41d4-a716-446655440000") is True

    def test_valid_nanoid(self) -> None:
        assert _looks_like_composio_id("ca_abc123def456") is True

    def test_invalid_format(self) -> None:
        assert _looks_like_composio_id("instagram_vick-udder") is False

    def test_empty_string(self) -> None:
        assert _looks_like_composio_id("") is False

    def test_short_uuid(self) -> None:
        assert _looks_like_composio_id("550e8400-e29b-41d4-a716") is False


class TestResolveConnectedAccountId:
    @patch("src.publisher.composio_auth._fetch_connected_accounts")
    def test_passthrough_if_already_uuid(self, mock_fetch: MagicMock) -> None:
        result = resolve_connected_account_id(
            "key", "instagram", "550e8400-e29b-41d4-a716-446655440000"
        )
        assert result == "550e8400-e29b-41d4-a716-446655440000"
        mock_fetch.assert_not_called()

    @patch("src.publisher.composio_auth._fetch_connected_accounts")
    def test_passthrough_if_nanoid(self, mock_fetch: MagicMock) -> None:
        result = resolve_connected_account_id("key", "instagram", "ca_abc123")
        assert result == "ca_abc123"
        mock_fetch.assert_not_called()

    @patch("src.publisher.composio_auth._fetch_connected_accounts")
    def test_resolves_by_app_name(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [
            {"id": "aaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "appName": "instagram"},
        ]
        result = resolve_connected_account_id("key", "instagram", "some-alias")
        assert result == "aaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    @patch("src.publisher.composio_auth._fetch_connected_accounts")
    def test_returns_none_when_no_match(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [
            {"id": "aaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "appName": "twitter"},
        ]
        result = resolve_connected_account_id("key", "instagram")
        assert result is None

    @patch("src.publisher.composio_auth._fetch_connected_accounts")
    def test_picks_first_when_multiple(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [
            {"id": "first-uuid", "appName": "instagram", "labels": []},
            {"id": "second-uuid", "appName": "instagram", "labels": []},
        ]
        result = resolve_connected_account_id("key", "instagram")
        assert result == "first-uuid"

    @patch("src.publisher.composio_auth._fetch_connected_accounts")
    def test_matches_hint_in_labels(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [
            {"id": "first-uuid", "appName": "instagram", "labels": ["sagar_sethh"]},
            {"id": "second-uuid", "appName": "instagram", "labels": ["creativity.prompt"]},
        ]
        result = resolve_connected_account_id("key", "instagram", "creativity.prompt")
        assert result == "second-uuid"
