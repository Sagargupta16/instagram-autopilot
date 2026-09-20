from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.flows import carousel_flow, image_flow
from src.media.image import ImageFilteredError


@pytest.fixture
def data() -> dict:
    return {
        "image_prompts": ["first", "filtered", "third", "fourth", "fifth"],
        "alt_texts": ["alt one", "alt two", "alt three", "alt four", "alt five"],
        "location_query": "Bali",
    }


@pytest.mark.parametrize("module", [carousel_flow, image_flow])
def test_filtered_prompts_keep_alt_text_and_return_receipt(module, data, monkeypatch) -> None:
    monkeypatch.setattr(
        module,
        "generate_image",
        Mock(side_effect=[ImageFilteredError("filtered"), b"two", b"three", b"four", b"five"]),
    )
    monkeypatch.setattr(module, "upload_image", lambda body: body.decode())
    monkeypatch.setattr(module, "resolve_location_id", Mock(return_value="place"))
    publisher = Mock(return_value="media-id")
    carousel = module is carousel_flow
    monkeypatch.setattr(module, "publish_carousel" if carousel else "publish_image_post", publisher)
    callback = Mock()
    flow = module.post_carousel if carousel else module.post_image
    assert flow(data, "caption", "model", dry_run=False, before_publish=callback) == "media-id"
    assert publisher.call_args.kwargs["before_publish"] is callback
    if carousel:
        assert publisher.call_args.kwargs["alt_texts"] == data["alt_texts"][1:]
    else:
        assert publisher.call_args.kwargs["alt_text"] == "alt two"


@pytest.mark.parametrize("module", [carousel_flow, image_flow])
def test_dryrun_saves_preview_without_external_side_effects(
    module, data, monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "generate_image", Mock(return_value=b"jpeg"))
    forbidden = Mock(side_effect=AssertionError("dry-run side effect"))
    monkeypatch.setattr(module, "upload_image", forbidden)
    monkeypatch.setattr(module, "resolve_location_id", forbidden)
    carousel = module is carousel_flow
    monkeypatch.setattr(module, "publish_carousel" if carousel else "publish_image_post", forbidden)
    flow = module.post_carousel if carousel else module.post_image
    assert flow(data, "caption", "model", dry_run=True, before_publish=forbidden) is None
    assert list((tmp_path / "output").rglob("*.jpg"))


def test_all_filtered_carousel_dryrun_fails(data, monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        carousel_flow, "generate_image", Mock(side_effect=ImageFilteredError("filtered"))
    )
    with pytest.raises(RuntimeError, match="Only 0"):
        carousel_flow.post_carousel(data, "caption", "model", dry_run=True)


def test_alt_text_mismatch_fails_before_generation(data, monkeypatch) -> None:
    data["alt_texts"] = ["one"]
    generate = Mock(side_effect=AssertionError("paid generation"))
    monkeypatch.setattr(carousel_flow, "generate_image", generate)
    with pytest.raises(ValueError, match="alt"):
        carousel_flow.post_carousel(data, "caption", "model", dry_run=False)
