"""Runnable compiler checks — .venv/bin/python test_compiler.py"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from compiler import (
    CHALLENGER_OVERRIDE_NOTE,
    ORG_IDS,
    VENDOR_IDS,
    apply_legal_dpa_sign,
    compile_record,
    load_catalog,
    reset_replit,
)

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "approval_record.schema.json"


def _load_schema() -> dict:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _assert_valid(record: dict) -> None:
    jsonschema.validate(record, _load_schema())


def test_replit_compile() -> None:
    record = compile_record("replit")
    assert len(record["inherited"]) == 5, record["inherited"]
    assert record["inherited"] == ORG_IDS
    assert record["gaps"] == VENDOR_IDS
    assert record["status"] == "blocked"
    assert record["record_id"] == "greenlit-replit"
    assert record["tool"] == "Replit"
    assert record["vendor"] == "Replit"
    assert record["source_thread_id"] == "T-REPLIT-2026-08"
    assert record["version"] == 1
    _assert_valid(record)
    print("1. Replit compile: PASS")


def test_unknown_control_dropped() -> None:
    envelopes = [
        {
            "role": "Legal",
            "stance": "caution",
            "inherited": ORG_IDS + ["bogus_control"],
            "gaps": VENDOR_IDS + ["another_fake"],
            "natural_language": "test",
        }
    ]
    record = compile_record("replit", envelopes=envelopes)
    legal = record["agent_envelopes"][0]
    assert "bogus_control" not in legal.get("inherited", [])
    assert "another_fake" not in legal.get("gaps", [])
    assert len(record["inherited"]) == 5
    assert record["gaps"] == VENDOR_IDS
    _assert_valid(record)
    print("2. Unknown control id dropped: PASS")


def test_catalog_overrides_agent_split() -> None:
    six_inherited = ORG_IDS + ["vendor_dpa_signed"]
    envelopes = [
        {
            "role": "Security",
            "stance": "block",
            "inherited": six_inherited,
            "gaps": ["no_training_on_code"],
            "natural_language": "wrong split",
        }
    ]
    record = compile_record("replit", envelopes=envelopes)
    assert len(record["inherited"]) == 5
    assert record["gaps"] == VENDOR_IDS
    challenger = next(
        (
            env
            for env in record["agent_envelopes"]
            if str(env.get("agent") or env.get("role") or "").lower() == "challenger"
        ),
        None,
    )
    assert challenger is not None
    assert challenger["natural_language"] == CHALLENGER_OVERRIDE_NOTE
    _assert_valid(record)
    print("3. Catalog overrides agent split: PASS")


def test_catalog_overrides_existing_challenger_agent_key() -> None:
    envelopes = [
        {
            "agent": "challenger",
            "stance": "block_copy",
            "inherited": ORG_IDS + ["vendor_dpa_signed"],
            "gaps": ["no_training_on_code"],
            "natural_language": "Notion DPA is not code-retention proof.",
        }
    ]
    record = compile_record("replit", envelopes=envelopes)
    challengers = [
        env
        for env in record["agent_envelopes"]
        if str(env.get("agent") or env.get("role") or "").lower() == "challenger"
    ]
    assert len(challengers) == 1
    assert challengers[0]["natural_language"] == CHALLENGER_OVERRIDE_NOTE
    assert record["gaps"] == VENDOR_IDS
    print("3b. Existing agent=challenger overwritten, not duplicated: PASS")


def test_never_signed_from_compile() -> None:
    envelopes = [{"role": "Legal", "status": "signed", "stance": "approve"}]
    record = compile_record("replit", envelopes=envelopes)
    assert record["status"] != "signed"
    assert record["status"] == "blocked"
    _assert_valid(record)
    print("4. compile_record never returns signed: PASS")


def test_apply_legal_dpa_sign() -> None:
    record = compile_record("replit")
    before_hash = record["content_hash"]
    signed = apply_legal_dpa_sign(record, rationale="DPA on file.")
    assert "vendor_dpa_signed" in signed["inherited"]
    assert "vendor_dpa_signed" not in signed["gaps"]
    assert "no_training_on_code" in signed["gaps"]
    assert signed["status"] == "blocked"
    assert signed["version"] == 2
    assert signed["content_hash"] != before_hash
    assert len(signed["human_signoffs"]) == 1
    assert signed["human_signoffs"][0]["role"] == "Legal"
    _assert_valid(signed)
    print("5. apply_legal_dpa_sign: PASS")


def test_reset_replit() -> None:
    record = reset_replit()
    assert len(record["inherited"]) == 5
    assert record["gaps"] == VENDOR_IDS
    assert record["status"] == "blocked"
    assert record["version"] == 1
    assert "human_signoffs" not in record
    _assert_valid(record)
    print("6. reset_replit: PASS")


def test_schema_validation() -> None:
    catalog = load_catalog()
    assert "replit" in catalog["cases"]
    record = compile_record("replit")
    _assert_valid(record)
    print("7. Record validates against JSON schema: PASS")


def main() -> None:
    test_replit_compile()
    test_unknown_control_dropped()
    test_catalog_overrides_agent_split()
    test_catalog_overrides_existing_challenger_agent_key()
    test_never_signed_from_compile()
    test_apply_legal_dpa_sign()
    test_reset_replit()
    test_schema_validation()
    print("\nAll compiler tests passed.")


if __name__ == "__main__":
    main()
