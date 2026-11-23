from datetime import date, timedelta
import calendar
from typing import Any, Dict, Optional
import pandas as pd


def _anniversary_in_year(dob: date, year: int) -> date:
    """Calculate birthday in a specific year, handling Feb 29 leap years."""
    try:
        return date(year, dob.month, dob.day)
    except ValueError:
        return date(year, 2, 28)


def get_next_birthday(dob: date, today: date) -> date:
    """Return the next upcoming birthday date on or after today."""
    cand = _anniversary_in_year(dob, today.year)
    if cand < today:
        cand = _anniversary_in_year(dob, today.year + 1)
    return cand


def format_rows(rows: pd.DataFrame, today: Optional[date] = None) -> str:
    """
    Format a DataFrame of people records into human-readable bullet points.
    Returns a fallback message if rows is empty.
    """
    if rows is None or rows.empty:
        return "No matching birthdays found."

    lines = []
    for _, r in rows.iterrows():
        dob = r["DOB"]
        dob_str = f"{dob.day} {dob.strftime('%B %Y')}"
        rel = str(r.get("Relationship", "")).strip()
        rel_str = f" ({rel})" if rel else ""
        lines.append(f"• {r['Name']} — {dob_str}{rel_str}")
    return "\n".join(lines)


def execute(parsed: Dict[str, Any], df: pd.DataFrame, today: Optional[date] = None) -> str:
    """
    Execute business logic and Excel filtering based on structured NLU output.
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return "No people dataset available."

    today = today or date.today()
    intent = parsed.get("intent", "unknown")
    entities = parsed.get("entities", {})

    # ========================================================
    # 1. person_place: Location lookup
    # ========================================================
    if intent == "person_place":
        target_row = None
        # Try matching by person_id
        if "person_id" in entities:
            matches = df[df["Person_ID"] == entities["person_id"]]
            if not matches.empty:
                target_row = matches.iloc[0]

        # Or fallback to person_name
        if target_row is None and "person_name" in entities:
            matches = df[df["Name"].str.casefold() == entities["person_name"].casefold()]
            if not matches.empty:
                target_row = matches.iloc[0]

        # Or fallback to relationship (e.g., "Where does my wife live?")
        if target_row is None and "relationship" in entities:
            rel = entities["relationship"]
            matches = df[df["Relationship"].str.casefold() == rel.casefold()]
            if rel.lower() == "wife" and not matches.empty:
                spouse = matches[matches["Relationship_Detail"].str.casefold() == "spouse"]
                if not spouse.empty:
                    target_row = spouse.iloc[0]
            if target_row is None and not matches.empty:
                target_row = matches.iloc[0]

        if target_row is not None:
            name = target_row["Name"]
            place = target_row.get("Place_of_Stay", "").strip()
            if place:
                return f"{name} stays in {place}."
            return f"Location for {name} is not recorded."

        return "Could not find location information for that person."

    # ========================================================
    # 2. count_birthdays: Count queries
    # ========================================================
    if intent == "count_birthdays":
        work = df.copy()

        # Filter by relationship
        if "relationship" in entities:
            rel = entities["relationship"]
            work = work[work["Relationship"].str.casefold() == rel.casefold()]

        # Filter by relative date: tomorrow
        if entities.get("relative_date") == "tomorrow":
            target_date = today + timedelta(days=1)
            work = work[(work["DOB"].dt.month == target_date.month) & (work["DOB"].dt.day == target_date.day)]
            count = len(work)
            rel_label = f" {entities['relationship'].lower()}" if "relationship" in entities else ""
            return f"There are {count}{rel_label} birthdays tomorrow."

        # Filter by relative month: next month
        if entities.get("relative_month") == "next":
            next_m = (today.month % 12) + 1
            work = work[work["DOB"].dt.month == next_m]
            count = len(work)
            next_m_name = calendar.month_name[next_m]
            rel_label = f" {entities['relationship'].lower()}" if "relationship" in entities else ""
            return f"There are {count}{rel_label} birthdays next month ({next_m_name})."

        # Filter by specific calendar month
        if "month" in entities:
            m = entities["month"]
            work = work[work["DOB"].dt.month == m]
            count = len(work)
            m_name = calendar.month_name[m]
            rel_label = f" {entities['relationship'].lower()}" if "relationship" in entities else ""
            return f"There are {count}{rel_label} birthdays in {m_name}."

        # Filter by relationship only
        if "relationship" in entities:
            count = len(work)
            return f"There are {count} people recorded as {entities['relationship']}."

        count = len(work)
        return f"There are {count} matching birthdays."

    # ========================================================
    # 3. upcoming_birthdays: Occurring within the next 30 days
    # ========================================================
    if intent == "upcoming_birthdays":
        upcoming_rows = []
        for idx, r in df.iterrows():
            dob = r["DOB"].date()
            next_bday = get_next_birthday(dob, today)
            days_away = (next_bday - today).days
            if 0 <= days_away <= 30:
                upcoming_rows.append({
                    "idx": idx,
                    "next_bday": next_bday,
                    "days_away": days_away,
                    "Name": r["Name"],
                    "DOB": r["DOB"],
                    "Relationship": r["Relationship"]
                })

        if not upcoming_rows:
            return "No matching birthdays found."

        # Sort by nearest upcoming birthday, then by Name
        upcoming_rows.sort(key=lambda x: (x["next_bday"], x["Name"]))

        lines = []
        for item in upcoming_rows:
            dob = item["DOB"]
            days = item["days_away"]
            timing = "today" if days == 0 else ("tomorrow" if days == 1 else f"in {days} days")
            lines.append(f"• {item['Name']} — {dob.day} {dob.strftime('%B')} ({item['Relationship']}; {timing})")

        return "Upcoming birthdays in the next 30 days:\n" + "\n".join(lines)

    # ========================================================
    # 4. birthday_search: Named person or filtered listing
    # ========================================================
    if intent == "birthday_search":
        # A. Specific person searched by person_id or person_name
        if "person_id" in entities or "person_name" in entities:
            matches = df[df["Person_ID"] == entities["person_id"]] if "person_id" in entities else \
                      df[df["Name"].str.casefold() == entities["person_name"].casefold()]
            if not matches.empty:
                r = matches.iloc[0]
                dob = r["DOB"]
                return f"{r['Name']}'s birthday is {dob.day} {dob.strftime('%B %Y')}."
            return "No matching birthdays found."

        work = df.copy()

        # B. Filter by relationship
        if "relationship" in entities:
            rel = entities["relationship"]
            work = work[work["Relationship"].str.casefold() == rel.casefold()]
            # If "Wife" and single spouse
            if rel.lower() == "wife":
                spouse = work[work["Relationship_Detail"].str.casefold() == "spouse"]
                if not spouse.empty:
                    work = spouse

        # C. Filter by relative date: tomorrow
        if entities.get("relative_date") == "tomorrow":
            target_date = today + timedelta(days=1)
            work = work[(work["DOB"].dt.month == target_date.month) & (work["DOB"].dt.day == target_date.day)]
            if work.empty:
                return "No matching birthdays found."
            return f"Birthdays tomorrow ({target_date.strftime('%d %B')}):\n" + format_rows(work, today)

        # D. Filter by relative month: next month
        if entities.get("relative_month") == "next":
            next_m = (today.month % 12) + 1
            next_m_name = calendar.month_name[next_m]
            work = work[work["DOB"].dt.month == next_m].copy()
            if work.empty:
                return "No matching birthdays found."
            work["_day"] = work["DOB"].dt.day
            work = work.sort_values(["_day", "Name"]).drop(columns=["_day"])
            rel_label = f" for relationship '{entities['relationship']}'" if "relationship" in entities else ""
            return f"Birthdays next month ({next_m_name}){rel_label}:\n" + format_rows(work, today)

        # E. Filter by calendar month
        if "month" in entities:
            m = entities["month"]
            m_name = calendar.month_name[m]
            work = work[work["DOB"].dt.month == m].copy()
            if work.empty:
                return "No matching birthdays found."
            work["_day"] = work["DOB"].dt.day
            work = work.sort_values(["_day", "Name"]).drop(columns=["_day"])
            rel_label = f" for relationship '{entities['relationship']}'" if "relationship" in entities else ""
            return f"Birthdays in {m_name}{rel_label}:\n" + format_rows(work, today)

        # F. Relationship only (no month or relative date)
        if "relationship" in entities:
            if work.empty:
                return "No matching birthdays found."
            if len(work) == 1:
                r = work.iloc[0]
                dob = r["DOB"]
                return f"{r['Name']}'s birthday is {dob.day} {dob.strftime('%B %Y')}."
            work["_next"] = work["DOB"].apply(lambda x: get_next_birthday(x.date(), today))
            work = work.sort_values(["_next", "Name"]).drop(columns=["_next"])
            return f"Birthdays for relationship '{entities['relationship']}':\n" + format_rows(work, today)

        if work.empty:
            return "No matching birthdays found."
        return format_rows(work, today)

    # ========================================================
    # 5. unknown: Fallback
    # ========================================================
    return (
        "I could not understand that question. "
        "Try asking: 'When is Rahul Patil's birthday?', 'Show upcoming birthdays', "
        "'How many birthdays are there in September?', or 'Where does Rahul Patil stay?'"
    )

