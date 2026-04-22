"""Generate short videos via Bedrock Nova Reel (async, S3 output)."""

from __future__ import annotations

import logging
import time

from src.adapters.bedrock import get_async_invocation_status, start_async_invocation

log = logging.getLogger(__name__)


def generate_video(
    prompt: str,
    model_id: str,
    s3_output_uri: str,
    *,
    duration_seconds: int = 6,
    poll_interval: int = 15,
    max_wait: int = 600,
) -> str:
    """Start an async video job, poll until complete, return the S3 URI."""
    body = {
        "modelInput": {
            "taskType": "TEXT_VIDEO",
            "textToVideoParams": {"text": prompt},
            "videoGenerationConfig": {
                "durationSeconds": duration_seconds,
                "fps": 24,
                "dimension": "1280x720",
            },
        },
        "outputDataConfig": {"s3OutputDataConfig": {"s3Uri": s3_output_uri}},
    }

    invocation_arn = start_async_invocation(model_id, body)
    log.info("Nova Reel job started: %s", invocation_arn)

    elapsed = 0
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        status_data = get_async_invocation_status(invocation_arn)
        status = status_data["status"]
        log.info("Nova Reel status: %s (%ds elapsed)", status, elapsed)

        if status == "Completed":
            output_uri = status_data["outputDataConfig"]["s3OutputDataConfig"]["s3Uri"]
            log.info("Reel generated: %s", output_uri)
            return output_uri + "/output.mp4"
        if status == "Failed":
            msg = status_data.get("failureMessage", "Unknown error")
            raise RuntimeError(f"Nova Reel generation failed: {msg}")

    raise TimeoutError(f"Nova Reel job did not complete within {max_wait}s")
