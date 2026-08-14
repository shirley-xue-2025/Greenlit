#!/usr/bin/env python3
"""Greenlit Slack bot — Socket Mode, app_mention only.

Golden Replit request replies from cache. After Legal signs on the
dashboard, post_legal_signed() sends one follow-up in that thread.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

GATE = Path(__file__).resolve().parent
load_dotenv(GATE / ".env")

LIVE_PATH = GATE / "demo" / "live_slack.json"
DASHBOARD_URL = os.environ.get("GREENLIT_DASHBOARD_URL", "http://127.0.0.1:8765/")

GOLDEN_TEXT = (
    "I've opened the Replit approval. You cannot start using it yet.\n\n"
    "The usual checks are already covered — company login, internal use only, "
    "no customer data in prompts. You don't need to re-explain those.\n\n"
    "Still missing, and not yours: Legal needs a signed privacy contract with "
    "Replit, and Security needs proof they do not keep our code.\n\n"
    "You don't need to upload or sign anything."
)
SIGN_FOLLOWUP = (
    "Legal (Priya Chen) signed Replit's privacy contract. You still cannot use Replit — "
    "Security (Jonas Weber) still needs proof they do not keep our code."
)
BUTTON_TEXT = "See my request"
OPEN_ACTION_ID = "open_dashboard"
LEGAL_BUTTON = "Open as Legal"
LEGAL_ACTION_ID = "open_as_legal"
LEGAL_ROUTE_TEXT = (
    "Legal · @Priya Chen — Shirley Xue (Product) asked to start a Replit approval. "
    "Your piece is Replit's privacy contract.\n\n"
    "Similar threads: Cursor (coding tool, you signed in May) and Notion AI "
    "(not a coding tool, you signed in June). Those contracts are not interchangeable.\n\n"
    "Legal recommendation: you can sign this privacy contract. Do not copy Notion. "
    "Proof they do not keep our code stays with Security (Jonas Weber)."
)
SECURITY_BUTTON = "Open as Security"
SECURITY_ACTION_ID = "open_as_security"
SECURITY_ROUTE_TEXT = (
    "Security · @Jonas Weber — Shirley Xue (Product) asked to start a Replit approval. "
    "Your piece is proof they do not keep our code.\n\n"
    "From earlier threads: you required that on Cursor. Notion is not "
    "a coding tool — its privacy contract cannot prove this. Those facts are not interchangeable.\n\n"
    "Security recommendation: a signature will not close this. Evidence is still "
    "missing. The privacy contract stays with Legal (Priya Chen)."
)


def is_replit_demo(text: str) -> bool:
    lowered = _plain_text(text).lower()
    return "replit" in lowered and "prototype" in lowered


def _plain_text(text: str) -> str:
    return re.sub(r"<@[^>]+>", "", text or "").strip()


def _assert_no_hash(text: str) -> None:
    if "#" in text:
        raise ValueError("Slack body copy must not contain # (it becomes a channel).")


def _mention(user_id: str | None) -> str:
    if not user_id:
        return ""
    return f"<@{user_id}> "


def build_reply(
    *,
    golden: bool,
    inherited_n: int,
    gaps_n: int,
    requester_id: str | None = None,
) -> tuple[str, list[dict]]:
    if golden:
        body = GOLDEN_TEXT
    else:
        body = (
            f"I've opened this approval. You cannot start using it yet. "
            f"{inherited_n} usual checks are already covered. "
            f"{gaps_n} things still need Legal or Security.\n\n"
            "You don't need to upload or sign anything."
        )
    text = _mention(requester_id) + body
    _assert_no_hash(text)
    request_url = DASHBOARD_URL.rstrip("/") + "/?role=Employee"
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": text},
        },
        {
            "type": "actions",
            "block_id": "open_greenlit",
            "elements": [
                {
                    "type": "button",
                    "action_id": OPEN_ACTION_ID,
                    "text": {"type": "plain_text", "text": BUTTON_TEXT},
                    "url": request_url,
                    "style": "primary",
                }
            ],
        },
    ]
    return text, blocks


def build_legal_route() -> tuple[str, list[dict]]:
    text = LEGAL_ROUTE_TEXT
    _assert_no_hash(text)
    url = DASHBOARD_URL.rstrip("/") + "/?role=Legal"
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": text},
        },
        {
            "type": "actions",
            "block_id": "open_as_legal",
            "elements": [
                {
                    "type": "button",
                    "action_id": LEGAL_ACTION_ID,
                    "text": {"type": "plain_text", "text": LEGAL_BUTTON},
                    "url": url,
                    "style": "primary",
                }
            ],
        },
    ]
    return text, blocks


def build_security_route() -> tuple[str, list[dict]]:
    text = SECURITY_ROUTE_TEXT
    _assert_no_hash(text)
    url = DASHBOARD_URL.rstrip("/") + "/?role=Security"
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": text},
        },
        {
            "type": "actions",
            "block_id": "open_as_security",
            "elements": [
                {
                    "type": "button",
                    "action_id": SECURITY_ACTION_ID,
                    "text": {"type": "plain_text", "text": SECURITY_BUTTON},
                    "url": url,
                    "style": "primary",
                }
            ],
        },
    ]
    return text, blocks


def remember_thread(channel: str, thread_ts: str, requester_id: str | None = None) -> None:
    LIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_live() or {}
    payload = {
        "channel": channel,
        "thread_ts": thread_ts,
        "posted_sign": False,
    }
    rid = requester_id or existing.get("requester_id")
    if rid:
        payload["requester_id"] = rid
    LIVE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_live() -> dict | None:
    if not LIVE_PATH.is_file():
        return None
    try:
        data = json.loads(LIVE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if not data.get("channel") or not data.get("thread_ts"):
        return None
    return data


def _save_live(data: dict) -> None:
    LIVE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def reset_sign_flag() -> None:
    data = _load_live()
    if not data:
        return
    data["posted_sign"] = False
    _save_live(data)


def post_legal_signed() -> bool:
    """One write-back after Legal signs. Safe to call when Slack is off."""
    token = (os.environ.get("SLACK_BOT_TOKEN") or "").strip()
    if not token:
        return False
    data = _load_live()
    if not data or data.get("posted_sign"):
        return False
    follow = _mention(data.get("requester_id")) + SIGN_FOLLOWUP
    _assert_no_hash(follow)
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    client = WebClient(token=token)
    try:
        _post_in_thread(client, data["channel"], data["thread_ts"], text=follow)
    except SlackApiError as exc:
        print(f"slack write-back failed: {exc.response.get('error')}", file=sys.stderr)
        return False
    data["posted_sign"] = True
    _save_live(data)
    return True


def _live_counts(request_text: str) -> tuple[int, int]:
    from agents import run_agents

    envelopes = run_agents(request_text)
    first = envelopes[0] if envelopes else {}
    inherited = first.get("inherited") or []
    gaps = first.get("gaps") or []
    return len(inherited), len(gaps)


def _web() -> "object":
    from slack_sdk import WebClient

    token = (os.environ.get("SLACK_BOT_TOKEN") or "").strip()
    return WebClient(token=token)


def _post_in_thread(client, channel: str, thread_ts: str, *, text: str, blocks=None) -> None:
    """Reply in the request thread only. Never also-send to the channel."""
    kwargs = {
        "channel": channel,
        "thread_ts": thread_ts,
        "text": text,
        "reply_broadcast": False,
    }
    if blocks is not None:
        kwargs["blocks"] = blocks
    client.chat_postMessage(**kwargs)


def _thread_action_ids(client, channel: str, thread_ts: str) -> set[str]:
    from slack_sdk.errors import SlackApiError

    ids: set[str] = set()
    try:
        resp = client.conversations_replies(channel=channel, ts=thread_ts, limit=50)
    except SlackApiError:
        return ids
    for msg in resp.get("messages") or []:
        for block in msg.get("blocks") or []:
            for el in block.get("elements") or []:
                aid = el.get("action_id")
                if aid:
                    ids.add(str(aid))
    return ids


def respond_to_mention(
    channel: str,
    thread_ts: str,
    text: str,
    bot_user_id: str,
    requester_id: str | None = None,
) -> bool:
    """Employee status, then Legal and Security. Shared by Socket Mode and the poller."""
    from slack_sdk.errors import SlackApiError

    client = _web()
    ids = _thread_action_ids(client, channel, thread_ts)
    posted = False
    golden = is_replit_demo(text)
    remember_thread(channel, thread_ts, requester_id=requester_id)

    if OPEN_ACTION_ID not in ids:
        if golden:
            inherited_n, gaps_n = 5, 2
        else:
            inherited_n, gaps_n = _live_counts(_plain_text(text))
        fallback, blocks = build_reply(
            golden=golden,
            inherited_n=inherited_n,
            gaps_n=gaps_n,
            requester_id=requester_id,
        )
        try:
            _post_in_thread(
                client, channel, thread_ts, text=fallback, blocks=blocks
            )
        except SlackApiError as exc:
            print(f"mention reply failed: {exc.response.get('error')}", file=sys.stderr)
            return False
        posted = True
        print(f"employee reply in {channel} ts={thread_ts} golden={golden}", flush=True)

    if LEGAL_ACTION_ID not in ids:
        if not _load_live():
            remember_thread(channel, thread_ts)
        route_text, route_blocks = build_legal_route()
        try:
            _post_in_thread(
                client, channel, thread_ts, text=route_text, blocks=route_blocks
            )
        except SlackApiError as exc:
            print(f"legal route failed: {exc.response.get('error')}", file=sys.stderr)
            return posted
        posted = True
        print(f"legal route in {channel} ts={thread_ts}", flush=True)

    if SECURITY_ACTION_ID not in ids:
        if not _load_live():
            remember_thread(channel, thread_ts)
        route_text, route_blocks = build_security_route()
        try:
            _post_in_thread(
                client, channel, thread_ts, text=route_text, blocks=route_blocks
            )
        except SlackApiError as exc:
            print(f"security route failed: {exc.response.get('error')}", file=sys.stderr)
            return posted
        posted = True
        print(f"security route in {channel} ts={thread_ts}", flush=True)

    return posted


def _poll_once(bot_user_id: str, channel_id: str) -> None:
    from slack_sdk.errors import SlackApiError

    client = _web()
    try:
        hist = client.conversations_history(channel=channel_id, limit=10)
    except SlackApiError as exc:
        print(f"poll history failed: {exc.response.get('error')}", file=sys.stderr)
        return
    mention = f"<@{bot_user_id}>"
    for msg in hist.get("messages") or []:
        if msg.get("user") == bot_user_id:
            continue
        text = msg.get("text") or ""
        if mention not in text:
            continue
        ts = msg.get("thread_ts") or msg["ts"]
        respond_to_mention(
            msg["channel"] if msg.get("channel") else channel_id,
            ts,
            text,
            bot_user_id,
            requester_id=msg.get("user"),
        )


def _ai_tools_channel() -> str | None:
    from slack_sdk.errors import SlackApiError

    client = _web()
    try:
        conv = client.users_conversations(types="public_channel", limit=100)
    except SlackApiError as exc:
        print(f"channel list failed: {exc.response.get('error')}", file=sys.stderr)
        return None
    for ch in conv.get("channels") or []:
        if ch.get("name") == "ai-tools":
            return ch.get("id")
    return None


async def _run() -> None:
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    from slack_bolt.async_app import AsyncApp

    bot_token = (os.environ.get("SLACK_BOT_TOKEN") or "").strip()
    signing_secret = (os.environ.get("SLACK_SIGNING_SECRET") or "").strip()
    app_token = (os.environ.get("SLACK_APP_TOKEN") or "").strip()
    missing = [
        name
        for name, val in (
            ("SLACK_BOT_TOKEN", bot_token),
            ("SLACK_SIGNING_SECRET", signing_secret),
            ("SLACK_APP_TOKEN", app_token),
        )
        if not val
    ]
    if missing:
        raise SystemExit(f"Missing Slack secrets: {', '.join(missing)}")

    auth = _web().auth_test()
    bot_user_id = auth["user_id"]
    channel_id = _ai_tools_channel()

    app = AsyncApp(token=bot_token, signing_secret=signing_secret)

    @app.event("app_mention")
    async def handle_mention(event, say):  # noqa: ARG001 — say unused; WebClient posts
        channel = event["channel"]
        thread_ts = event.get("thread_ts") or event["ts"]
        text = event.get("text") or ""
        print(f"socket mention {channel} ts={thread_ts}", flush=True)
        await asyncio.to_thread(
            respond_to_mention,
            channel,
            thread_ts,
            text,
            bot_user_id,
            event.get("user"),
        )

    @app.action(OPEN_ACTION_ID)
    async def ack_open(ack):
        await ack()

    @app.action(LEGAL_ACTION_ID)
    async def ack_legal(ack):
        await ack()

    @app.action(SECURITY_ACTION_ID)
    async def ack_security(ack):
        await ack()

    async def poll_loop() -> None:
        if not channel_id:
            print("poller off: #ai-tools not found", flush=True)
            return
        print(f"poller on #ai-tools {channel_id}", flush=True)
        while True:
            try:
                await asyncio.to_thread(_poll_once, bot_user_id, channel_id)
            except Exception as exc:  # noqa: BLE001
                print(f"poller: {exc}", file=sys.stderr)
            await asyncio.sleep(2)

    handler = AsyncSocketModeHandler(app, app_token)
    poll_task = asyncio.create_task(poll_loop())
    print("Greenlit Slack bot listening (Socket Mode + poller).", flush=True)
    try:
        await handler.start_async()
    finally:
        poll_task.cancel()


if __name__ == "__main__":
    asyncio.run(_run())
