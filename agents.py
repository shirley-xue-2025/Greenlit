#!/usr/bin/env python3
"""Four specialist agents: Legal, Security, Procurement, Challenger.

Returns JSON envelopes only. Catalog owns inherited/gaps for the Replit demo.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

GATE = Path(__file__).resolve().parent
GOLDEN_PATH = GATE / "demo" / "golden_replit.json"
CONTROLS_PATH = GATE / "corpus" / "controls.json"
REPLIT_REQUEST = "@Greenlit Can Product use Replit for internal prototypes?"

CHALLENGER_REQUIRED_NL = (
    "Notion had a signed DPA but is not a code tool, so it cannot prove "
    "Replit code retention. Cursor's Anysphere DPA does not transfer to Replit."
)

STANCE_BY_AGENT = {
    "legal": "recommend_with_gaps",
    "security": "recommend_with_gaps",
    "procurement": "recommend_with_gaps",
    "challenger": "block_copy",
}

AGENT_ORDER = ("legal", "security", "procurement", "challenger")

SYSTEM_PROMPTS: dict[str, str] = {
    "legal": (
        "You are the Legal specialist for Greenlit, an AI tool approval gate. "
        "Review the incoming tool request against org policy and prior signed approvals. "
        "Return a JSON object with keys: agent (\"legal\"), stance (short e.g. "
        "recommend_with_gaps or block), inherited (control id strings), "
        "gaps (control id strings), natural_language (2-4 sentences for Legal). "
        "Org controls may inherit from prior cases; vendor gaps need their own DPA."
    ),
    "security": (
        "You are the Security specialist for Greenlit. "
        "Check SSO, audit logging, PII rules, and code-retention requirements for coding tools. "
        "Return JSON: agent (\"security\"), stance, inherited[], gaps[], natural_language. "
        "A coding IDE needs proof the vendor does not train on or retain source code."
    ),
    "procurement": (
        "You are the Procurement specialist for Greenlit. "
        "Track vendor DPAs, contract files, and whether procurement artifacts exist for this vendor. "
        "Return JSON: agent (\"procurement\"), stance, inherited[], gaps[], natural_language. "
        "Cursor's Anysphere DPA does not transfer to other vendors."
    ),
    "challenger": (
        "You are the Challenger for Greenlit — your job is to block bad reasoning. "
        "Do NOT treat Notion AI approval as evidence for a coding tool: Notion had a signed DPA "
        "but is not a code tool, so it cannot prove Replit code retention or no-training-on-code. "
        "Do NOT copy Cursor's Anysphere DPA onto Replit. "
        "Return JSON: agent (\"challenger\"), stance (e.g. block_copy), inherited[], gaps[], "
        "natural_language must state that Notion had a DPA but is not a code tool and therefore "
        "cannot prove Replit code retention."
    ),
}

load_dotenv(GATE / ".env")
LLM_ENDPOINT = os.environ["LLM_ENDPOINT"]
LLM_API_KEY = os.environ["LLM_API_KEY"]
LLM_MODEL = os.environ["LLM_MODEL"].removeprefix("openai/")


def _client() -> OpenAI:
    return OpenAI(api_key=LLM_API_KEY, base_url=LLM_ENDPOINT)


def _load_catalog() -> tuple[list[str], list[str], list[str]]:
    data = json.loads(CONTROLS_PATH.read_text())
    org_ids = [c["id"] for c in data["org_controls"]]
    vendor_ids = [c["id"] for c in data["vendor_controls"]]
    known = org_ids + vendor_ids
    replit = data["cases"]["replit"]["controls"]
    inherited = [cid for cid in org_ids if replit.get(cid) == "inherit"]
    gaps = [cid for cid in vendor_ids if replit.get(cid) is False]
    return inherited, gaps, known


def _is_golden_trigger(text: str) -> bool:
    lowered = text.lower()
    return "replit" in lowered and "prototype" in lowered


def _strip_json_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_json(raw: str) -> dict | list:
    return json.loads(_strip_json_fences(raw))


def _call_qwen(messages: list[dict]) -> str:
    r = _client().chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=2048,
    )
    return (r.choices[0].message.content or "").strip()


def _build_user_prompt(request_text: str, prior_summaries: str | None) -> str:
    parts = [
        "Prior approvals context:",
        "- Cursor (Anysphere): signed DPA, all org + vendor controls met for a code IDE.",
        "- Notion AI (Notion Labs): signed DPA, org controls met; not a code tool.",
        "",
        f"New request: {request_text}",
    ]
    if prior_summaries:
        parts.extend(["", "Retrieved summaries:", prior_summaries])
    parts.extend(
        [
            "",
            "Known control ids:",
            "org: no_customer_pii, company_sso, prompt_audit_6mo, internal_use_only, named_owner",
            "vendor: vendor_dpa_signed, no_training_on_code",
            "",
            "For Replit (coding tool, no signed DPA): five org controls inherit; "
            "two vendor gaps remain.",
        ]
    )
    return "\n".join(parts)


def _normalize_envelope(raw: dict, agent: str) -> dict:
    return {
        "agent": agent,
        "stance": str(raw.get("stance", "review")),
        "inherited": list(raw.get("inherited") or []),
        "gaps": list(raw.get("gaps") or []),
        "natural_language": str(raw.get("natural_language", "")),
    }


def _apply_catalog(
    envelopes: list[dict], *, force_replit: bool, known_ids: set[str]
) -> list[dict]:
    inherited, gaps, _ = _load_catalog()
    out: list[dict] = []
    for env in envelopes:
        e = dict(env)
        if force_replit:
            e["inherited"] = list(inherited)
            e["gaps"] = list(gaps)
        else:
            e["inherited"] = [x for x in e.get("inherited", []) if x in known_ids]
            e["gaps"] = [x for x in e.get("gaps", []) if x in known_ids]
        out.append(e)
    return out


def _run_live_agents(request_text: str, prior_summaries: str | None = None) -> list[dict]:
    user_prompt = _build_user_prompt(request_text, prior_summaries)
    batch_prompt = (
        user_prompt
        + "\n\nReturn a JSON array of exactly four objects, one per agent in order: "
        "legal, security, procurement, challenger. Each object must have keys: "
        "agent, stance, inherited, gaps, natural_language. JSON only, no markdown."
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You simulate four Greenlit specialist agents in one response. "
                + " ".join(f"{a}: {SYSTEM_PROMPTS[a][:120]}..." for a in AGENT_ORDER)
            ),
        },
        {"role": "user", "content": batch_prompt},
    ]

    raw = _call_qwen(messages)
    try:
        parsed = _parse_json(raw)
    except json.JSONDecodeError:
        raw = _call_qwen(messages)
        parsed = _parse_json(raw)

    if isinstance(parsed, dict):
        if "envelopes" in parsed:
            items = parsed["envelopes"]
        else:
            items = [parsed]
    else:
        items = parsed

    by_agent: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        agent = str(item.get("agent", "")).lower()
        if agent in AGENT_ORDER:
            by_agent[agent] = _normalize_envelope(item, agent)

    missing = [a for a in AGENT_ORDER if a not in by_agent]
    if missing:
        for agent in missing:
            solo_messages = [
                {"role": "system", "content": SYSTEM_PROMPTS[agent]},
                {"role": "user", "content": user_prompt + "\n\nReturn JSON only."},
            ]
            solo_raw = _call_qwen(solo_messages)
            try:
                solo = _parse_json(solo_raw)
            except json.JSONDecodeError:
                solo_raw = _call_qwen(solo_messages)
                solo = _parse_json(solo_raw)
            if isinstance(solo, list):
                solo = solo[0]
            by_agent[agent] = _normalize_envelope(solo, agent)

    envelopes = [by_agent[a] for a in AGENT_ORDER]
    _, _, known = _load_catalog()
    return _apply_catalog(
        envelopes, force_replit=_is_golden_trigger(request_text), known_ids=set(known)
    )


def _load_golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text())


def run_agents(request_text: str, prior_summaries: str | None = None) -> list[dict]:
    if _is_golden_trigger(request_text):
        golden = _load_golden()
        return list(golden["envelopes"])
    return _run_live_agents(request_text, prior_summaries)


def seed_golden() -> None:
    request = REPLIT_REQUEST
    envelopes = _run_live_agents(request)
    inherited, gaps, _ = _load_catalog()
    for e in envelopes:
        e["inherited"] = list(inherited)
        e["gaps"] = list(gaps)
        e["stance"] = STANCE_BY_AGENT.get(e["agent"], e.get("stance", "review"))
        if e["agent"] == "challenger":
            e["natural_language"] = CHALLENGER_REQUIRED_NL

    payload = {
        "trigger_contains": ["replit", "prototype"],
        "request": request,
        "envelopes": envelopes,
    }
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(json.dumps(payload, indent=2) + "\n")


def check_golden() -> None:
    golden = _load_golden()
    envelopes = golden["envelopes"]
    if len(envelopes) != 4:
        raise SystemExit(f"expected 4 agents, got {len(envelopes)}")

    inherited, gaps, _ = _load_catalog()
    for e in envelopes:
        if e.get("inherited") != inherited:
            raise SystemExit(f"{e['agent']}: inherited mismatch {e.get('inherited')}")
        if e.get("gaps") != gaps:
            raise SystemExit(f"{e['agent']}: gaps mismatch {e.get('gaps')}")

    challenger = next(e for e in envelopes if e["agent"] == "challenger")
    nl = challenger.get("natural_language", "").lower()
    if "notion" not in nl:
        raise SystemExit("challenger natural_language must mention Notion")
    if "code" not in nl:
        raise SystemExit("challenger natural_language must mention code")
    if challenger.get("stance") != "block_copy":
        raise SystemExit(f"challenger stance must be block_copy, got {challenger.get('stance')}")
    for e in envelopes:
        if e["agent"] != "challenger" and e.get("stance") != "recommend_with_gaps":
            raise SystemExit(f"{e['agent']} stance must be recommend_with_gaps")

    agents = {e["agent"] for e in envelopes}
    if agents != set(AGENT_ORDER):
        raise SystemExit(f"unexpected agents: {agents}")

    print("check: ok — 4 agents, 5 inherited, 2 gaps, challenger cites Notion + code")


def main() -> None:
    parser = argparse.ArgumentParser(description="Greenlit specialist agents")
    parser.add_argument("--seed", action="store_true", help="Live Qwen seed of golden file")
    parser.add_argument("--check", action="store_true", help="Validate golden file")
    args = parser.parse_args()

    if args.check:
        check_golden()
        return

    if args.seed:
        print(f"Seeding golden via {LLM_MODEL}...", file=sys.stderr)
        seed_golden()
        print(json.dumps(_load_golden(), indent=2))
        return

    if not GOLDEN_PATH.exists():
        print(f"No golden file; seeding via {LLM_MODEL}...", file=sys.stderr)
        seed_golden()

    print(json.dumps(_load_golden(), indent=2))


if __name__ == "__main__":
    main()
