#!/usr/bin/env python3
"""Copy and trigger checks for the Slack bot. No network."""
from __future__ import annotations

from slack_bot import (
    GOLDEN_TEXT,
    LEGAL_ROUTE_TEXT,
    SECURITY_ROUTE_TEXT,
    SIGN_FOLLOWUP,
    build_legal_route,
    build_reply,
    build_security_route,
    is_replit_demo,
)


def test_golden_trigger() -> None:
    assert is_replit_demo(
        "@Greenlit I want to use Replit for internal prototypes. Can you help with the approval?"
    )
    assert is_replit_demo("<@U123> replit prototype please")
    assert not is_replit_demo("Can we use Notion?")
    print("1. golden trigger: PASS")


def test_copy_rules() -> None:
    text, blocks = build_reply(golden=True, inherited_n=5, gaps_n=2)
    assert text == GOLDEN_TEXT
    assert "#" not in text
    assert "|" not in text
    assert "company rules" not in text
    assert "company login" in text
    assert "privacy contract" in text
    actions = [b for b in blocks if b["type"] == "actions"]
    assert len(actions) == 1
    buttons = actions[0]["elements"]
    assert len(buttons) == 1
    assert buttons[0]["type"] == "button"
    assert buttons[0]["text"]["text"] == "See my request"
    assert "role=Employee" in buttons[0]["url"]
    print("2. golden copy + one button: PASS")


def test_employee_mention() -> None:
    text, _blocks = build_reply(
        golden=True, inherited_n=5, gaps_n=2, requester_id="U12345678"
    )
    assert text.startswith("<@U12345678> ")
    assert GOLDEN_TEXT in text
    print("2b. employee mention: PASS")


def test_live_copy_has_no_hash() -> None:
    text, _blocks = build_reply(golden=False, inherited_n=4, gaps_n=3)
    assert "#" not in text
    assert "4 usual checks" in text
    assert "3 things still need Legal or Security" in text
    print("3. live copy: PASS")


def test_sign_followup() -> None:
    assert "#" not in SIGN_FOLLOWUP
    assert "DPA" in SIGN_FOLLOWUP
    assert "keep our code" in SIGN_FOLLOWUP
    assert "Jonas Weber" in SIGN_FOLLOWUP
    print("4. sign follow-up: PASS")


def test_legal_route() -> None:
    text, blocks = build_legal_route()
    assert "Priya Chen" in text
    assert "Shirley Xue" in text
    assert "Cursor" in text
    assert "Notion" in text
    buttons = [b for b in blocks if b["type"] == "actions"][0]["elements"]
    assert len(buttons) == 1
    assert buttons[0]["text"]["text"] == "Open as Legal"
    assert "role=Legal" in buttons[0]["url"]
    print("5. legal route: PASS")


def test_security_route() -> None:
    text, blocks = build_security_route()
    assert text == SECURITY_ROUTE_TEXT
    assert "Jonas Weber" in text
    assert "Priya Chen" in text
    assert "Shirley Xue" in text
    assert "Cursor" in text
    assert "Notion" in text
    assert "#" not in text
    buttons = [b for b in blocks if b["type"] == "actions"][0]["elements"]
    assert len(buttons) == 1
    assert buttons[0]["text"]["text"] == "Open as Security"
    assert "role=Security" in buttons[0]["url"]
    print("6. security route: PASS")


if __name__ == "__main__":
    test_golden_trigger()
    test_copy_rules()
    test_employee_mention()
    test_live_copy_has_no_hash()
    test_sign_followup()
    test_legal_route()
    test_security_route()
    print("slack_bot copy checks: ALL PASS")
