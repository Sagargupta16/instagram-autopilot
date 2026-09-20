"""Publish at most one due slot per tick, with durable receipts and truthful outcomes."""

from __future__ import annotations

import argparse
import logging
import random
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from src.adapters import bedrock, cloudinary_host, composio
from src.content.caption import generate_caption
from src.content.dedup import record_post
from src.content.topic import generate_topic_brief
from src.flows.carousel_flow import post_carousel
from src.flows.image_flow import post_image
from src.flows.reel_flow import post_reel
from src.pillar import load_config
from src.run_report import write_summary
from src.schedule import SlotPlan, plan_today
from src.settings import settings
from src.state.factory import create_ledger
from src.state.history import sync_history
from src.state.ledger import MAX_ATTEMPTS, Ledger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def _preflight_all_auth(text_model_id: str, *, dry_run: bool = False) -> None:
    bedrock.verify_auth(text_model_id)
    if not dry_run:
        composio.verify_auth()
        cloudinary_host.verify_auth()


def _run_slot(
    slot: SlotPlan,
    config: dict[str, Any],
    *,
    dry_run: bool,
    ledger: Ledger | None = None,
    key: str = "",
    clock: Callable[[], datetime] | None = None,
) -> str | None:
    current = clock or (lambda: datetime.now(UTC))
    brief = generate_topic_brief(slot.pillar, random.choice(settings.content_type_list))
    content = generate_caption(
        brief["topic"], slot.pillar, config["persona"], sources=brief.get("sources", [])
    )
    content["sources"] = brief.get("sources", [])
    caption = content["caption"] + "\n\n" + content["hashtags"]
    log.info(
        "Content ready | topic: %s | slides: %d", brief["topic"], len(content["image_prompts"])
    )
    if ledger:
        ledger.remember(key, brief["topic"], content, current())
        record_post(brief["topic"], content["image_prompts"])

    def before_publish(container_id: str) -> None:
        instant = current().astimezone(UTC)
        window = config["cadence"]["window_utc"]
        if not window["start"] <= instant.strftime("%H:%M") < window["end"] or not key.startswith(
            instant.date().isoformat()
        ):
            raise RuntimeError("Posting window ended during generation; slot was not published")
        if ledger is None:
            raise RuntimeError("Publication requires a durable ledger")
        ledger.before_publish(key, container_id, instant)

    kwargs = {"dry_run": dry_run, "before_publish": None if dry_run else before_publish}
    image_model = config["models"]["image"]
    match slot.pillar.get("content_format", "carousel"):
        case "reel":
            return post_reel(content, caption, image_model, config["models"]["video"], **kwargs)
        case "image":
            return post_image(content, caption, image_model, **kwargs)
        case _:
            return post_carousel(content, caption, image_model, **kwargs)


def run(*, dry_run: bool = False, now: datetime | None = None) -> dict[str, Any]:
    if now is not None and now.tzinfo is None:
        raise ValueError("Scheduling requires a timezone-aware UTC time")
    clock = (lambda: now.astimezone(UTC)) if now else (lambda: datetime.now(UTC))
    current = clock()
    config = load_config()
    plan = plan_today(current.date(), config["cadence"], config["pillars"])
    window = config["cadence"]["window_utc"]
    candidates = [
        slot
        for slot in plan
        if not slot.skip
        and (
            dry_run or window["start"] <= slot.time_utc <= current.strftime("%H:%M") < window["end"]
        )
    ]
    if dry_run and not candidates:
        candidates = [SlotPlan(current.strftime("%H:%M"), config["pillars"][0], False)]
    if not candidates:
        result = {"status": "skipped", "reason": "No due slots inside today's posting window"}
        write_summary(result)
        return result
    ledger = None if dry_run else create_ledger()
    if ledger:
        sync_history(ledger)
        unresolved = [
            key
            for key, value in ledger.snapshot()["slots"].items()
            if value["status"] in {"publishing", "uncertain"}
        ]
        if unresolved:
            write_summary({"status": "needs_reconciliation", "slots": unresolved})
            raise RuntimeError("Publication requires reconciliation before another post")
    for slot in candidates:
        key = f"{current.date().isoformat()}|{slot.time_utc}|{slot.pillar['id']}"
        if ledger and not ledger.claim(
            key,
            current,
            min_gap_minutes=config["cadence"]["min_gap_minutes"],
            max_posts_per_day=config["cadence"]["max_posts_per_day"],
        ):
            continue
        try:
            cloudinary_host.configure()
            _preflight_all_auth(config["models"]["text"], dry_run=dry_run)
            media_id = _run_slot(slot, config, dry_run=dry_run, ledger=ledger, key=key, clock=clock)
            if ledger:
                ledger.complete(key, media_id, clock())
            result = {
                "status": "preview" if dry_run else "published",
                "slot": key,
                "media_id": media_id,
            }
            write_summary(result)
            return result
        except Exception as error:
            if ledger:
                ledger.fail(key, type(error).__name__, clock())
            write_summary({"status": "failed", "slot": key, "error": type(error).__name__})
            if dry_run:
                raise RuntimeError(
                    "Preview failed; see generation logs. Nothing was published."
                ) from error
            raise RuntimeError(
                f"Publication failed for {key}; inspect the durable receipt"
            ) from error
    exhausted = ledger and any(
        entry["status"] == "failed" and entry.get("attempts", 0) >= MAX_ATTEMPTS
        for key, entry in ledger.snapshot()["slots"].items()
        if key.startswith(current.date().isoformat())
    )
    if exhausted:
        write_summary({"status": "failed", "reason": "Daily slot retry budget exhausted"})
        raise RuntimeError("Publication failed: retry budget exhausted for today")
    result = {
        "status": "skipped",
        "reason": "Slots already handled, owned, or waiting for minimum gap",
    }
    write_summary(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Instagram Autopilot")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", action="store_true", help="Generate a local preview; no uploads or posts"
    )
    mode.add_argument(
        "--resolve-slot", help="Reconcile a slot after checking its outcome on Instagram"
    )
    resolution = parser.add_mutually_exclusive_group()
    resolution.add_argument("--media-id", help="Confirmed Instagram media ID for --resolve-slot")
    resolution.add_argument("--confirm-not-published", action="store_true")
    args = parser.parse_args()
    if args.resolve_slot:
        if not args.media_id and not args.confirm_not_published:
            parser.error("--resolve-slot requires --media-id or --confirm-not-published")
        create_ledger().resolve(args.resolve_slot, media_id=args.media_id, now=datetime.now(UTC))
        return
    if args.media_id or args.confirm_not_published:
        parser.error("Resolution options require --resolve-slot")
    try:
        run(dry_run=args.dry_run)
    except Exception as error:
        log.error("%s", error)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
