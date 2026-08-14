# Greenlit

**Every signed AI-tool approval makes the next one faster.**

Teams re-approve every new AI tool from scratch because the last DPA is buried in Slack. Greenlit turns a Slack request into a signed, reusable record: org checks that still apply are carried forward; only genuine vendor gaps stay open.

> Agents can recommend. They cannot greenlight.

Cognee × Qdrant hack night — Berlin, 14 August 2026.

## The question

```
@Greenlit I want to use Replit for internal prototypes. Can you help with the approval?
```

Keyword search for “DPA” or “approval” returns **Cursor** and **Notion AI** as if they were interchangeable. The real question is which of seven controls transfer to a new vendor. Org rules may inherit. A Notion DPA cannot prove Replit code retention. Keyword match cannot tell those relations apart.

## What you will see

Synthetic corpus: two signed priors (Cursor, Notion AI) and one new Replit request.

1. **Five green / two pink chips.** Company checks already covered. Still missing: a Replit DPA (Legal) and proof Replit does not keep our code (Security).
2. **Qdrant** ranks similar prior approvals — Cursor above Notion on this request.
3. **Cognee** keeps tool → vendor → control → evidence → signer → decision. Similar is not the same vendor.
4. **Challenger** blocks copying Notion’s DPA onto Replit.
5. **Legal can sign the DPA.** Status stays `blocked` until Security has evidence. Agents cannot set `signed`.

Slack is the discussion surface. The web screen is accountability. There is no generic query box.

## Stack

| Layer | Role |
|---|---|
| Slack | Human discussion (optional live bot) |
| Qdrant | Similar prior approvals |
| Cognee | Provenance graph |
| Qwen | Specialist JSON envelopes |
| Compiler | JSON Schema + content hash. No LLM. |
| Web sign-off | Humans activate |

## Run locally

Needs Python 3.12, Docker, and an OpenAI-compatible Qwen key (chat + embeddings). Embedding batch size must stay `10`.

```bash
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
cp .env.example .env   # fill LLM_API_KEY and EMBEDDING_API_KEY
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python ingest.py
python retrieve.py "Replit internal prototypes"   # Cursor should rank above Notion
python serve.py                                   # http://127.0.0.1:8765/
```

Import `cognee_community_vector_adapter_qdrant.register` as a **module** (side-effect registration). Do not call `register()`. Do not use the default LanceDB backend.

Open http://127.0.0.1:8765/?role=Legal — Sign moves only the DPA chip. `POST /demo/reset` between takes.

Optional Slack: fill `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, and `SLACK_APP_TOKEN` in `.env`, then `python slack_bot.py`. Mention the bot with the Replit sentence above.

`python smoke.py` checks chat, embeddings, Qdrant, and a small Cognee round-trip.

## Honest scope

Greenlit supports an audit-ready approval workflow. It does not certify that an organization is legally compliant. Required humans stay accountable.
