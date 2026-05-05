"""Generate short videos via Bedrock Nova Reel (async, S3 output).

Nova Reel v1 only outputs 1280x720 landscape. Instagram Reels expect 9:16
portrait and will letterbox landscape sources -- usable but sub-optimal.
Once Nova Reel supports 720x1280 natively, swap the dimension below.
An ffmpeg post-process step could also pad to 9:16, but that would require
adding ffmpeg to the runner and is deferred until anyone actually switches
a pillar to `content_format: "reel"` (all pillars are currently carousels).
"""

from __future__ import annotations

import logging
import time

from src.adapters.bedrock import get_async_invocation_status, start_async_invocation

log = logging.getLogger(__name__)

# Nova Reel v1 supported output dimension. Do not change without checking
# the model docs -- unsupported values fail the async job silently.
NOVA_REEL_DIMENSION = "1280x720"


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
                "dimension": NOVA_REEL_DIMENSION,
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
