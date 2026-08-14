#!/usr/bin/env python3
"""Retrieve similar prior approvals (Qdrant) and graph context (Cognee).

Run from the repo root:  python retrieve.py "Replit internal prototypes"
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

GATE = Path(__file__).resolve().parent
load_dotenv(GATE / ".env")
os.environ["DATA_ROOT_DIRECTORY"] = str(GATE / ".cognee_data")
os.environ["SYSTEM_ROOT_DIRECTORY"] = str(GATE / ".cognee_system")

QWEN_BASE = os.environ["LLM_ENDPOINT"]
EMB_MODEL = os.environ["EMBEDDING_MODEL"]
EMB_KEY = os.environ["EMBEDDING_API_KEY"]
QDRANT_URL = os.environ.get("VECTOR_DB_URL", "http://localhost:6333")
COLLECTION = "DocumentChunk_text"
NAMED_VECTOR = "text"
TOP_K = 8
DEFAULT_QUERY = "Replit internal prototypes"


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


def _with_backoff_sync(label: str, fn, *args, **kwargs):
    delays = (5, 15, 45, 90, 120)
    last: BaseException | None = None
    for attempt, delay in enumerate((0, *delays), start=1):
        if delay:
            print(f"{label}: rate-limit/backoff, sleep {delay}s (attempt {attempt})")
            time.sleep(delay)
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last = exc
            if _is_rate_limit(exc) and attempt <= len(delays):
                print(f"{label}: {exc}")
                continue
            raise
    raise last  # pragma: no cover


async def _with_backoff(label: str, fn, *args, **kwargs):
    delays = (5, 15, 45, 90, 120)
    last: BaseException | None = None
    for attempt, delay in enumerate((0, *delays), start=1):
        if delay:
            print(f"{label}: rate-limit/backoff, sleep {delay}s (attempt {attempt})")
            time.sleep(delay)
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last = exc
            if _is_rate_limit(exc) and attempt <= len(delays):
                print(f"{label}: {exc}")
                continue
            raise
    raise last  # pragma: no cover


def guess_tool(text: str) -> str:
    """Guess which corpus thread a chunk came from.

    Notion's thread mentions Cursor, so check Notion and Replit first.
    """
    lower = text.lower()
    if "t-replit" in lower or "tool: replit" in lower or "use replit" in lower:
        return "Replit"
    if (
        "t-notion" in lower
        or "notion ai" in lower
        or "notion labs" in lower
        or "tool: notion" in lower
    ):
        return "Notion"
    if "t-cursor" in lower or "anysphere" in lower or "tool: cursor" in lower:
        return "Cursor"
    if "replit" in lower:
        return "Replit"
    if "notion" in lower:
        return "Notion"
    if "cursor" in lower:
        return "Cursor"
    return "unknown"


def embed_query(query: str) -> list[float]:
    client = OpenAI(api_key=EMB_KEY, base_url=QWEN_BASE)

    def _call() -> list[float]:
        r = client.embeddings.create(model=EMB_MODEL, input=query)
        vec = r.data[0].embedding
        expected = int(os.environ.get("EMBEDDING_DIMENSIONS", "0"))
        if expected and len(vec) != expected:
            raise SystemExit(f"embed: got dim {len(vec)}, expected {expected}")
        return vec

    return _with_backoff_sync("embed", _call)


def search_qdrant(query: str) -> list[dict]:
    vector = embed_query(query)
    qdrant = QdrantClient(url=QDRANT_URL)
    result = qdrant.query_points(
        collection_name=COLLECTION,
        query=vector,
        using=NAMED_VECTOR,
        limit=TOP_K,
        with_payload=True,
    )
    hits: list[dict] = []
    for point in result.points:
        payload = point.payload or {}
        text = str(payload.get("text") or "")
        preview = " ".join(text.split())
        if len(preview) > 280:
            preview = preview[:277] + "..."
        hits.append(
            {
                "score": float(point.score),
                "preview": preview,
                "tool_guess": guess_tool(text),
            }
        )
    return hits


def print_qdrant(hits: list[dict]) -> None:
    print()
    print("=== A) Qdrant similar chunks (DocumentChunk_text / vector=text) ===")
    if not hits:
        print("(no hits)")
        return
    for i, hit in enumerate(hits, start=1):
        print(
            f"{i}. score={hit['score']:.6f}  tool={hit['tool_guess']}\n"
            f"   {hit['preview']}"
        )


def ranking_ok(hits: list[dict]) -> tuple[bool, str]:
    """Among prior-approval chunks, Cursor must rank above Notion."""
    cursor_best: float | None = None
    notion_best: float | None = None
    for hit in hits:
        guess = hit["tool_guess"]
        score = hit["score"]
        if guess == "Cursor" and (cursor_best is None or score > cursor_best):
            cursor_best = score
        elif guess == "Notion" and (notion_best is None or score > notion_best):
            notion_best = score
    if cursor_best is None:
        return False, "no Cursor chunk in top hits"
    if notion_best is None:
        return True, f"Cursor={cursor_best:.6f}; Notion not in top hits"
    if cursor_best > notion_best:
        return True, f"Cursor={cursor_best:.6f} > Notion={notion_best:.6f}"
    return False, f"Cursor={cursor_best:.6f} <= Notion={notion_best:.6f}"


def _preview_search(results) -> str:
    chunks: list[str] = []
    for item in results or []:
        payload = getattr(item, "search_result", item)
        chunks.append(str(payload))
    text = "\n".join(chunks) if chunks else str(results)
    return text if len(text) <= 800 else text[:797] + "..."


async def search_cognee(query: str) -> str:
    os.chdir(GATE)
    from cognee_community_vector_adapter_qdrant import register as _qdrant_register  # noqa: F401
    import cognee
    from cognee import config
    from cognee.modules.search.types import SearchType

    config.set_vector_db_config(
        {
            "vector_db_provider": "qdrant",
            "vector_db_url": QDRANT_URL,
            "vector_db_key": os.environ.get("VECTOR_DB_KEY", ""),
        }
    )

    chunks = await _with_backoff(
        "cognee.search CHUNKS",
        cognee.search,
        query_text=query,
        query_type=SearchType.CHUNKS,
        top_k=8,
    )
    graph = await _with_backoff(
        "cognee.search GRAPH_COMPLETION",
        cognee.search,
        query_text=query,
        query_type=SearchType.GRAPH_COMPLETION,
        top_k=8,
    )
    preview = (
        "CHUNKS:\n"
        + _preview_search(chunks)
        + "\n\nGRAPH_COMPLETION:\n"
        + _preview_search(graph)
    )
    print()
    print("=== B) Cognee graph search ===")
    print(preview)
    return preview


async def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or DEFAULT_QUERY
    print(f"query: {query!r}")

    hits = search_qdrant(query)
    print_qdrant(hits)
    ok, evidence = ranking_ok(hits)
    print()
    print(f"ranking (Cursor vs Notion priors): {'PASS' if ok else 'FAIL'} — {evidence}")

    cognee_preview = await search_cognee(query)

    export = {
        "query": query,
        "qdrant": hits,
        "cognee_preview": cognee_preview,
    }
    demo_dir = GATE / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    out_path = demo_dir / "retrieve_replit.json"
    out_path.write_text(json.dumps(export, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print()
    print("=== JSON ===")
    print(json.dumps(export, indent=2, ensure_ascii=False))
    print(f"wrote {out_path}")

    if not ok:
        print("RANKING_FAIL: Cursor did not rank above Notion. Ranked list above is live, unboosted.")
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
