#!/usr/bin/env python3
"""Local smoke: Qwen chat + Qwen embeddings + Qdrant + Cognee add/search.

Run from gate/ with the venv active. Uses DashScope directly.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

GATE = Path(__file__).resolve().parent
load_dotenv(GATE / ".env")
os.environ["DATA_ROOT_DIRECTORY"] = str(GATE / ".cognee_data")
os.environ["SYSTEM_ROOT_DIRECTORY"] = str(GATE / ".cognee_system")

QWEN_BASE = os.environ["LLM_ENDPOINT"]
QWEN_KEY = os.environ["LLM_API_KEY"]
LLM_MODEL = os.environ["LLM_MODEL"].removeprefix("openai/")
EMB_MODEL = os.environ["EMBEDDING_MODEL"]
QDRANT_URL = os.environ.get("VECTOR_DB_URL", "http://localhost:6333")


def _client() -> OpenAI:
    return OpenAI(api_key=QWEN_KEY, base_url=QWEN_BASE)


def check_qwen_chat() -> None:
    r = _client().chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": "Reply with the single word: pong"}],
        max_tokens=16,
    )
    text = (r.choices[0].message.content or "").strip()
    print(f"qwen-chat: ok ({LLM_MODEL}) -> {text!r}")


def check_qwen_embed() -> None:
    r = _client().embeddings.create(model=EMB_MODEL, input="settled decision")
    dim = len(r.data[0].embedding)
    expected = int(os.environ.get("EMBEDDING_DIMENSIONS", "0"))
    if expected and dim != expected:
        raise SystemExit(f"qwen-embed: got dim {dim}, expected {expected}")
    print(f"qwen-embed: ok ({EMB_MODEL}) dim={dim}")


def check_qdrant() -> None:
    import urllib.request

    with urllib.request.urlopen(f"{QDRANT_URL}/readyz", timeout=5) as resp:
        body = resp.read().decode()
    if resp.status != 200:
        raise SystemExit(f"qdrant: HTTP {resp.status} {body}")
    print(f"qdrant: ok ({QDRANT_URL})")


async def check_cognee() -> None:
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
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    await cognee.add(
        "On 3 August the team decided to use Qdrant as the vector store. "
        "On 10 August that decision was superseded: stay on Qdrant, do not reopen LanceDB."
    )
    await cognee.cognify()
    results = await cognee.search("What did we decide about the vector store?")
    preview = str(results)[:400]
    print(f"cognee: ok search -> {preview}")


def main() -> None:
    steps = sys.argv[1:] or ["chat", "embed", "qdrant", "cognee"]
    if "chat" in steps:
        check_qwen_chat()
    if "embed" in steps:
        check_qwen_embed()
    if "qdrant" in steps:
        check_qdrant()
    if "cognee" in steps:
        asyncio.run(check_cognee())


if __name__ == "__main__":
    main()
