from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd


def is_greeting(message: str) -> bool:
    """Check if the user utterance is a standard conversational greeting."""
    cleaned = (message or "").strip().lower()
    cleaned = re.sub(r"[^\w\s]", "", cleaned).strip()
    greeting_patterns = [
        r"^(hi|hello|hey|heya|howdy|namaste|greetings)(\s+there)?$",
        r"^good\s+(morning|afternoon|evening|day)$"
    ]
    return any(re.match(pat, cleaned) for pat in greeting_patterns)


def is_reset_command(message: str) -> bool:
    """Check if the user requested a conversation reset."""
    cleaned = (message or "").strip().lower()
    cleaned = re.sub(r"[^\w\s]", "", cleaned).strip()
    reset_patterns = [
        r"^reset(\s+the)?(\s+conversation)?$",
        r"^clear(\s+the)?(\s+conversation)?$",
        r"^restart(\s+the)?(\s+conversation)?$",
        r"^start\s+over$"
    ]
    return any(re.match(pat, cleaned) for pat in reset_patterns)


def is_general_query(text: str) -> bool:
    """Check if an utterance is an open/general birthday query rather than a follow-up."""
    if not text:
        return False
    t = text.lower().strip()
    if re.search(r"\b(whose|who|anyone|anybody|everyone|everybody|all|list\s+all)\b", t):
        return True
    if re.search(r"^(any\s+)?birthdays?\s+(in|of|for)?\s+[a-z]+", t) and not re.search(r"\b(what\s+about|how\s+about|and)\b", t):
        return True
    return False


def enrich_with_context(
    parsed: Dict[str, Any],
    state: Dict[str, Any],
    raw_message: str = ""
) -> Dict[str, Any]:
    """
    Receive the parsed NLU result and current dialogue state.
    Carries forward relevant context (month, relationship) when the new turn
    does not provide them and the previous context is relevant.
    Replaces old values if new values are explicitly present.
    """
    enriched = {
        "intent": parsed.get("intent", "unknown"),
        "entities": {k: v for k, v in parsed.get("entities", {}).items() if v is not None}
    }
    e = enriched["entities"]
    intent = enriched["intent"]

    # If the user utterance is an elliptical follow-up (e.g. 'What about October?', 'How about nieces?', 'And next month?')
    # or was parsed as unknown, inherit the previous active intent (e.g. 'count_birthdays' or 'birthday_search')
    is_elliptical = bool(re.search(r"^(what|how)\s+about\b", (raw_message or "").strip().lower()) or
                         re.search(r"^(and|also)\b", (raw_message or "").strip().lower()))
    if is_elliptical and state.get("last_intent"):
        enriched["intent"] = state["last_intent"]
        intent = enriched["intent"]
    elif intent == "unknown":
        if ("month" in e or "relationship" in e or "relative_month" in e) and (
            state.get("relationship") or state.get("month") or state.get("last_intent")
        ):
            enriched["intent"] = state.get("last_intent", "birthday_search")
            intent = enriched["intent"]

    # Do not apply birthday context to unrelated or location queries
    if intent not in ("birthday_search", "count_birthdays", "upcoming_birthdays"):
        return enriched

    # If user explicitly searched for a person by name or ID, do not inherit relationship
    if "person_id" in e or "person_name" in e:
        return enriched

    # If the query is an open/general query (e.g. 'Whose birthday in September',
    # 'Birthday in September month', 'Birthdays in October month'), do not inherit
    # a previously active relationship filter.
    is_general = is_general_query(raw_message)

    # Carry forward month and relationship if not present in new turn
    for key in ("month", "relationship"):
        if (key not in e or e[key] is None) and state.get(key) is not None:
            if key == "relationship" and is_general:
                continue
            # If relative_month is explicitly specified in new turn, do not carry forward calendar month
            if key == "month" and "relative_month" in e:
                continue
            e[key] = state[key]

    return enriched


