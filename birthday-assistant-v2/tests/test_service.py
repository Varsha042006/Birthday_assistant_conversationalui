import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date
import pytest
import pandas as pd
from service import execute, format_rows


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
        },
        {
            "Person_ID": "P007",
            "Name": "Anil Kumar",
            "Nickname": "Anil",
            "DOB": pd.to_datetime("1990-01-15"),
            "Place_of_Stay": "Mangaluru",
            "Relationship": "Cousin",
            "Relationship_Group": "Extended Family",
            "Relationship_Detail": "Uncle's son"
        }
    ])


TODAY = date(2026, 9, 11)


def test_format_rows_empty():
    empty_df = pd.DataFrame()
    assert format_rows(empty_df) == "No matching birthdays found."


def test_format_rows_with_data(sample_df):
    formatted = format_rows(sample_df.head(2))
    assert "• Lakshmi Rao — 14 December 1982 (Wife)" in formatted
    assert "• Rahul Patil — 18 September 2004 (Nephew)" in formatted


def test_person_birthday_search(sample_df):
    parsed = {
        "intent": "birthday_search",
        "entities": {"person_id": "P004", "person_name": "Rahul Patil"}
    }
    answer = execute(parsed, sample_df, today=TODAY)
    assert answer == "Rahul Patil's birthday is 18 September 2004."


def test_person_location_lookup(sample_df):
    parsed = {
        "intent": "person_place",
        "entities": {"person_id": "P004", "person_name": "Rahul Patil"}
    }
    answer = execute(parsed, sample_df, today=TODAY)
    assert answer == "Rahul Patil stays in Bengaluru."


def test_wife_location_by_relationship(sample_df):
    parsed = {
        "intent": "person_place",
        "entities": {"relationship": "Wife"}
    }
    answer = execute(parsed, sample_df, today=TODAY)
    assert answer == "Lakshmi Rao stays in Bengaluru."


def test_count_nephews_in_september(sample_df):
    parsed = {
        "intent": "count_birthdays",
        "entities": {"relationship": "Nephew", "month": 9}
    }
    answer = execute(parsed, sample_df, today=TODAY)
    assert "There are 1 nephew birthdays in September." in answer


def test_count_birthdays_in_october(sample_df):
    parsed = {
        "intent": "count_birthdays",
        "entities": {"month": 10}
    }
    answer = execute(parsed, sample_df, today=TODAY)
    assert "There are 1 birthdays in October." in answer


def test_count_birthdays_next_month(sample_df):
    parsed = {
        "intent": "count_birthdays",
        "entities": {"relative_month": "next"}
    }
    # Today is Sep 11, so next month is October (Nikhil Hegde)
    answer = execute(parsed, sample_df, today=TODAY)
    assert "There are 1 birthdays next month (October)." in answer


def test_count_birthdays_tomorrow(sample_df):
    parsed = {
        "intent": "count_birthdays",
        "entities": {"relative_date": "tomorrow"}
    }
    # Today is Sep 11, tomorrow is Sep 12 -> Aarav Sharma
    answer = execute(parsed, sample_df, today=TODAY)
    assert "There are 1 birthdays tomorrow." in answer


def test_show_birthdays_next_month(sample_df):
    parsed = {
        "intent": "birthday_search",
        "entities": {"relative_month": "next"}
    }
    answer = execute(parsed, sample_df, today=TODAY)
    assert "Nikhil Hegde" in answer
    assert "Rahul Patil" not in answer


def test_december_to_january_rollover(sample_df):
    december_today = date(2026, 12, 10)
    parsed = {
        "intent": "birthday_search",
        "entities": {"relative_month": "next"}
    }
    # Next month from December is January -> Anil Kumar (15 Jan)
    answer = execute(parsed, sample_df, today=december_today)
    assert "Anil Kumar" in answer


def test_upcoming_birthdays_30_days(sample_df):
    parsed = {
        "intent": "upcoming_birthdays",
        "entities": {}
    }
    # TODAY is Sep 11. Next 30 days are Sep 11 - Oct 11:
    # Sep 12: Aarav Sharma (tomorrow)
    # Sep 18: Rahul Patil (in 7 days)
    # Oct 03: Nikhil Hegde (in 22 days)
    # Anil Kumar (Jan) and Lakshmi Rao (Dec) are > 30 days away.
    answer = execute(parsed, sample_df, today=TODAY)
    assert "Aarav Sharma" in answer
    assert "Rahul Patil" in answer
    assert "Nikhil Hegde" in answer
    assert "Lakshmi Rao" not in answer


def test_no_matching_records(sample_df):
    parsed = {
        "intent": "birthday_search",
        "entities": {"month": 5}  # No one in May
    }
    answer = execute(parsed, sample_df, today=TODAY)
    assert answer == "No matching birthdays found."
