#!/usr/bin/env python3
"""Ingest the three Greenlit corpus threads into Cognee + Qdrant.

Run from the repo root:  python ingest.py
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

GATE = Path(__file__).resolve().parent
load_dotenv(GATE / ".env")
os.environ["DATA_ROOT_DIRECTORY"] = str(GATE / ".cognee_data")
os.environ["SYSTEM_ROOT_DIRECTORY"] = str(GATE / ".cognee_system")

QDRANT_URL = os.environ.get("VECTOR_DB_URL", "http://localhost:6333")

CORPUS_FILES = (
    GATE / "corpus" / "cursor-approval.json",
    GATE / "corpus" / "notion-approval.json",
    GATE / "corpus" / "replit-request.json",
)


def render_thread(payload: dict) -> str:
    """Turn a corpus JSON thread into readable prose (not minified JSON)."""
    tool = payload.get("tool", "unknown tool")
    vendor = payload.get("vendor", "unknown vendor")
    decision = payload.get("decision", "unknown")
    thread_id = payload.get("id", "")
    signed_at = payload.get("signed_at")
    signers = payload.get("signers") or []
    trigger = payload.get("trigger")
    messages = payload.get("messages") or []

    lines = [
        f"AI-tool approval thread {thread_id}.".strip(),
        f"Tool: {tool}.",
        f"Vendor: {vendor}.",
        f"Decision: {decision}.",
    ]
    if signed_at:
        lines.append(f"Signed at: {signed_at}.")
    else:
        lines.append("Not signed.")
    if signers:
        lines.append("Signers: " + "; ".join(signers) + ".")
    if trigger:
        lines.append(f"Request: {trigger}")
    lines.append("Dated discussion:")
    for msg in messages:
        speaker = msg.get("user", "Unknown")
        role = msg.get("role", "")
        ts = msg.get("ts", "")
        text = msg.get("text", "")
        who = f"{speaker} ({role})" if role else speaker
        lines.append(f"{ts} {who}: {text}")
    return "\n".join(lines)


def _is_rate_limit(exc: BaseException) -> bool:
    text = str(exc).lower()
    markers = (
        "429",
        "rate limit",
        "ratelimit",
        "too many requests",
        "throttl",
        "quota",
    )
    return any(m in text for m in markers)


async def _with_backoff(label: str, fn, *args, **kwargs):
    delays = (5, 15, 45, 90, 120)
    last: BaseException | None = None
    for attempt, delay in enumerate((0, *delays), start=1):
        if delay:
            print(f"{label}: rate-limit/backoff, sleep {delay}s (attempt {attempt})")
            time.sleep(delay)
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — cognify wraps provider errors
            last = exc
            if _is_rate_limit(exc) and attempt <= len(delays):
                print(f"{label}: {exc}")
                continue
            raise
    raise last  # pragma: no cover


async def main() -> None:
    os.chdir(GATE)
    # Side-effect import: adapter registers "qdrant" on load. register is a
    # module, not a function — do not call it.
    from cognee_community_vector_adapter_qdrant import register as _qdrant_register  # noqa: F401
    import cognee
    from cognee import config

    config.set_vector_db_config(
        {
            "vector_db_provider": "qdrant",
            "vector_db_url": QDRANT_URL,
            "vector_db_key": os.environ.get("VECTOR_DB_KEY", ""),
        }
    )

    print("prune: previous smoke/cognify data")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    for path in CORPUS_FILES:
        payload = json.loads(path.read_text(encoding="utf-8"))
        prose = render_thread(payload)
        print(f"add: {path.name} ({payload.get('tool')}, {len(prose)} chars)")
        await _with_backoff(f"add {path.name}", cognee.add, prose)

    print("cognify: extracting graph (this can take several minutes)")
    await _with_backoff("cognify", cognee.cognify)

    web_dir = GATE / "web"
    web_dir.mkdir(parents=True, exist_ok=True)
    graph_path = web_dir / "graph.html"
    print(f"visualize: {graph_path}")
    await _with_backoff(
        "visualize_graph",
        cognee.visualize_graph,
        destination_file_path=str(graph_path),
        query="Replit internal prototypes",
    )
    if not graph_path.is_file():
        raise SystemExit(f"graph.html missing at {graph_path}")
    print(f"ingest: ok -> {graph_path} ({graph_path.stat().st_size} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
