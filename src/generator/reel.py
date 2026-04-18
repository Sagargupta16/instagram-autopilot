"""Generate short videos using AWS Bedrock Nova Reel."""

from __future__ import annotations

import logging
import time

import requests

from src.config import settings

log = logging.getLogger(__name__)

BEDROCK_START_URL = "https://bedrock-runtime.{region}.amazonaws.com/model/{model}/async-invoke"
BEDROCK_STATUS_URL = "https://bedrock-runtime.{region}.amazonaws.com/async-invoke/{arn}"


def generate_reel(
    prompt: str,
    model_id: str,
    s3_output_uri: str,
    *,
    duration_seconds: int = 6,
    poll_interval: int = 15,
    max_wait: int = 600,
) -> str:
    """Generate a short video via Bedrock Nova Reel.

    Submits an async job, polls until complete, and returns the S3 URI
    where the video was written.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.aws_bearer_token_bedrock}",
    }

    # Start async video generation
    start_url = BEDROCK_START_URL.format(
        region=settings.aws_region,
        model=model_id,
    )
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

    resp = requests.post(start_url, json=body, headers=headers, timeout=60)
    if not resp.ok:
        log.error("Bedrock %s returned %s: %s", resp.status_code, resp.reason, resp.text)
        resp.raise_for_status()

    invocation_arn = resp.json()["invocationArn"]
    log.info("Nova Reel job started: %s", invocation_arn)

    # Poll for completion
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        status_url = BEDROCK_STATUS_URL.format(
            region=settings.aws_region,
            arn=invocation_arn,
        )
        status_resp = requests.get(status_url, headers=headers, timeout=30)
        status_resp.raise_for_status()
        status_data = status_resp.json()

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