def detect_ambiguity(parsed: Dict[str, Any], df: pd.DataFrame) -> Tuple[bool, List[Dict[str, str]]]:
    """
    Check if a query is ambiguous because:
    1. It asks for a person by relationship matching multiple candidates (e.g. 'When is my nephew's birthday?').
    2. Or it asks for a person by name/nickname that matches multiple people (e.g. 'When was Nikhil birthday?').
    Returns (is_ambiguous, candidates_list).
    """
    intent = parsed.get("intent")
    entities = parsed.get("entities", {})

    if df is None or df.empty:
        return False, []

    # Case A: Ambiguous person name detected during NLU grounding
    ambiguous_names = entities.get("ambiguous_candidates")
    if ambiguous_names and isinstance(ambiguous_names, list) and len(ambiguous_names) > 1:
        candidates = []
        for name in ambiguous_names:
            matches = df[df["Name"].str.casefold() == str(name).strip().casefold()]
            if not matches.empty:
                r = matches.iloc[0]
                candidates.append({
                    "person_id": str(r["Person_ID"]),
                    "name": str(r["Name"]),
                    "nickname": str(r["Nickname"]).strip() if pd.notna(r["Nickname"]) else ""
                })
            else:
                candidates.append({"person_id": "", "name": str(name), "nickname": ""})
        return True, candidates

    # Ambiguity check applies to birthday_search with relationship
    # and no specific person name, person_id, month, or date filter.
    if intent != "birthday_search":
        return False, []

    if "person_id" in entities or "person_name" in entities:
        return False, []

    if "month" in entities or "relative_date" in entities or "relative_month" in entities:
        return False, []

    rel = entities.get("relationship")
    if not rel:
        return False, []

    matches = df[df["Relationship"].str.casefold() == rel.casefold()]

    # If relationship is 'Wife' and 1 record is marked as Spouse, resolve directly without ambiguity
    if rel.lower() == "wife" and not matches.empty:
        spouse = matches[matches["Relationship_Detail"].str.casefold() == "spouse"]
        if not spouse.empty:
            matches = spouse

    if len(matches) > 1:
        candidates = []
        for _, r in matches.iterrows():
            nickname = str(r["Nickname"]).strip() if pd.notna(r["Nickname"]) else ""
            candidates.append({
                "person_id": str(r["Person_ID"]),
                "name": str(r["Name"]),
                "nickname": nickname
            })
        return True, candidates

    return False, []


def create_clarification_prompt(relationship_or_name: str, candidates: List[Dict[str, str]]) -> str:
    """Generate a polite clarification prompt listing matching candidates."""
    names = [c["name"] for c in candidates]
    names_str = ", ".join(names)
    count = len(candidates)
    if relationship_or_name:
        # Check if relationship_or_name is a known relationship
        is_rel = relationship_or_name.lower() in [
            "nephew", "niece", "sister", "brother", "friend", "cousin", "wife", "uncle", "aunt",
            "father", "mother", "son", "daughter", "colleague", "student", "brother-in-law"
        ]
        if is_rel:
            return (
                f"I found multiple people with the relationship {relationship_or_name}:\n"
                f"{names_str}\n"
                f"Which person's birthday would you like to know?"
            )
        return (
            f"There are {count} people named {relationship_or_name}: {names_str}. "
            f"Whom do you want?"
        )
    return (
        f"There are {count} matching people: {names_str}. "
        f"Whom do you want?"
    )


