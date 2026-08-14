# Agent notes — Greenlit (public repo)

This git repo is **public**. Session handover, spoken lines, Devpost drafts,
and personal notes live in the parent hub and must never be committed here.

## Stack rules

- LLM: Qwen via DashScope intl
  (`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`). Personal key in
  `.env` (gitignored).
- Vector store: local Qdrant (`qdrant-memory` on `:6333`). Import
  `cognee_community_vector_adapter_qdrant.register` as a **module**. Do not
  call `register()`. Do not demo default LanceDB.
- `EMBEDDING_BATCH_SIZE=10` or cognify fails on graph-edge indexing.
- After a reboot: start Docker Desktop, then `docker start qdrant-memory`.
  Smoke: `python smoke.py`.

## Product rules

- Slack is discussion; the web surface is accountability. No generic query box.
- Agents recommend. The compiler hashes. Only humans set `status=signed`.
- Synthetic Slack corpus only. No company Slack exports.
- Catalog in `corpus/controls.json` owns the 5/2 split for the Replit demo.

## Do not commit

`.env`, `.venv/`, `.cognee_data/`, `.cognee_system/`, `qdrant_storage/`,
and anything from the parent hub (`STATUS.md`, `BUILD_PLAN.md`, spoken lines).
