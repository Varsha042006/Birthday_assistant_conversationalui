import os
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

V5_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V5_DIR))

import pytest
import pandas as pd
from app import app
from llm_nlu import call_llm, ground_entities, parse_with_fallback, NLUOutputModel
from service import execute

DATA_PATH = V5_DIR / "data" / "people.xlsx"
df = pd.read_excel(DATA_PATH, sheet_name="People")
df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce")


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_gemini_pipeline_q1_nephew_september(client):
    """
    Test 1: 'Do I need to wish any nephew during September?'
    Verifies:
      - Gemini structured JSON output
      - Schema validation
      - Excel grounding
      - Final answer from service.py
      - Parser used: llm
    """
    mock_gemini_json = {
        "intent": "birthday_search",
        "entities": {
            "person_name": None,
            "person_id": None,
            "relationship": "nephew",
            "month": 9,
            "relative_date": None,
            "relative_month": None,
            "place": None
        }
    }

    mock_client = MagicMock()
    with patch("llm_nlu.get_gemini_client", return_value=mock_client):
        with patch("llm_nlu.call_llm", return_value=mock_gemini_json):
            res = client.post("/api/chat", json={"message": "Do I need to wish any nephew during September?"})
            assert res.status_code == 200
            data = res.get_json()

            assert data["debug"]["parser"] == "llm"
            assert data["debug"]["raw_entities"]["relationship"] in ("nephew", "Nephew")
            assert data["debug"]["enriched_entities"]["relationship"] == "Nephew"
            assert data["debug"]["enriched_entities"]["month"] == 9
            assert "Rahul Patil" in data["answer"]
            assert "18 September" in data["answer"]


def test_gemini_pipeline_q2_sibling_family_next_month(client):
    """
    Test 2: 'Are there people from my sibling family celebrating next month?'
    Verifies semantic extraction of relationship group 'Sibling Family' and relative month 'next'.
    """
    mock_gemini_json = {
        "intent": "birthday_search",
        "entities": {
            "person_name": None,
            "person_id": None,
            "relationship": "Sibling Family",
            "month": None,
            "relative_date": None,
            "relative_month": "next",
            "place": None
        }
    }

    mock_client = MagicMock()
    with patch("llm_nlu.get_gemini_client", return_value=mock_client):
        with patch("llm_nlu.call_llm", return_value=mock_gemini_json):
            res = client.post("/api/chat", json={"message": "Are there people from my sibling family celebrating next month?"})
            assert res.status_code == 200
            data = res.get_json()

            assert data["debug"]["parser"] == "llm"
            assert data["debug"]["enriched_entities"]["relationship"] == "Sibling Family"
            assert data["debug"]["enriched_entities"]["relative_month"] == "next"
            # In December, sibling family member Varun Kumar (Nephew) has birthday on Dec 17
            assert "Varun Kumar" in data["answer"]


def test_gemini_pipeline_q3_rahul_coming_soon(client):
    """
    Test 3: 'I was wondering whether Rahul has a birthday coming soon.'
    Verifies person name extraction, grounding to Person_ID P004, and service answer.
    """
    mock_gemini_json = {
        "intent": "birthday_search",
        "entities": {
            "person_name": "Rahul",
            "person_id": None,
            "relationship": None,
            "month": None,
            "relative_date": None,
            "relative_month": None,
            "place": None
        }
    }

    mock_client = MagicMock()
    with patch("llm_nlu.get_gemini_client", return_value=mock_client):
        with patch("llm_nlu.call_llm", return_value=mock_gemini_json):
            res = client.post("/api/chat", json={"message": "I was wondering whether Rahul has a birthday coming soon."})
            assert res.status_code == 200
            data = res.get_json()

            assert data["debug"]["parser"] == "llm"
            assert data["debug"]["person_id"] == "P004"
            assert "Rahul Patil's birthday is 18 September 2004." in data["answer"]


def test_gemini_pipeline_q4_complex_paraphrase(client):
    """
    Test 4: Complex sentence: 'Could you check if anyone among my cousins was born in the final month of the year?'
    Gemini semantically maps 'final month of the year' to month 12 and 'cousins' to 'Cousin'.
    """
    mock_gemini_json = {
        "intent": "birthday_search",
        "entities": {
            "person_name": None,
            "person_id": None,
            "relationship": "Cousin",
            "month": 12,
            "relative_date": None,
            "relative_month": None,
            "place": None
        }
    }

    mock_client = MagicMock()
    with patch("llm_nlu.get_gemini_client", return_value=mock_client):
        with patch("llm_nlu.call_llm", return_value=mock_gemini_json):
            res = client.post("/api/chat", json={
                "message": "Could you check if anyone among my cousins was born in the final month of the year?"
            })
            assert res.status_code == 200
            data = res.get_json()

            assert data["debug"]["parser"] == "llm"
            assert data["debug"]["enriched_entities"]["relationship"] == "Cousin"
            assert data["debug"]["enriched_entities"]["month"] == 12
            assert "Shreyas Desai" in data["answer"]
