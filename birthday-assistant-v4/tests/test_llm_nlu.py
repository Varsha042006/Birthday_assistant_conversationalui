import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd
from pydantic import ValidationError
from llm_nlu import (
    EntitiesModel,
    NLUOutputModel,
    ground_entities,
    parse_with_fallback,
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
            "Relationship_Group": "Immediate Family",
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


def test_schema_valid():
    data = {
        "intent": "birthday_search",
        "entities": {
            "person_name": "Rahul Patil",
            "relationship": "Nephew",
            "month": 9,
            "relative_date": None,
            "relative_month": None,
            "place": None
        }
    }
    model = NLUOutputModel.model_validate(data)
    assert model.intent == "birthday_search"
    assert model.entities.month == 9


def test_schema_invalid_intent():
    data = {
        "intent": "invent_birthday",
        "entities": {}
    }
    with pytest.raises(ValidationError):
        NLUOutputModel.model_validate(data)


def test_schema_invalid_month():
    data = {
        "intent": "birthday_search",
        "entities": {"month": 15}
    }
    with pytest.raises(ValidationError):
        NLUOutputModel.model_validate(data)


def test_grounding_known_person_full_name(sample_df):
    parsed = {
        "intent": "birthday_search",
        "entities": {"person_name": "Rahul Patil"}
    }
    grounded = ground_entities(parsed, sample_df)
    assert grounded["entities"]["person_id"] == "P004"
    assert grounded["entities"]["person_name"] == "Rahul Patil"


def test_grounding_known_person_nickname(sample_df):
    parsed = {
        "intent": "birthday_search",
        "entities": {"person_name": "Rahul"}
    }
    grounded = ground_entities(parsed, sample_df)
    assert grounded["entities"]["person_id"] == "P004"
    assert grounded["entities"]["person_name"] == "Rahul Patil"


def test_grounding_unknown_person_no_fake_id(sample_df):
    parsed = {
        "intent": "birthday_search",
        "entities": {"person_name": "Bruce Wayne"}
    }
    grounded = ground_entities(parsed, sample_df)
    assert grounded["entities"]["person_id"] is None


def test_grounding_ambiguous_person_name():
    # Two people with exact same name match "Sanjay"
    ambiguous_df = pd.DataFrame([
        {"Person_ID": "P008", "Name": "Sanjay Rao", "Nickname": ""},
        {"Person_ID": "P017", "Name": "Sanjay M", "Nickname": ""}
    ])
    parsed = {
        "intent": "birthday_search",
        "entities": {"person_name": "Sanjay"}
    }
    grounded = ground_entities(parsed, ambiguous_df)
    assert grounded["entities"]["person_id"] is None
    assert len(grounded["entities"]["ambiguous_candidates"]) == 2


def test_grounding_relationship_and_group(sample_df):
    parsed = {
        "intent": "birthday_search",
        "entities": {"relationship": "nephews"}
    }
    grounded = ground_entities(parsed, sample_df)
    assert grounded["entities"]["relationship"] == "Nephew"

    parsed_group = {
        "intent": "birthday_search",
        "entities": {"relationship": "sibling family"}
    }
    grounded_group = ground_entities(parsed_group, sample_df)
    assert grounded_group["entities"]["relationship"] == "Sibling Family"


def test_parse_with_fallback_when_no_api_key(sample_df):
    with patch.dict(os.environ, {}, clear=True):
        res, parser_used = parse_with_fallback("Any nephew birthdays in September?", sample_df)
        assert parser_used == "rule_fallback"
        assert res["intent"] == "birthday_search"
        assert res["entities"]["relationship"] == "Nephew"
        assert res["entities"]["month"] == 9


def test_parse_with_fallback_on_api_error(sample_df):
    # With a mock client that raises an exception, should fallback cleanly
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-dummy-test-key"}):
        with patch("llm_nlu.call_llm", side_effect=Exception("API connection timeout")):
            res, parser_used = parse_with_fallback("When is Rahul's birthday?", sample_df)
            assert parser_used == "rule_fallback"
            assert res["intent"] == "birthday_search"
            assert res["entities"]["person_id"] == "P004"


def test_parse_with_fallback_success_mock(sample_df):
    mock_llm_output = {
        "intent": "birthday_search",
        "entities": {
            "person_name": "Rahul Patil",
            "relationship": None,
            "month": None,
            "relative_date": None,
            "relative_month": None,
            "place": None
        }
    }
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-dummy-test-key"}):
        with patch("llm_nlu.call_llm", return_value=mock_llm_output):
            res, parser_used = parse_with_fallback("I wonder when Rahul Patil was born", sample_df)
            assert parser_used == "llm"
            assert res["intent"] == "birthday_search"
            assert res["entities"]["person_id"] == "P004"
