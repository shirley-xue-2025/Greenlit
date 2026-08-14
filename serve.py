#!/usr/bin/env python3
"""Greenlit approval dashboard — FastAPI on :8765.

JSON shape for GET /api/state, POST /api/sign (200), POST /demo/reset:

  {
    "record": <approval record>,          # compiler output (inherited/gaps/status/hash/…)
    "envelopes": [<agent envelope>, ...], # same as record.agent_envelopes
    "similars": {
      "priors": [                         # Cursor + Notion from catalog
        {"case_id","tool","vendor","status","signed",
         "score": float|null, "preview": str|null, "note": str|null}
      ],
      "qdrant": [...],                    # demo/retrieve_replit.json hits, or []
      "pending": bool                     # true when retrieve file is missing
    },
    "slack": <corpus/replit-request.json plus synthetic=true>,
    "queue": [Cursor signed, Notion signed, Replit <record.status>],
    "roles": ["Legal", "Security", "Procurement"],
    "control_labels": {id: label},
    "control_order": [seven catalog ids],
    "graph_html": bool                    # web/graph.html present
  }

Agents cannot set status=signed. Only Legal may move vendor_dpa_signed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents import REPLIT_REQUEST, run_agents
from compiler import apply_legal_dpa_sign, compile_record, load_catalog, reset_replit

GATE = Path(__file__).resolve().parent
WEB_DIR = GATE / "web"
STATE_PATH = GATE / "demo" / "state.json"
GOLDEN_PATH = GATE / "demo" / "golden_replit.json"
RETRIEVE_PATH = GATE / "demo" / "retrieve_replit.json"
REPLIT_THREAD_PATH = GATE / "corpus" / "replit-request.json"
GRAPH_PATH = WEB_DIR / "graph.html"

LEGAL_ONLY_DETAIL = (
    "Only Legal can close the DPA gap tonight. Code-retention still needs evidence."
)

app = FastAPI(title="Greenlit")


class SignRequest(BaseModel):
    role: str
    rationale: str = ""


def _golden_envelopes() -> list[dict]:
    if not GOLDEN_PATH.is_file():
        return []
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    return list(data.get("envelopes") or [])


def persist(record: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def load_record() -> dict:
    if STATE_PATH.is_file():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "inherited" in data and "gaps" in data:
                return data
        except (OSError, json.JSONDecodeError):
            pass
    record = compile_record("replit", envelopes=_golden_envelopes())
    persist(record)
    return record


def _control_meta(catalog: dict) -> tuple[dict[str, str], list[str]]:
    labels: dict[str, str] = {}
    order: list[str] = []
    for group in ("org_controls", "vendor_controls"):
        for item in catalog[group]:
            order.append(item["id"])
            labels[item["id"]] = item["label"]
    return labels, order


def _similars(catalog: dict) -> dict:
    priors: list[dict] = []
    for case_id in ("cursor", "notion"):
        case = catalog["cases"][case_id]
        priors.append(
            {
                "case_id": case_id,
                "tool": case["tool"],
                "vendor": case["vendor"],
                "status": case["status"],
                "signed": case.get("signed"),
                "score": None,
                "preview": None,
                "note": "retrieval pending",
            }
        )
    qdrant: list = []
    pending = True
    if RETRIEVE_PATH.is_file():
        try:
            payload = json.loads(RETRIEVE_PATH.read_text(encoding="utf-8"))
            qdrant = list(payload.get("qdrant") or [])
            pending = False
        except (OSError, json.JSONDecodeError):
            qdrant = []
            pending = True
    if not pending:
        for prior in priors:
            key = "cursor" if "cursor" in prior["tool"].lower() else "notion"
            matches = [
                hit
                for hit in qdrant
                if key in str(hit.get("tool_guess") or "").lower()
            ]
            if matches:
                best = max(matches, key=lambda hit: float(hit.get("score") or 0))
                score = best.get("score")
                prior["score"] = None if score is None else float(score)
                prior["preview"] = best.get("preview")
                prior["note"] = None
            else:
                prior["score"] = None
                prior["preview"] = None
                prior["note"] = "no matching chunk yet"
    return {"priors": priors, "qdrant": qdrant, "pending": pending}


def _slack() -> dict:
    raw = json.loads(REPLIT_THREAD_PATH.read_text(encoding="utf-8"))
    raw["synthetic"] = True
    return raw


def _queue(record: dict, catalog: dict) -> list[dict]:
    rows = []
    for case_id in ("cursor", "notion", "replit"):
        case = catalog["cases"][case_id]
        status = record["status"] if case_id == "replit" else case["status"]
        rows.append(
            {
                "case_id": case_id,
                "tool": case["tool"],
                "vendor": case["vendor"],
                "status": status,
                "signed": None if case_id == "replit" else case.get("signed"),
                "current": case_id == "replit",
            }
        )
    return rows


def build_state() -> dict:
    catalog = load_catalog()
    record = load_record()
    labels, order = _control_meta(catalog)
    envelopes = list(record.get("agent_envelopes") or [])
    return {
        "record": record,
        "envelopes": envelopes,
        "similars": _similars(catalog),
        "slack": _slack(),
        "queue": _queue(record, catalog),
        "roles": ["Employee", "Legal", "Security", "Procurement"],
        "control_labels": labels,
        "control_order": order,
        "graph_html": GRAPH_PATH.is_file(),
    }


@app.get("/api/state")
def api_state() -> dict:
    return build_state()


@app.post("/api/sign")
def api_sign(body: SignRequest) -> dict:
    role = (body.role or "").strip()
    role_key = role.casefold()
    rationale = (body.rationale or "").strip()

    if role_key in {"security", "procurement"}:
        raise HTTPException(status_code=400, detail=LEGAL_ONLY_DETAIL)
    if role_key != "legal":
        raise HTTPException(
            status_code=400,
            detail="Unknown role. Sign as Legal, Security, or Procurement.",
        )
    if not rationale:
        raise HTTPException(status_code=400, detail="Rationale is required to sign.")

    record = load_record()
    updated = apply_legal_dpa_sign(record, rationale=rationale)
    persist(updated)
    try:
        from slack_bot import post_legal_signed

        post_legal_signed()
    except Exception as exc:  # noqa: BLE001 — Slack must not fail the sign API
        print(f"slack write-back skipped: {exc}", file=sys.stderr)
    return build_state()


@app.post("/demo/reset")
def demo_reset() -> dict:
    envelopes = run_agents(REPLIT_REQUEST)
    record = reset_replit(envelopes=envelopes)
    persist(record)
    try:
        from slack_bot import reset_sign_flag

        reset_sign_flag()
    except Exception as exc:  # noqa: BLE001 — Slack must not fail reset
        print(f"slack reset flag skipped: {exc}", file=sys.stderr)
    return build_state()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html", media_type="text/html")


app.mount("/", StaticFiles(directory=str(WEB_DIR)), name="web")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
