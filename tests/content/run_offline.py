"""Run pytest with dummy credentials, dotenv disabled, and sockets blocked."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4


def main() -> int:
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    for key in (
        "AWS_BEARER_TOKEN_BEDROCK",
        "COMPOSIO_API_KEY",
        "COMPOSIO_CONNECTED_ACCOUNT_ID",
        "COMPOSIO_USER_ID",
        "INSTAGRAM_USER_ID",
        "CLOUDINARY_CLOUD_NAME",
        "CLOUDINARY_API_KEY",
        "CLOUDINARY_API_SECRET",
    ):
        os.environ[key] = "offline-test"
    for key in ("GUARDIAN_API_KEY", "META_USER_ACCESS_TOKEN", "S3_VIDEO_BUCKET"):
        os.environ[key] = ""
    os.environ["INSTAGRAM_USER_ID"] = "123456"

    import pytest
    from pydantic_settings.sources import DotEnvSettingsSource

    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access is forbidden in offline tests")

    with (
        patch.object(DotEnvSettingsSource, "__call__", return_value={}),
        patch.object(DotEnvSettingsSource, "_read_env_files", return_value={}),
        patch("socket.socket.connect", blocked),
        patch("socket.socket.connect_ex", blocked),
        patch("socket.create_connection", blocked),
        patch("socket.getaddrinfo", blocked),
    ):
        # A unique child avoids Windows ACLs on a previous pytest user's shared temp root.
        base = Path(tempfile.gettempdir()).resolve() / f"content-tests-{uuid4().hex}"
        return pytest.main(["-p", "no:cacheprovider", f"--basetemp={base}", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
