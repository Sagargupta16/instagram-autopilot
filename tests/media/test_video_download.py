from __future__ import annotations

import io
from unittest.mock import Mock, patch

import pytest
from botocore.response import StreamingBody
from botocore.session import get_session
from botocore.stub import Stubber

from src.media import video


def test_private_s3_download_uses_sigv4_and_preserves_key(tmp_path) -> None:
    session = get_session()
    client = session.create_client(
        "s3", region_name="us-west-2", aws_access_key_id="testing", aws_secret_access_key="testing"
    )
    data = b"\x00\x00\x00\x18ftypmp42video"
    with Stubber(client) as stubber:
        stubber.add_response(
            "get_object",
            {"Body": StreamingBody(io.BytesIO(data), len(data))},
            {"Bucket": "bucket", "Key": "folder/output.mp4"},
        )
        fake_session = Mock()
        fake_session.create_client.return_value = client
        with patch("botocore.session.get_session", return_value=fake_session):
            target = tmp_path / "video.mp4"
            video.download_video("s3://bucket/folder/output.mp4", target)
        assert target.read_bytes() == data
        assert fake_session.create_client.call_args.kwargs["config"].signature_version == "s3v4"


@pytest.mark.parametrize("uri", ["https://example.com/file.mp4", "s3://bucket", "s3:///file"])
def test_rejects_non_object_s3_uri_before_download(uri, tmp_path) -> None:
    with pytest.raises(ValueError):
        video.download_video(uri, tmp_path / "video.mp4")
