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


def test_v5_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["version"] == "V5"
    assert data["mode"] == "voice_enabled"
    assert data["records"] == 100


def test_v5_voice_style_query_tomorrow(client):
    """TEST 1: Voice-style question: 'Any birthdays tomorrow?'"""
    res = client.post("/api/chat", json={"message": "Any birthdays tomorrow?"})
    assert res.status_code == 200
    data = res.get_json()
    print("\n[V5 Test 1] Answer:", data["answer"])
    assert "answer" in data
    assert data["debug"]["intent"] == "birthday_search"
    assert data["debug"]["enriched_entities"]["relative_date"] == "tomorrow"


def test_v5_voice_style_person_name(client):
    """TEST 2: Voice-style spoken person name: 'When is Rahul Patil's birthday?'"""
    res = client.post("/api/chat", json={"message": "When is Rahul Patil's birthday?"})
    assert res.status_code == 200
    data = res.get_json()
    print("[V5 Test 2] Answer:", data["answer"])
    assert "Rahul Patil's birthday is 18 September 2004." in data["answer"]
    assert data["debug"]["person_id"] == "P004"


def test_v5_voice_follow_up_multi_turn(client):
    """
    TEST 3: Multi-turn voice dialogue:
    Turn 1: 'Any nephew birthdays in September?'
    Turn 2: 'What about October?'
    """
    # Turn 1
    r1 = client.post("/api/chat", json={"message": "Any nephew birthdays in September?"})
    assert r1.status_code == 200
    d1 = r1.get_json()
    assert "Rahul Patil" in d1["answer"]
    assert d1["debug"]["enriched_entities"]["relationship"] == "Nephew"
    assert d1["debug"]["enriched_entities"]["month"] == 9

    # Turn 2: Follow-up retains relationship = Nephew
    r2 = client.post("/api/chat", json={"message": "What about October?"})
    assert r2.status_code == 200
    d2 = r2.get_json()
    print("[V5 Test 3] Follow-up Answer:", d2["answer"])
    assert d2["debug"]["enriched_entities"]["relationship"] == "Nephew"
    assert d2["debug"]["enriched_entities"]["month"] == 10
    # In October, only Nikhil Hegde is a nephew
    assert "Nikhil Hegde" in d2["answer"]
    assert "Rahul Patil" not in d2["answer"]


def test_v5_reset_endpoint(client):
    # Establish context
    client.post("/api/chat", json={"message": "Any nephew birthdays in September?"})
    # Reset
    res = client.post("/api/reset")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert "reset" in data["message"].lower()

    # Next query should have fresh state
    r2 = client.post("/api/chat", json={"message": "What about October?"})
    d2 = r2.get_json()
    assert d2["debug"]["enriched_entities"].get("relationship") is None
    assert d2["debug"]["enriched_entities"]["month"] == 10


def test_v5_general_query_after_relationship(client):
    """
    Verify that an open/general query (e.g. 'Whose birthday in September month?')
    does not inherit a previously queried specific relationship like 'Wife'.
    """
    # Turn 1: Ask for wife's birthday
    r1 = client.post("/api/chat", json={"message": "When was my wife birthday?"})
    assert r1.status_code == 200
    d1 = r1.get_json()
    assert "Lakshmi Rao" in d1["answer"]

    # Turn 2: Ask an open question 'Whose birthday in September month?'
    r2 = client.post("/api/chat", json={"message": "Whose birthday in September month?"})
    assert r2.status_code == 200
    d2 = r2.get_json()
    assert "Birthdays in September" in d2["answer"]
    assert "No matching birthdays found." not in d2["answer"]
    assert d2["debug"]["enriched_entities"].get("relationship") is None
    assert d2["debug"]["enriched_entities"]["month"] == 9

    # Turn 3: Ask 'Birthdays in October month.'
    r3 = client.post("/api/chat", json={"message": "Birthdays in October month."})
    assert r3.status_code == 200
    d3 = r3.get_json()
    assert "Birthdays in October" in d3["answer"]
    assert "No matching birthdays found." not in d3["answer"]
    assert d3["debug"]["enriched_entities"].get("relationship") is None
    assert d3["debug"]["enriched_entities"]["month"] == 10


def test_v5_unsupported_death_and_murder_queries(client):
    """
    Verify queries asking about death, murder, or dying are rejected as unknown
    and NEVER display birthday dates.
    """
    queries = [
        "When was my sister murder?",
        "When was my aunt died?",
        "Did Rahul die?",
        "Who was murdered?"
    ]
    for q in queries:
        res = client.post("/api/chat", json={"message": q})
        assert res.status_code == 200
        data = res.get_json()
        assert data["debug"]["intent"] == "unknown", f"Failed on {q}"
        assert "could not understand" in data["answer"].lower(), f"Failed on {q}"
        assert "birthday" not in data["answer"].lower() or "try asking" in data["answer"].lower()


