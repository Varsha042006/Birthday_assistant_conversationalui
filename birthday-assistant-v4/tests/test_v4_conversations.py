import os
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_checkpoint_q1_nephew_during_september(client):
    """Q1: 'Do I need to wish any nephew during September?'"""
    res = client.post("/api/chat", json={"message": "Do I need to wish any nephew during September?"})
    assert res.status_code == 200
    data = res.get_json()
    print("\n[V4 Checkpoint Q1] Answer:\n", data["answer"])
    assert "Rahul Patil" in data["answer"]
    assert data["debug"]["enriched_entities"]["relationship"] == "Nephew"
    assert data["debug"]["enriched_entities"]["month"] == 9
    assert data["debug"]["parser"] in ("llm", "rule_fallback")


def test_checkpoint_q2_sibling_family_next_month(client):
    """Q2: 'Are there people from my sibling family celebrating next month?'"""
    # Current month is November -> next month is December
    # Mock LLM parsing to test semantic extraction of Sibling Family
    mock_llm_output = {
        "intent": "birthday_search",
        "entities": {
            "person_name": None,
            "relationship": "Sibling Family",
            "month": None,
            "relative_date": None,
            "relative_month": "next",
            "place": None
        }
    }
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-dummy"}):
        with patch("llm_nlu.call_llm", return_value=mock_llm_output):
            res = client.post("/api/chat", json={"message": "Are there people from my sibling family celebrating next month?"})
            assert res.status_code == 200
            data = res.get_json()
            print("\n[V4 Checkpoint Q2] Answer:\n", data["answer"])
            assert data["debug"]["parser"] == "llm"
            assert data["debug"]["enriched_entities"]["relationship"] == "Sibling Family"
            assert data["debug"]["enriched_entities"]["relative_month"] == "next"
            # In December, sibling family member Varun Kumar (Nephew) has birthday on Dec 17
            assert "Varun Kumar" in data["answer"]


def test_checkpoint_q3_rahul_birthday_coming_soon(client):
    """Q3: 'I was wondering whether Rahul has a birthday coming soon.'"""
    mock_llm_output = {
        "intent": "birthday_search",
        "entities": {
            "person_name": "Rahul",
            "relationship": None,
            "month": None,
            "relative_date": None,
            "relative_month": None,
            "place": None
        }
    }
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-dummy"}):
        with patch("llm_nlu.call_llm", return_value=mock_llm_output):
            res = client.post("/api/chat", json={"message": "I was wondering whether Rahul has a birthday coming soon."})
            assert res.status_code == 200
            data = res.get_json()
            print("\n[V4 Checkpoint Q3] Answer:\n", data["answer"])
            assert data["debug"]["parser"] == "llm"
            assert data["debug"]["person_id"] == "P004"
            assert "Rahul Patil's birthday is 18 September 2004." in data["answer"]


def test_checkpoint_q4_complex_paraphrase_cousins_december(client):
    """Q4: Paraphrased question that rule-based parser fails to understand completely."""
    # "Could you check if anyone among my cousins was born in the final month of the year?"
    # Rule parser misses month 12 from "final month of the year", but LLM resolves it:
    mock_llm_output = {
        "intent": "birthday_search",
        "entities": {
            "person_name": None,
            "relationship": "Cousin",
            "month": 12,
            "relative_date": None,
            "relative_month": None,
            "place": None
        }
    }
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-dummy"}):
        with patch("llm_nlu.call_llm", return_value=mock_llm_output):
            res = client.post("/api/chat", json={
                "message": "Could you check if anyone among my cousins was born in the final month of the year?"
            })
            assert res.status_code == 200
            data = res.get_json()
            print("\n[V4 Checkpoint Q4] Answer:\n", data["answer"])
            assert data["debug"]["parser"] == "llm"
            assert data["debug"]["enriched_entities"]["relationship"] == "Cousin"
            assert data["debug"]["enriched_entities"]["month"] == 12
            # In December, cousin Shreyas Desai has birthday on Dec 16
            assert "Shreyas Desai" in data["answer"]


def test_person_not_in_excel(client):
    """Test person who does not exist in Excel dataset."""
    res = client.post("/api/chat", json={"message": "When is Bruce Wayne's birthday?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["debug"]["person_id"] is None
    assert "No matching birthdays found." in data["answer"]


def test_unrelated_unknown_question(client):
    """Test unrelated / out-of-domain question."""
    res = client.post("/api/chat", json={"message": "What is the capital of France?"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["debug"]["intent"] == "unknown"
    assert "could not understand" in data["answer"].lower()


def test_context_carryover_and_reset(client):
    """Multi-turn context retention and conversation reset."""
    # Turn 1
    r1 = client.post("/api/chat", json={"message": "Any nephew birthdays in September?"})
    assert r1.status_code == 200
    assert r1.get_json()["debug"]["enriched_entities"]["relationship"] == "Nephew"

    # Turn 2: Follow-up retains relationship
    r2 = client.post("/api/chat", json={"message": "What about October?"})
    assert r2.status_code == 200
    d2 = r2.get_json()
    assert d2["debug"]["enriched_entities"]["relationship"] == "Nephew"
    assert d2["debug"]["enriched_entities"]["month"] == 10
    assert "Nikhil Hegde" in d2["answer"]

    # Turn 3: Reset
    r3 = client.post("/api/chat", json={"message": "Reset the conversation."})
    assert r3.status_code == 200
    assert r3.get_json()["state"] == {}

    # Turn 4: Fresh query without previous context
    r4 = client.post("/api/chat", json={"message": "What about October?"})
    assert r4.status_code == 200
    d4 = r4.get_json()
    assert d4["debug"]["enriched_entities"].get("relationship") is None
    assert d4["debug"]["enriched_entities"]["month"] == 10
