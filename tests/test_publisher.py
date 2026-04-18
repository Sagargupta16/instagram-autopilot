"""Tests for publishers (Composio REST API calls mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestInstagramPublisher:
    @patch("src.publisher.instagram.requests.post")
    def test_publish_image_post_two_step(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = [
            MagicMock(ok=True, json=MagicMock(return_value={"data": {"id": "container_123"}})),
            MagicMock(ok=True, json=MagicMock(return_value={"data": {"id": "media_456"}})),
        ]

        from src.publisher.instagram import publish_image_post

        media_id = publish_image_post(
            image_url="https://example.com/test.png",
            caption="Test caption #test",
            api_key="test-key",
            ig_user_id="123456",
            connected_account_id="test-account",
        )
        assert media_id == "media_456"
        assert mock_post.call_count == 2

    @patch("src.publisher.instagram.requests.post")
    def test_publish_reel_two_step(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = [
            MagicMock(ok=True, json=MagicMock(return_value={"data": {"id": "reel_container_789"}})),
            MagicMock(ok=True, json=MagicMock(return_value={"data": {"id": "reel_media_012"}})),
        ]

        from src.publisher.instagram import publish_reel

        media_id = publish_reel(
            video_url="s3://bucket/output.mp4",
            caption="Reel caption",
            api_key="test-key",
            ig_user_id="123456",
            connected_account_id="test-account",
        )
        assert media_id == "reel_media_012"
        assert mock_post.call_count == 2

    @patch("src.publisher.instagram.requests.post")
    def test_reel_uses_reels_media_type(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = [
            MagicMock(ok=True, json=MagicMock(return_value={"data": {"id": "c"}})),
            MagicMock(ok=True, json=MagicMock(return_value={"data": {"id": "m"}})),
        ]

        from src.publisher.instagram import publish_reel

        publish_reel(video_url="s3://b/v.mp4", caption="c", api_key="k", ig_user_id="123")
        first_call_body = mock_post.call_args_list[0].kwargs["json"]
        assert first_call_body["input"]["media_type"] == "REELS"
        assert first_call_body["input"]["share_to_feed"] is True


class TestTwitterPublisher:
    @patch("src.publisher.twitter.requests.post")
    def test_publish_text_post_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True, json=MagicMock(return_value={"data": {"id": "tweet_789"}})
        )

        from src.publisher.twitter import publish_text_post

        tweet_id = publish_text_post(text="Test tweet", api_key="test-key")
        assert tweet_id == "tweet_789"

    @patch("src.publisher.twitter.requests.post")
    def test_returns_none_on_failure(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(ok=False, status_code=400, text="error")

        from src.publisher.twitter import publish_text_post

        result = publish_text_post(text="Test tweet", api_key="test-key")
        assert result is None

    @patch("src.publisher.twitter.requests.post")
    def test_handles_nested_response_format(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            json=MagicMock(return_value={"data": {"data": {"data": {"id": "nested_id"}}}}),
        )

        from src.publisher.twitter import publish_text_post

        tweet_id = publish_text_post(text="Test", api_key="key")
        assert tweet_id == "nested_id"
