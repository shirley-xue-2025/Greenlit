# Agent notes — Greenlit (public repo)

This repository is public. Do not commit `.env`, local Cognee or Qdrant
data, Slack live-thread pointers, or competition paste.

## Stack

- LLM and embeddings: Qwen via an OpenAI-compatible endpoint in `.env`.
- Vector store: Qdrant at `VECTOR_DB_URL` (default `http://localhost:6333`).
  Import `cognee_community_vector_adapter_qdrant.register` as a **module**.
  Do not call `register()`. Do not use default LanceDB.
- `EMBEDDING_BATCH_SIZE=10` or graph-edge indexing fails.

## Product

- Slack is discussion; the web surface is accountability. No query box.
- Agents recommend. The compiler hashes. Only humans set `status=signed`.
- Synthetic Slack corpus only. No company Slack exports.
- `corpus/controls.json` owns the 5/2 split for the Replit demo.

## Do not commit

`.env`, `.venv/`, `.cognee_data/`, `.cognee_system/`, `qdrant_storage/`,
`demo/state.json`, `demo/live_slack.json`.
