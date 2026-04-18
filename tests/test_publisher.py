"""Tests for Instagram publisher (Composio v3 REST API calls mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


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
            connected_account_id="ca_test123",
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
            connected_account_id="ca_test123",
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

        publish_reel(
            video_url="s3://b/v.mp4",
            caption="c",
            api_key="k",
            ig_user_id="123",
            connected_account_id="ca_test123",
        )
        first_call_body = mock_post.call_args_list[0].kwargs["json"]
        assert first_call_body["arguments"]["media_type"] == "REELS"
        assert first_call_body["arguments"]["share_to_feed"] is True

    @patch("src.publisher.instagram.requests.post")
    def test_sends_v3_request_format(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = [
            MagicMock(ok=True, json=MagicMock(return_value={"data": {"id": "c"}})),
            MagicMock(ok=True, json=MagicMock(return_value={"data": {"id": "m"}})),
        ]

        from src.publisher.instagram import publish_image_post

        publish_image_post(
            image_url="https://example.com/test.png",
            caption="Test",
            api_key="key",
            ig_user_id="123",
            connected_account_id="ca__WhTEKdz5xRg",
            user_id="my-user-id",
        )
        first_call_body = mock_post.call_args_list[0].kwargs["json"]
        assert first_call_body["connected_account_id"] == "ca__WhTEKdz5xRg"
        assert first_call_body["user_id"] == "my-user-id"
        assert "arguments" in first_call_body

    @patch("src.publisher.instagram.requests.post")
    def test_raises_on_composio_action_failure(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            ok=True,
            json=MagicMock(
                return_value={
                    "data": {
                        "message": "Failed to create container (status 400)",
                        "status_code": 400,
                    },
                    "successful": False,
                    "error": "Only photo or video can be accepted as media type",
                }
            ),
        )

        from src.publisher.instagram import ComposioActionError, publish_image_post

        with pytest.raises(ComposioActionError, match="Only photo or video"):
            publish_image_post(
                image_url="https://bad-url.example.com/img",
                caption="Test",
                api_key="key",
                ig_user_id="123",
                connected_account_id="ca_test123",
            )
