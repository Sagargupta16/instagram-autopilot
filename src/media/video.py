"""Generate short videos via Bedrock Luma Ray 2 (async, S3 output).

Luma Ray 2 accepts "9:16" natively, so reels render portrait directly --
no letterboxing (Nova Reel only did 1280x720 landscape; that model is now
AWS-legacy and was dropped). Output is 720p at 5s or 9s. The output S3
bucket must live in the SAME region as the model (us-west-2).
"""

from __future__ import annotations

import logging
import time

from src.adapters.bedrock import get_async_invocation_status, start_async_invocation

log = logging.getLogger(__name__)

# Luma Ray 2 only accepts "5s" or "9s".
_VALID_DURATIONS = {5, 9}


def generate_video(
    prompt: str,
    model_id: str,
    s3_output_uri: str,
    *,
    duration_seconds: int = 5,
    aspect_ratio: str = "9:16",
    poll_interval: int = 15,
    max_wait: int = 600,
) -> str:
    """Start an async video job, poll until complete, return the S3 URI."""
    if duration_seconds not in _VALID_DURATIONS:
        raise ValueError(
            f"Luma Ray 2 supports durations {sorted(_VALID_DURATIONS)}s, got {duration_seconds}"
        )

    body = {
        "modelInput": {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "duration": f"{duration_seconds}s",
            "resolution": "720p",
            "loop": False,
        },
        "outputDataConfig": {"s3OutputDataConfig": {"s3Uri": s3_output_uri}},
    }

    invocation_arn = start_async_invocation(model_id, body)
    log.info("Luma Ray 2 job started: %s", invocation_arn)

    elapsed = 0
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        status_data = get_async_invocation_status(invocation_arn)
        status = status_data["status"]
        log.info("Luma Ray 2 status: %s (%ds elapsed)", status, elapsed)

        if status == "Completed":
            output_uri = status_data["outputDataConfig"]["s3OutputDataConfig"]["s3Uri"]
            log.info("Reel generated: %s", output_uri)
            return output_uri + "/output.mp4"
        if status == "Failed":
            msg = status_data.get("failureMessage", "Unknown error")
            raise RuntimeError(f"Luma Ray 2 generation failed: {msg}")

    raise TimeoutError(f"Luma Ray 2 job did not complete within {max_wait}s")
