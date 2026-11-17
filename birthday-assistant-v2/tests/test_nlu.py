import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd
from nlu import parse


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
            "Person_ID": "P005",
            "Name": "Nikhil Hegde",
            "Nickname": "Nikhil",
            "DOB": pd.to_datetime("2001-10-03"),
            "Place_of_Stay": "Mysuru",
            "Relationship": "Nephew",
            "Relationship_Group": "Sibling Family",
            "Relationship_Detail": "Brother's son"
        },
        {
            "Person_ID": "P006",
            "Name": "Aarav Sharma",
            "Nickname": "Aaru",
            "DOB": pd.to_datetime("1995-09-12"),
            "Place_of_Stay": "Hubballi",
            "Relationship": "Friend",
            "Relationship_Group": "Friends",
            "Relationship_Detail": "College friend"
        }
    ])


def test_checkpoint_1_count_nephews_in_september(sample_df):
    query = "Count nephew birthdays in September."
    res = parse(query, sample_df)
    print(f"\n[Test Checkpoint 1] Query: '{query}' -> {res}")
    assert res["intent"] == "count_birthdays"
    assert res["entities"].get("relationship") == "Nephew"
    assert res["entities"].get("month") == 9


def test_checkpoint_2_where_does_rahul_patil_stay(sample_df):
    query = "Where does Rahul Patil stay?"
    res = parse(query, sample_df)
    print(f"\n[Test Checkpoint 2] Query: '{query}' -> {res}")
    assert res["intent"] == "person_place"
    assert res["entities"].get("person_id") == "P004"
    assert res["entities"].get("person_name") == "Rahul Patil"


def test_checkpoint_3_show_birthdays_next_month(sample_df):
    query = "Show birthdays next month."
    res = parse(query, sample_df)
    print(f"\n[Test Checkpoint 3] Query: '{query}' -> {res}")
    assert res["intent"] == "birthday_search"
    assert res["entities"].get("relative_month") == "next"


def test_any_nephew_birthdays_in_september(sample_df):
    query = "Any nephew birthdays in September?"
    res = parse(query, sample_df)
    print(f"\nQuery: '{query}' -> {res}")
    assert res["intent"] == "birthday_search"
    assert res["entities"].get("relationship") == "Nephew"
    assert res["entities"].get("month") == 9


def test_how_many_birthdays_in_october(sample_df):
    query = "How many birthdays are there in October?"
    res = parse(query, sample_df)
    print(f"\nQuery: '{query}' -> {res}")
    assert res["intent"] == "count_birthdays"
    assert res["entities"].get("month") == 10


def test_when_is_rahul_birthday_nickname(sample_df):
    query = "When is Rahul's birthday?"
    res = parse(query, sample_df)
    print(f"\nQuery: '{query}' -> {res}")
    assert res["intent"] == "birthday_search"
    assert res["entities"].get("person_id") == "P004"
    assert res["entities"].get("person_name") == "Rahul Patil"


def test_show_upcoming_birthdays(sample_df):
    query = "Show upcoming birthdays."
    res = parse(query, sample_df)
    print(f"\nQuery: '{query}' -> {res}")
    assert res["intent"] == "upcoming_birthdays"
    assert res["entities"] == {}


def test_is_there_any_birthday_tomorrow(sample_df):
    query = "Is there any birthday tomorrow?"
    res = parse(query, sample_df)
    print(f"\nQuery: '{query}' -> {res}")
    assert res["intent"] == "birthday_search"
    assert res["entities"].get("relative_date") == "tomorrow"


def test_where_does_my_wife_live(sample_df):
    query = "Where does my wife live?"
    res = parse(query, sample_df)
    print(f"\nQuery: '{query}' -> {res}")
    assert res["intent"] == "person_place"
    assert res["entities"].get("relationship") == "Wife"


def test_unsupported_question_unknown(sample_df):
    query = "Who is the most intelligent person?"
    res = parse(query, sample_df)
    print(f"\nQuery: '{query}' -> {res}")
    assert res["intent"] == "unknown"


def test_case_insensitivity(sample_df):
    query = "cOuNt nEpHeW bIrThDaYs iN sEpTeMbEr"
    res = parse(query, sample_df)
    assert res["intent"] == "count_birthdays"
    assert res["entities"].get("relationship") == "Nephew"
    assert res["entities"].get("month") == 9


def test_empty_input(sample_df):
    res = parse("", sample_df)
    assert res["intent"] == "unknown"
    assert res["entities"] == {}

    res_spaces = parse("   ", sample_df)
    assert res_spaces["intent"] == "unknown"
    assert res_spaces["entities"] == {}


def test_no_fake_person_id(sample_df):
    query = "When is Batman's birthday?"
    res = parse(query, sample_df)
    assert "person_id" not in res["entities"]
