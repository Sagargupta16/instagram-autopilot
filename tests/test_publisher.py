"""Tests for publishers (Composio calls mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestInstagramPublisher:
    @patch("src.publisher.instagram.ComposioToolSet")
    def test_publish_image_post_two_step(self, mock_toolset_cls: MagicMock) -> None:
        mock_toolset = MagicMock()
        mock_toolset_cls.return_value = mock_toolset

        mock_toolset.execute_action.side_effect = [
            {"data": {"id": "container_123"}},  # Create container
            {"data": {"id": "media_456"}},  # Publish
        ]

        from src.publisher.instagram import publish_image_post

        media_id = publish_image_post(
            image_url="https://example.com/test.png",
            caption="Test caption #test",
            api_key="test-key",
        )

        assert media_id == "media_456"
        assert mock_toolset.execute_action.call_count == 2

    @patch("src.publisher.instagram.ComposioToolSet")
    def test_passes_correct_params_to_container(self, mock_toolset_cls: MagicMock) -> None:
        mock_toolset = MagicMock()
        mock_toolset_cls.return_value = mock_toolset

        mock_toolset.execute_action.side_effect = [
            {"data": {"id": "container_123"}},
            {"data": {"id": "media_456"}},
        ]

        from src.publisher.instagram import IG_USER_ID, publish_image_post

        publish_image_post(
            image_url="https://example.com/img.png",
            caption="My caption",
            api_key="key",
        )

        first_call = mock_toolset.execute_action.call_args_list[0]
        params = first_call.kwargs["params"]
        assert params["ig_user_id"] == IG_USER_ID
        assert params["image_url"] == "https://example.com/img.png"
        assert params["caption"] == "My caption"


class TestTwitterPublisher:
    @patch("src.publisher.twitter.ComposioToolSet")
    def test_publish_text_post_success(self, mock_toolset_cls: MagicMock) -> None:
        mock_toolset = MagicMock()
        mock_toolset_cls.return_value = mock_toolset
        mock_toolset.execute_action.return_value = {"data": {"id": "tweet_789"}}

        from src.publisher.twitter import publish_text_post

        tweet_id = publish_text_post(text="Test tweet", api_key="test-key")
        assert tweet_id == "tweet_789"

    @patch("src.publisher.twitter.ComposioToolSet")
    def test_returns_none_when_not_connected(self, mock_toolset_cls: MagicMock) -> None:
        mock_toolset = MagicMock()
        mock_toolset_cls.return_value = mock_toolset
        mock_toolset.execute_action.side_effect = Exception("No active connection")

        from src.publisher.twitter import publish_text_post

        result = publish_text_post(text="Test tweet", api_key="test-key")
        assert result is None

    @patch("src.publisher.twitter.ComposioToolSet")
    def test_handles_nested_response_format(self, mock_toolset_cls: MagicMock) -> None:
        mock_toolset = MagicMock()
        mock_toolset_cls.return_value = mock_toolset
        mock_toolset.execute_action.return_value = {
            "data": {"data": {"data": {"id": "nested_id"}}}
        }

        from src.publisher.twitter import publish_text_post

        tweet_id = publish_text_post(text="Test", api_key="key")
        assert tweet_id == "nested_id"
