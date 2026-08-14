# Greenlit

**Every signed AI-tool approval makes the next one faster.**

A new request lands in Slack: *Can Product use Replit for internal
prototypes?* Greenlit retrieves similar signed approvals, carries forward
the org controls that still apply, and names only the genuine vendor gaps.
Specialist agents disagree in the open. Deterministic code compiles a
versioned draft. A human signs. That record is memory for the next tool.

> Agents can recommend. They cannot greenlight.

Cognee × Qdrant hack night — Berlin, 14 August 2026.

## What you will see

The synthetic corpus has two signed priors (**Cursor**, **Notion AI**) and one
new **Replit** request. Five org controls inherit. Two vendor facts do not: a
Replit DPA, and proof the vendor does not keep our code. A Challenger blocks
treating Notion as code-retention evidence.

Slack is the discussion surface. A focused web screen holds gaps, human
sign-off, and the hashed audit trail. There is no generic query box.

## Stack

| Layer | Role |
|---|---|
| Slack | Human discussion and evidence |
| Qdrant | Similar prior approvals (not LanceDB) |
| Cognee | Tool → vendor → control → signer → decision |
| Qwen (`qwen-flash` + `text-embedding-v3` via DashScope intl) | Specialist envelopes |
| Compiler | JSON Schema + content hash. No LLM. |
| Web sign-off | Humans activate. Status `signed` is not an agent output. |

## Local setup

1. Docker: run Qdrant on `:6333` (this repo expects a container named
   `qdrant-memory`).
2. Copy `.env.example` to `.env` and add a DashScope international key.
3. Python 3.12 venv, then `pip install -r requirements.txt`.
4. `python ingest.py` — corpus into Cognee + Qdrant. Then
   `python retrieve.py "Replit internal prototypes"` — Cursor should rank
   above Notion.
5. `python serve.py` — approval screen at http://127.0.0.1:8765/
   Legal sign moves only the DPA chip. `POST /demo/reset` between takes.

`python smoke.py` still checks chat, embeddings, Qdrant, and a tiny Cognee
round-trip. `EMBEDDING_BATCH_SIZE` must stay `10` (DashScope cap). Import
`cognee_community_vector_adapter_qdrant.register` as a **module** for
side-effect registration — do not call `register()`.

## Honest scope

Greenlit supports an audit-ready approval workflow. It does not certify that
an organization is legally compliant. Required humans stay accountable.
