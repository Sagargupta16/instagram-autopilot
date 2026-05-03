"""AWS Bedrock HTTP client (bearer token auth, no boto3)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from src.settings import settings

log = logging.getLogger(__name__)

INVOKE_URL = "https://bedrock-runtime.{region}.amazonaws.com/model/{model}/invoke"
ASYNC_INVOKE_URL = "https://bedrock-runtime.{region}.amazonaws.com/model/{model}/async-invoke"
ASYNC_STATUS_URL = "https://bedrock-runtime.{region}.amazonaws.com/async-invoke/{arn}"


def _auth_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.aws_bearer_token_bedrock}",
    }


def verify_auth(model_id: str) -> None:
    """Smoke test the bearer token with a 1-token Claude call.

    Raises HTTPError immediately on 403 so expired tokens fail fast
    instead of dying after the 3-hour jitter sleep.
    """
    url = INVOKE_URL.format(region=settings.aws_region, model=model_id)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "ok"}],
    }
    resp = requests.post(url, json=body, headers=_auth_headers(), timeout=15)
    if not resp.ok:
        log.error("Bedrock auth preflight FAILED %s: %s", resp.status_code, resp.text)
        resp.raise_for_status()
    log.info("Bedrock auth preflight OK")


def invoke_claude(model_id: str, prompt: str, max_tokens: int = 2048) -> str:
    """Call a Claude model on Bedrock and return the response text."""
    url = INVOKE_URL.format(region=settings.aws_region, model=model_id)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = requests.post(url, json=body, headers=_auth_headers(), timeout=60)
    if not resp.ok:
        log.error("Bedrock Claude returned %s: %s", resp.status_code, resp.text)
        resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def invoke_model(model_id: str, body: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    """Call any Bedrock model with a raw body (used by Nova Canvas)."""
    url = INVOKE_URL.format(region=settings.aws_region, model=model_id)
    resp = requests.post(url, json=body, headers=_auth_headers(), timeout=timeout)
    if not resp.ok:
        log.error("Bedrock %s returned %s: %s", model_id, resp.status_code, resp.text)
        resp.raise_for_status()
    return resp.json()


def start_async_invocation(model_id: str, body: dict[str, Any]) -> str:
    """Start an async Bedrock job (used by Nova Reel) and return the invocation ARN."""
    url = ASYNC_INVOKE_URL.format(region=settings.aws_region, model=model_id)
    resp = requests.post(url, json=body, headers=_auth_headers(), timeout=60)
    if not resp.ok:
        log.error("Bedrock async %s returned %s: %s", model_id, resp.status_code, resp.text)
        resp.raise_for_status()
    return resp.json()["invocationArn"]


def get_async_invocation_status(invocation_arn: str) -> dict[str, Any]:
    """Poll the status of an async Bedrock job."""
    url = ASYNC_STATUS_URL.format(region=settings.aws_region, arn=invocation_arn)
    resp = requests.get(url, headers=_auth_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_json(raw: str) -> Any:
    """Extract JSON from a Claude response, stripping markdown code fences."""
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
    if match:
        raw = match.group(1).strip()
    return json.loads(raw)
