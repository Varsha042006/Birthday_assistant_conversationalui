import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_checkpoint_case_1_month_context(client):
    """
    TEST CASE 1: MONTH CONTEXT
    User: Any nephew birthdays in September?
    Assistant: Display matching nephew birthdays in September.
    User: What about October?
    Expected:
    - Retain relationship = Nephew.
    - Replace month = October.
    - Display only October birthdays belonging to Nephews.
    """
    # Turn 1
    r1 = client.post("/api/chat", json={"message": "Any nephew birthdays in September?"})
    assert r1.status_code == 200
    d1 = r1.get_json()
    print("\n[Case 1 Turn 1] Answer:\n", d1["answer"])
    assert "Rahul Patil" in d1["answer"]
    assert d1["debug"]["enriched_entities"]["relationship"] == "Nephew"
    assert d1["debug"]["enriched_entities"]["month"] == 9

    # Turn 2: Follow-up
    r2 = client.post("/api/chat", json={"message": "What about October?"})
    assert r2.status_code == 200
    d2 = r2.get_json()
    print("[Case 1 Turn 2] Answer:\n", d2["answer"])
    # Context carried: relationship=Nephew, new month=10
    assert d2["debug"]["enriched_entities"]["relationship"] == "Nephew"
    assert d2["debug"]["enriched_entities"]["month"] == 10
    # In the dataset, only Nikhil Hegde is a nephew in October
    assert "Nikhil Hegde" in d2["answer"]
    # September nephews should not appear
    assert "Rahul Patil" not in d2["answer"]


def test_checkpoint_case_2_clarification(client):
    """
    TEST CASE 2: CLARIFICATION
    User: When is my nephew's birthday?
    Assistant:
    - Find all matching Nephews.
    - If multiple people exist, ask which person the user means.
    User: Nikhil
    Expected:
    - Resolve Nikhil against the pending candidates.
    - Return the correct person's birthday.
    """
    # Turn 1: Ambiguous relationship question
    r1 = client.post("/api/chat", json={"message": "When is my nephew's birthday?"})
    assert r1.status_code == 200
    d1 = r1.get_json()
    print("\n[Case 2 Turn 1] Clarification Prompt:\n", d1["answer"])
    assert "multiple people with the relationship Nephew" in d1["answer"]
    assert "Rahul Patil" in d1["answer"]
    assert "Nikhil" in d1["answer"]
    assert d1["state"].get("pending_clarification") is not None

    # Turn 2: Clarification reply
    r2 = client.post("/api/chat", json={"message": "Nikhil"})
    assert r2.status_code == 200
    d2 = r2.get_json()
    print("[Case 2 Turn 2] Resolved Answer:\n", d2["answer"])
    assert "Nikhil Hegde's birthday is 3 October 2001." in d2["answer"]
    # Pending clarification is cleared
    assert d2["state"].get("pending_clarification") is None
    assert d2["state"].get("person_id") == "P006"


def test_checkpoint_case_3_relationship_context(client):
    """
    TEST CASE 3: RELATIONSHIP CONTEXT
    User: Birthdays in September.
    Assistant: Display birthdays in September.
    User: What about nieces?
    Expected:
    - Retain month = September.
    - Update relationship = Niece.
    - Display September birthdays belonging to Nieces.
    """
    # Turn 1: Month search
    r1 = client.post("/api/chat", json={"message": "Birthdays in September."})
    assert r1.status_code == 200
    d1 = r1.get_json()
    print("\n[Case 3 Turn 1] Answer:\n", d1["answer"][:120], "...")
    assert d1["state"]["month"] == 9

    # Turn 2: Follow-up with new relationship
    r2 = client.post("/api/chat", json={"message": "What about nieces?"})
    assert r2.status_code == 200
    d2 = r2.get_json()
    print("[Case 3 Turn 2] Answer:\n", d2["answer"])
    assert d2["debug"]["enriched_entities"]["relationship"] == "Niece"
    assert d2["debug"]["enriched_entities"]["month"] == 9
    # In the dataset, nieces in September are Ananya Patil, Nayana Joshi, Asha M
    assert "Ananya Patil" in d2["answer"]


def test_checkpoint_case_4_reset_context(client):
    """
    TEST CASE 4: RESET CONTEXT
    User: Birthdays in September.
    Assistant: Display September birthdays.
    User: Reset the conversation.
    Assistant: Confirm that the conversation has been reset.
    User: What about October?
    Expected:
    - The previous September context must be cleared.
    - Do not reuse any previous relationship or month.
    - Interpret October independently.
    - Display all October birthdays without an old relationship filter.
    """
    # Turn 1
    r1 = client.post("/api/chat", json={"message": "Birthdays in September."})
    assert r1.status_code == 200
    assert r1.get_json()["state"]["month"] == 9

    # Turn 2: Reset
    r2 = client.post("/api/chat", json={"message": "Reset the conversation."})
    assert r2.status_code == 200
    d2 = r2.get_json()
    print("\n[Case 4 Turn 2] Reset confirmation:\n", d2["answer"])
    assert "reset" in d2["answer"].lower()
    assert d2["state"] == {}

    # Turn 3: Follow-up without prior context
    r3 = client.post("/api/chat", json={"message": "What about October?"})
    assert r3.status_code == 200
    d3 = r3.get_json()
    print("[Case 4 Turn 3] Independent October query:\n", d3["answer"][:120], "...")
    assert d3["debug"]["enriched_entities"].get("relationship") is None
    assert d3["debug"]["enriched_entities"]["month"] == 10
    # There are 12 people across different relationships in October
    # Check that multiple relationships appear (not filtered by any previous relationship)
    assert "Nikhil Hegde" in d3["answer"]
    assert "Nayana Kumar" in d3["answer"]


def test_api_reset_endpoint(client):
    # Set context first
    client.post("/api/chat", json={"message": "Any nephew birthdays in September?"})
    # Call /api/reset
    res = client.post("/api/reset")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert "reset" in data["message"].lower()

    # Next call should have fresh state
    r2 = client.post("/api/chat", json={"message": "Where does Rahul Patil stay?"})
    assert r2.get_json()["debug"]["enriched_entities"].get("relationship") is None
