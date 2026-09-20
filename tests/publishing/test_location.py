"""Location fallback depends on explicit provider error details."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.adapters.composio import ComposioActionError
from src.publishing.boundaries import create_with_location


@pytest.mark.parametrize(
    "error",
    [
        {"code": "INVALID_LOCATION_ID"},
        {"error": {"type": "INSTAGRAM_PLATFORM_API__INVALID_LOCATION_ID"}},
        "INSTAGRAM_PLATFORM_API__INVALID_LOCATION_ID: bad page id",
    ],
)
def test_explicit_location_error_retries_container_once(error):
    execute = Mock(
        side_effect=[
            {"successful": False, "error": error},
            {"successful": True, "data": {"id": "container"}},
        ]
    )
    params = {"image_url": "https://example.com/image.jpg"}
    result = create_with_location(execute, "INSTAGRAM_CREATE_MEDIA_CONTAINER", params, "bad")
    assert result["data"]["id"] == "container"
    assert execute.call_args_list[0].kwargs["params"]["location_id"] == "bad"
    assert execute.call_args_list[1].kwargs["params"] == params
    assert "location_id" not in params


def test_non_error_metadata_cannot_trigger_location_retry():
    execute = Mock(
        return_value={
            "successful": False,
            "error": {"code": 9004, "message": "Media download failed"},
            "data": {"trace_id": "INVALID_LOCATION_ID"},
        }
    )
    with pytest.raises(ComposioActionError):
        create_with_location(execute, "INSTAGRAM_CREATE_MEDIA_CONTAINER", {}, "location")
    assert execute.call_count == 1


def test_repeated_invalid_location_failure_is_not_retried_again():
    execute = Mock(return_value={"successful": False, "error": {"code": "INVALID_LOCATION_ID"}})
    with pytest.raises(ComposioActionError):
        create_with_location(execute, "INSTAGRAM_CREATE_MEDIA_CONTAINER", {}, "bad")
    assert execute.call_count == 2
