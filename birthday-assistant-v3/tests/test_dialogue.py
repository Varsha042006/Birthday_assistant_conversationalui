import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd
from dialogue import (
    create_clarification_prompt,
    detect_ambiguity,
    enrich_with_context,
    is_reset_command,
    resolve_clarification,
    update_state,
)


@pytest.fixture
def sample_df():
    return pd.DataFrame([
        {
            "Person_ID": "P001",
            "Name": "Lakshmi Rao",
            "Nickname": "Lakshmi",
            "DOB": pd.to_datetime("1982-12-14"),
            "Place_of_Stay": "Bengaluru",
            "Relationship": "Wife",
            "Relationship_Group": "Nuclear Family",
            "Relationship_Detail": "Spouse"
        },
        {
            "Person_ID": "P004",
            "Name": "Rahul Patil",
            "Nickname": "Rahul",
            "DOB": pd.to_datetime("2004-09-18"),
            "Place_of_Stay": "Bengaluru",
            "Relationship": "Nephew",
            "Relationship_Group": "Sibling Family",
            "Relationship_Detail": "Sister's son"
        },
        {
            "Person_ID": "P006",
            "Name": "Nikhil Hegde",
            "Nickname": "Nikhil",
            "DOB": pd.to_datetime("2001-10-03"),
            "Place_of_Stay": "Mysuru",
            "Relationship": "Nephew",
            "Relationship_Group": "Sibling Family",
            "Relationship_Detail": "Brother's son"
        },
        {
            "Person_ID": "P011",
            "Name": "Nikhil Bhat",
            "Nickname": "",
            "DOB": pd.to_datetime("2006-09-25"),
            "Place_of_Stay": "Sirsi",
            "Relationship": "Nephew",
            "Relationship_Group": "Sibling Family",
            "Relationship_Detail": "Sister's son"
        }
    ])


def test_is_reset_command():
    assert is_reset_command("Reset the conversation.") is True
    assert is_reset_command("reset") is True
    assert is_reset_command("reset conversation") is True
    assert is_reset_command("clear") is True
    assert is_reset_command("When is Rahul's birthday?") is False
    assert is_reset_command("") is False


def test_enrich_with_context_carryover_relationship():
    # Previous state: relationship=Nephew
    state = {"relationship": "Nephew", "month": 9, "last_intent": "birthday_search"}
    # New turn: only month=10
    parsed = {"intent": "birthday_search", "entities": {"month": 10}}
    enriched = enrich_with_context(parsed, state)
    assert enriched["entities"]["month"] == 10
    assert enriched["entities"]["relationship"] == "Nephew"


def test_enrich_with_context_carryover_month():
    # Previous state: month=9
    state = {"month": 9, "last_intent": "birthday_search"}
    # New turn: only relationship=Niece
    parsed = {"intent": "birthday_search", "entities": {"relationship": "Niece"}}
    enriched = enrich_with_context(parsed, state)
    assert enriched["entities"]["relationship"] == "Niece"
    assert enriched["entities"]["month"] == 9


def test_enrich_with_context_replace_month_and_relation():
    state = {"month": 9, "relationship": "Nephew"}
    # Explicit new month=11 and new relationship=Sister
    parsed = {"intent": "birthday_search", "entities": {"month": 11, "relationship": "Sister"}}
    enriched = enrich_with_context(parsed, state)
    assert enriched["entities"]["month"] == 11
    assert enriched["entities"]["relationship"] == "Sister"


def test_enrich_with_context_no_leak_to_unrelated():
    state = {"month": 9, "relationship": "Nephew"}
    parsed = {"intent": "unknown", "entities": {}}
    enriched = enrich_with_context(parsed, state)
    assert enriched["entities"] == {}


def test_enrich_with_context_no_leak_to_named_person():
    state = {"relationship": "Nephew", "month": 9}
    parsed = {"intent": "birthday_search", "entities": {"person_id": "P001", "person_name": "Lakshmi Rao"}}
    enriched = enrich_with_context(parsed, state)
    assert "relationship" not in enriched["entities"]


def test_detect_ambiguity_multiple_nephews(sample_df):
    parsed = {"intent": "birthday_search", "entities": {"relationship": "Nephew"}}
    is_ambiguous, candidates = detect_ambiguity(parsed, sample_df)
    assert is_ambiguous is True
    assert len(candidates) == 3
    names = [c["name"] for c in candidates]
    assert "Rahul Patil" in names
    assert "Nikhil Hegde" in names
    assert "Nikhil Bhat" in names


def test_detect_ambiguity_single_wife(sample_df):
    parsed = {"intent": "birthday_search", "entities": {"relationship": "Wife"}}
    is_ambiguous, candidates = detect_ambiguity(parsed, sample_df)
    assert is_ambiguous is False
    assert len(candidates) == 0


def test_detect_ambiguity_not_triggered_when_month_present(sample_df):
    parsed = {"intent": "birthday_search", "entities": {"relationship": "Nephew", "month": 9}}
    is_ambiguous, candidates = detect_ambiguity(parsed, sample_df)
    assert is_ambiguous is False


def test_create_clarification_prompt():
    candidates = [
        {"person_id": "P004", "name": "Rahul Patil", "nickname": "Rahul"},
        {"person_id": "P006", "name": "Nikhil Hegde", "nickname": "Nikhil"}
    ]
    prompt = create_clarification_prompt("Nephew", candidates)
    assert "Rahul Patil" in prompt
    assert "Nikhil Hegde" in prompt
    assert "Which person's birthday would you like to know?" in prompt


def test_resolve_clarification_by_nickname(sample_df):
    pending = {
        "relationship": "Nephew",
        "candidates": [
            {"person_id": "P004", "name": "Rahul Patil", "nickname": "Rahul"},
            {"person_id": "P006", "name": "Nikhil Hegde", "nickname": "Nikhil"},
            {"person_id": "P011", "name": "Nikhil Bhat", "nickname": ""}
        ]
    }
    # Exact nickname match 'Nikhil' resolves to Nikhil Hegde
    success, candidate, prompt = resolve_clarification("Nikhil", pending, sample_df)
    assert success is True
    assert candidate["person_id"] == "P006"
    assert candidate["name"] == "Nikhil Hegde"
    assert prompt is None


def test_resolve_clarification_by_full_name(sample_df):
    pending = {
        "relationship": "Nephew",
        "candidates": [
            {"person_id": "P006", "name": "Nikhil Hegde", "nickname": "Nikhil"},
            {"person_id": "P011", "name": "Nikhil Bhat", "nickname": ""}
        ]
    }
    success, candidate, prompt = resolve_clarification("Nikhil Bhat", pending, sample_df)
    assert success is True
    assert candidate["person_id"] == "P011"
    assert candidate["name"] == "Nikhil Bhat"


def test_resolve_clarification_unrecognized(sample_df):
    pending = {
        "relationship": "Nephew",
        "candidates": [
            {"person_id": "P004", "name": "Rahul Patil", "nickname": "Rahul"}
        ]
    }
    success, candidate, prompt = resolve_clarification("Superman", pending, sample_df)
    assert success is False
    assert candidate is None
    assert "didn't recognize 'Superman'" in prompt


def test_update_state():
    state = {}
    parsed = {"intent": "birthday_search", "entities": {"relationship": "Nephew", "month": 9}}
    new_state = update_state(parsed, state, last_result_ids=["P004"])
    assert new_state["relationship"] == "Nephew"
    assert new_state["month"] == 9
    assert new_state["last_result_ids"] == ["P004"]
    assert new_state["last_intent"] == "birthday_search"

