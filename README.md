# Greenlit

**Every signed AI-tool approval makes the next one faster.**

Teams start over every time someone asks for a new AI tool, because the last privacy contract is buried in Slack. Greenlit turns that Slack request into a signed record the next request can reuse: company checks that still apply are already covered; only what is new about this company stays open.

> The chatbot can recommend. It cannot approve.

Cognee × Qdrant hack night — Berlin, 14 August 2026.

## The question

```
@Greenlit I want to use Replit for internal prototypes. Can you help with the approval?
```

This is the third AI-tool request. Cursor already got a yes (a month of Slack, then saved). Notion already got a yes (days, not a month — people still pasted terms). Tonight is Replit.

Searching Slack for “privacy contract” or “approval” finds Cursor and Notion. They look like the answer. They are not: a past yes is not reusable just because the words match. Keyword search cannot tell which parts still apply to a different company and which would be a false copy. Cursor’s contract is with a different company. Notion is not a coding tool, so it cannot prove Replit will not keep our code.

## What you will see

Two earlier approvals already got a yes (Cursor, Notion AI). Tonight someone asks for Replit.

1. **Five checks already covered, two still open.** Green dots = already done. Pink dots = still missing: a privacy contract with Replit (Legal), and proof Replit does not keep our code (Security).
2. **Qdrant** finds similar past approvals. Cursor ranks above Notion because both are coding tools.
3. **Cognee** remembers who signed what for which company. Similar is not the same company.
4. **Do not copy.** Notion had a privacy contract. It is not a coding tool. Do not reuse it for Replit.
5. **Legal can sign the privacy contract.** Replit is still not approved until Security has proof about the code. The chatbot cannot mark it approved.

Slack is where people talk. The web page is where someone signs. There is no search box.

## Stack

| Layer | Role |
|---|---|
| Slack | Where people talk (optional live bot) |
| Qdrant | Finds similar past approvals |
| Cognee | Remembers who signed what for which company |
| Qwen | Drafts Legal and Security notes |
| Code | Writes the official record. Not the chatbot. |
| Web sign-off | A person has to sign |

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

Open http://127.0.0.1:8765/?role=Legal — Sign files only the privacy contract. `POST /demo/reset` between takes. Optional: http://127.0.0.1:8765/history.html — Cursor’s month in Slack, then Notion.

Optional Slack: fill `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, and `SLACK_APP_TOKEN` in `.env`, then `python slack_bot.py`. Mention the bot with the Replit sentence above.

`python smoke.py` checks chat, embeddings, Qdrant, and a small Cognee round-trip.

## Honest scope

Greenlit helps run an approval. It does not certify that a company is legally compliant. The people who must sign stay responsible.
