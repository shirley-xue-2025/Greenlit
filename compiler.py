"""Deterministic approval-record compiler. Catalog owns inherited/gaps split."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

ORG_IDS = [
    "no_customer_pii",
    "company_sso",
    "prompt_audit_6mo",
    "internal_use_only",
    "named_owner",
]
VENDOR_IDS = ["vendor_dpa_signed", "no_training_on_code"]
ALL_CONTROL_IDS = set(ORG_IDS + VENDOR_IDS)

CHALLENGER_OVERRIDE_NOTE = "Catalog overrides agent split."

_GATE_DIR = Path(__file__).resolve().parent
CATALOG_PATH = _GATE_DIR / "corpus" / "controls.json"
SCHEMA_PATH = _GATE_DIR / "schemas" / "approval_record.schema.json"


def load_catalog() -> dict:
    with CATALOG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _catalog_split(catalog: dict, case_id: str) -> tuple[list[str], list[str]]:
    case = catalog["cases"][case_id]
    controls = case["controls"]
    inherited: list[str] = []
    gaps: list[str] = []

    for org in catalog["org_controls"]:
        cid = org["id"]
        val = controls.get(cid)
        if val == "inherit" or val is True:
            inherited.append(cid)
        else:
            gaps.append(cid)

    for vendor in catalog["vendor_controls"]:
        cid = vendor["id"]
        val = controls.get(cid)
        if val is True:
            inherited.append(cid)
        else:
            gaps.append(cid)

    return inherited, gaps


def _sanitize_envelope(envelope: dict, valid_ids: set[str]) -> dict:
    cleaned = copy.deepcopy(envelope)
    if "inherited" in cleaned and isinstance(cleaned["inherited"], list):
        cleaned["inherited"] = [cid for cid in cleaned["inherited"] if cid in valid_ids]
    if "gaps" in cleaned and isinstance(cleaned["gaps"], list):
        cleaned["gaps"] = [cid for cid in cleaned["gaps"] if cid in valid_ids]
    return cleaned


def _envelope_has_split(envelope: dict) -> bool:
    return "inherited" in envelope or "gaps" in envelope


def _envelope_disagrees(envelope: dict, inherited: list[str], gaps: list[str]) -> bool:
    if not _envelope_has_split(envelope):
        return False
    env_inherited = set(envelope.get("inherited", []))
    env_gaps = set(envelope.get("gaps", []))
    return env_inherited != set(inherited) or env_gaps != set(gaps)


def _is_challenger(envelope: dict) -> bool:
    label = str(envelope.get("agent") or envelope.get("role") or "").strip().lower()
    return label == "challenger"


def _apply_challenger_override(
    envelopes: list[dict], inherited: list[str], gaps: list[str]
) -> list[dict]:
    result = copy.deepcopy(envelopes)
    for envelope in result:
        if _is_challenger(envelope):
            envelope["natural_language"] = CHALLENGER_OVERRIDE_NOTE
            envelope["inherited"] = list(inherited)
            envelope["gaps"] = list(gaps)
            return result

    result.append(
        {
            "agent": "challenger",
            "role": "Challenger",
            "stance": "override",
            "inherited": list(inherited),
            "gaps": list(gaps),
            "natural_language": CHALLENGER_OVERRIDE_NOTE,
        }
    )
    return result


def canonical_hash(record: dict) -> str:
    payload = {key: value for key, value in record.items() if key != "content_hash"}
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _load_schema() -> dict:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _validate_record(record: dict) -> None:
    try:
        jsonschema.validate(record, _load_schema())
    except jsonschema.ValidationError as exc:
        raise ValueError(str(exc)) from exc


def compile_record(
    case_id: str,
    envelopes: list[dict] | None = None,
    human_signoffs: list[dict] | None = None,
) -> dict:
    """Build a schema-valid approval record. Catalog owns inherited/gaps."""
    catalog = load_catalog()
    case = catalog["cases"][case_id]
    inherited, gaps = _catalog_split(catalog, case_id)

    processed_envelopes: list[dict] = []
    if envelopes:
        processed_envelopes = [
            _sanitize_envelope(envelope, ALL_CONTROL_IDS) for envelope in envelopes
        ]
        if any(
            _envelope_disagrees(envelope, inherited, gaps)
            for envelope in processed_envelopes
        ):
            processed_envelopes = _apply_challenger_override(
                processed_envelopes, inherited, gaps
            )

    status = "blocked" if gaps else "draft"

    record: dict = {
        "record_id": f"greenlit-{case_id}",
        "tool": case["tool"],
        "vendor": case["vendor"],
        "status": status,
        "inherited": list(inherited),
        "gaps": list(gaps),
        "source_thread_id": case["thread_id"],
        "agent_envelopes": processed_envelopes,
        "version": 1,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if human_signoffs:
        record["human_signoffs"] = copy.deepcopy(human_signoffs)

    record["content_hash"] = canonical_hash(record)
    _validate_record(record)
    return record


def apply_legal_dpa_sign(
    record: dict,
    rationale: str,
    signer: str = "Priya Chen, Legal",
) -> dict:
    """Move vendor_dpa_signed from gaps to inherited; status stays blocked if gaps remain."""
    result = copy.deepcopy(record)
    inherited = list(result["inherited"])
    gaps = list(result["gaps"])

    if "vendor_dpa_signed" in gaps:
        gaps.remove("vendor_dpa_signed")
    if "vendor_dpa_signed" not in inherited:
        inherited.append("vendor_dpa_signed")

    result["inherited"] = inherited
    result["gaps"] = gaps
    result["version"] = result.get("version", 1) + 1
    result["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if gaps:
        result["status"] = "blocked"

    signoff = {
        "role": "Legal",
        "signer": signer,
        "rationale": rationale,
        "at": result["updated_at"],
    }
    result.setdefault("human_signoffs", []).append(signoff)

    result["content_hash"] = canonical_hash(result)
    _validate_record(result)
    return result


def reset_replit(envelopes: list[dict] | None = None) -> dict:
    """Unsigned Replit draft from catalog (version 1, blocked, 5/2)."""
    return compile_record("replit", envelopes=envelopes, human_signoffs=None)


if __name__ == "__main__":
    record = compile_record("replit")
    print("=== Replit compile ===")
    print(f"inherited ({len(record['inherited'])}): {record['inherited']}")
    print(f"gaps ({len(record['gaps'])}): {record['gaps']}")
    print(f"status: {record['status']}")
    print(f"hash: {record['content_hash']}")

    signed = apply_legal_dpa_sign(
        record,
        rationale="Replit DPA countersigned and on file.",
    )
    print("\n=== After Legal DPA sign ===")
    print(f"inherited ({len(signed['inherited'])}): {signed['inherited']}")
    print(f"gaps ({len(signed['gaps'])}): {signed['gaps']}")
    print(f"status: {signed['status']}")
    print(f"version: {signed['version']}")
    print(f"hash: {signed['content_hash']}")