def resolve_clarification(
    message: str,
    pending: Dict[str, Any],
    df: pd.DataFrame
) -> Tuple[bool, Optional[Dict[str, str]], Optional[str]]:
    """
    Attempt to resolve a user response against pending clarification candidates.
    Returns:
      (True, candidate_dict, None) on successful unique resolution
      (False, None, disambiguation_prompt) if multiple candidates match
      (False, None, error_prompt) if no candidate matches
    """
    candidates = pending.get("candidates", [])
    if not candidates:
        return False, None, "No pending clarification candidates found."

    text = (message or "").strip().lower()

    # 1. First priority: Exact match on nickname (e.g. 'Nikhil' -> Nikhil Hegde whose nickname is 'Nikhil')
    exact_nick_matches = [
        c for c in candidates
        if c.get("nickname") and c["nickname"].lower() == text
    ]
    if len(exact_nick_matches) == 1:
        return True, exact_nick_matches[0], None

    # 2. Second priority: Exact match on full name
    exact_name_matches = [
        c for c in candidates
        if c.get("name") and c["name"].lower() == text
    ]
    if len(exact_name_matches) == 1:
        return True, exact_name_matches[0], None

    # 3. Third priority: Word boundary / substring match
    fuzzy_matches = []
    for c in candidates:
        name_parts = c["name"].lower().split()
        cand_nick = c.get("nickname", "").lower()
        if re.search(rf"\b{re.escape(c['name'].lower())}\b", text):
            fuzzy_matches.append(c)
        elif cand_nick and re.search(rf"\b{re.escape(cand_nick)}\b", text):
            fuzzy_matches.append(c)
        elif any(part == text for part in name_parts):
            fuzzy_matches.append(c)

    # Deduplicate fuzzy matches by person_id
    unique_matches = {m["person_id"]: m for m in fuzzy_matches}.values()
    unique_matches = list(unique_matches)

    if len(unique_matches) == 1:
        return True, unique_matches[0], None
    elif len(unique_matches) > 1:
        names = ", ".join(m["name"] for m in unique_matches)
        return (
            False,
            None,
            f"Multiple people match '{message}': {names}. Please provide their full name."
        )

    # No match found
    all_names = ", ".join(c["name"] for c in candidates)
    return (
        False,
        None,
        f"I didn't recognize '{message}' among the matching candidates: {all_names}. "
        f"Please specify which person you mean."
    )


def update_state(
    parsed: Dict[str, Any],
    state: Dict[str, Any],
    last_result_ids: Optional[List[str]] = None,
    raw_message: str = ""
) -> Dict[str, Any]:
    """
    Update dialogue state after a successful interaction turn.
    Preserves relevant existing context unless explicitly replaced.
    """
    new_state = dict(state or {})
    entities = parsed.get("entities", {})
    intent = parsed.get("intent", "unknown")

    if intent == "unknown":
        return new_state

    new_state["last_intent"] = intent

    # Update or replace month
    if "month" in entities:
        new_state["month"] = entities["month"]
        new_state.pop("relative_month", None)
    elif "relative_month" in entities:
        new_state.pop("month", None)
        new_state["relative_month"] = entities["relative_month"]

    # Update or replace relationship
    if "relationship" in entities:
        new_state["relationship"] = entities["relationship"]
    elif is_general_query(raw_message):
        new_state.pop("relationship", None)
        new_state.pop("person_id", None)
        new_state.pop("person_name", None)

    # Update or replace person
    if "person_id" in entities:
        new_state["person_id"] = entities["person_id"]
    if "person_name" in entities:
        new_state["person_name"] = entities["person_name"]

    if last_result_ids is not None:
        new_state["last_result_ids"] = list(last_result_ids)

    # Clear pending clarification on successful standard interaction
    new_state.pop("pending_clarification", None)

    return new_state


def extract_result_ids(parsed: Dict[str, Any], df: pd.DataFrame) -> List[str]:
    """Helper to determine Person_IDs of records matching the enriched query."""
    if df is None or df.empty:
        return []

    entities = parsed.get("entities", {})
    work = df.copy()

    if entities.get("person_id"):
        work = work[work["Person_ID"] == entities["person_id"]]
        return work["Person_ID"].tolist()

    if entities.get("person_name"):
        work = work[work["Name"].str.casefold() == entities["person_name"].casefold()]
        return work["Person_ID"].tolist()

    if entities.get("relationship"):
        rel = entities["relationship"]
        is_rel = work["Relationship"].str.casefold() == rel.casefold()
        if "Relationship_Group" in work.columns:
            is_rel = is_rel | (work["Relationship_Group"].str.casefold() == rel.casefold())
        work = work[is_rel]

    if entities.get("month"):
        work = work[work["DOB"].dt.month == entities["month"]]

    return work["Person_ID"].tolist()
