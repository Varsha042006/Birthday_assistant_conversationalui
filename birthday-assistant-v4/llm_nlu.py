from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Literal, Optional, Tuple
import pandas as pd
from pydantic import BaseModel, Field, field_validator


class EntitiesModel(BaseModel):
    person_name: Optional[str] = None
    relationship: Optional[str] = None
    month: Optional[int] = None
    relative_date: Optional[str] = None
    relative_month: Optional[str] = None
    place: Optional[str] = None

    @field_validator("month")
    def validate_month(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 12):
            raise ValueError(f"Month must be between 1 and 12, got {v}")
        return v


class NLUOutputModel(BaseModel):
    intent: Literal[
        "birthday_search",
        "count_birthdays",
        "upcoming_birthdays",
        "person_place",
        "unknown"
    ]
    entities: EntitiesModel


SYSTEM_PROMPT = """You are a Natural Language Understanding (NLU) semantic parser for a Birthday Assistant.
Your ONLY role is to analyze the user utterance and convert it into a structured JSON query object.

CRITICAL RULES:
1. You MUST NOT answer the user's question directly.
2. You MUST NOT invent birthdays, names, locations, dates, or relationships.
3. You MUST NOT access databases or spreadsheets.
4. You MUST return ONLY a JSON object matching this exact schema:
{
  "intent": "<intent>",
  "entities": {
    "person_name": <string or null>,
    "relationship": <string or null>,
    "month": <integer 1-12 or null>,
    "relative_date": <string or null>,
    "relative_month": <string or null>,
    "place": <string or null>
  }
}

ALLOWED INTENTS:
- "birthday_search": User asks when someone's birthday is, or asks to list/search birthdays by month, relationship, or date.
- "count_birthdays": User asks how many birthdays exist or wants to count birthdays (e.g. "how many", "count").
- "upcoming_birthdays": User asks about soon-to-occur birthdays (e.g. "upcoming birthdays", "birthdays coming soon").
- "person_place": User asks where a person lives, stays, or resides (e.g. "where does Rahul stay?").
- "unknown": Unrelated queries, general knowledge, greetings, or unsupported questions (e.g. "Who is the most intelligent person?").

ENTITY EXTRACTION GUIDELINES:
- "person_name": Full name or nickname mentioned (e.g. "Rahul", "Rahul Patil", "Nikhil").
- "relationship": Canonical relationship or family term (e.g. "Nephew", "Niece", "Wife", "Brother", "Sister", "Father", "Mother", "Cousin", "Friend", "Colleague", "Student", "Uncle", "Aunt", "Neighbour", "Sister-in-law", "Brother-in-law", "Sibling Family").
- "month": Calendar month as an integer from 1 (January) to 12 (December). Convert month words (e.g. "September" -> 9).
- "relative_date": "tomorrow" or "today" if mentioned.
- "relative_month": "next" if "next month" is mentioned.
- "place": City or location name if mentioned (e.g. "Bengaluru").
- Set any entity not explicitly mentioned to null.
"""


def get_openai_client():
    """Create OpenAI client if OPENAI_API_KEY is available."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI
        base_url = os.environ.get("OPENAI_BASE_URL")
        if base_url:
            return OpenAI(api_key=api_key, base_url=base_url)
        return OpenAI(api_key=api_key)
    except Exception as e:
        print(f"[llm_nlu] Failed to initialize OpenAI client: {e}")
        return None


def call_llm(message: str) -> Dict[str, Any]:
    """Call OpenAI API to semantically parse the utterance into validated JSON."""
    client = get_openai_client()
    if client is None:
        raise ValueError("OpenAI client is not configured or OPENAI_API_KEY is missing.")

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message}
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        timeout=10.0
    )

    raw_content = response.choices[0].message.content or "{}"
    data = json.loads(raw_content)

    # Validate against strict Pydantic model
    validated = NLUOutputModel.model_validate(data)
    return validated.model_dump()


def ground_entities(parsed: Dict[str, Any], df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """
    Ground LLM-extracted entities against the factual Excel dataset.
    - Resolves person_name to actual Person_ID using Name and Nickname columns.
    - Resolves relationship / relationship_group to canonical values from Excel.
    - Never invents a fake Person_ID.
    """
    grounded = {
        "intent": parsed.get("intent", "unknown"),
        "entities": dict(parsed.get("entities", {}))
    }
    e = grounded["entities"]

    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return grounded

    # 1. Ground person_name -> Person_ID
    person_name = e.get("person_name")
    if person_name and isinstance(person_name, str):
        cleaned_name = person_name.strip()
        candidates = []

        for _, row in df.iterrows():
            full = str(row.get("Name", "")).strip()
            nick = str(row.get("Nickname", "")).strip()
            p_id = str(row.get("Person_ID", "")).strip()

            # Exact match on nickname
            if nick and nick.casefold() == cleaned_name.casefold():
                candidates.append((p_id, full, nick, 1))
            # Exact match on full name
            elif full and full.casefold() == cleaned_name.casefold():
                candidates.append((p_id, full, nick, 2))
            # Word boundary / prefix match
            elif full and re.search(rf"\b{re.escape(cleaned_name.casefold())}\b", full.casefold()):
                candidates.append((p_id, full, nick, 3))
            elif nick and re.search(rf"\b{re.escape(cleaned_name.casefold())}\b", nick.casefold()):
                candidates.append((p_id, full, nick, 4))

        # Sort by match priority (1: exact nick, 2: exact full, 3: word match full, 4: word match nick)
        candidates.sort(key=lambda x: x[3])

        if candidates:
            best_priority = candidates[0][3]
            best_matches = [c for c in candidates if c[3] == best_priority]
            unique_best = {}
            for c in best_matches:
                if c[0] not in unique_best:
                    unique_best[c[0]] = c
            unique_list = list(unique_best.values())

            if len(unique_list) == 1:
                e["person_id"] = unique_list[0][0]
                e["person_name"] = unique_list[0][1]
            elif len(unique_list) > 1:
                # Ambiguous person name: multiple people match with equal priority
                e["person_id"] = None
                e["ambiguous_candidates"] = [
                    {"person_id": c[0], "name": c[1], "nickname": c[2]}
                    for c in unique_list
                ]
        else:
            # Person not found in Excel dataset: do not invent Person_ID
            e["person_id"] = None

    # 2. Ground relationship to canonical title case in Excel
    rel = e.get("relationship")
    if rel and isinstance(rel, str):
        rel_clean = rel.strip()
        matched_rel = None

        if "Relationship" in df.columns:
            for canonical in df["Relationship"].dropna().unique():
                c_str = str(canonical).strip()
                if c_str.casefold() == rel_clean.casefold() or \
                   f"{c_str.casefold()}s" == rel_clean.casefold():
                    matched_rel = c_str
                    break

        # Check Relationship_Group (e.g. 'Sibling Family')
        if not matched_rel and "Relationship_Group" in df.columns:
            for group in df["Relationship_Group"].dropna().unique():
                g_str = str(group).strip()
                if g_str.casefold() == rel_clean.casefold():
                    matched_rel = g_str
                    break

        if matched_rel:
            e["relationship"] = matched_rel

    return grounded


def parse_with_fallback(
    message: str,
    df: Optional[pd.DataFrame] = None,
    rule_parser: Optional[Any] = None
) -> Tuple[Dict[str, Any], str]:
    """
    Attempt to parse user utterance using LLM NLU.
    If LLM API is unavailable, unconfigured, or fails validation,
    safely falls back to the deterministic rule-based parser.

    Returns:
        (parsed_dict, parser_used)
        where parser_used is either "llm" or "rule_fallback".
    """
    # 1. Attempt LLM NLU if API key is present
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            llm_result = call_llm(message)
            grounded = ground_entities(llm_result, df)
            return grounded, "llm"
        except Exception as e:
            # Log error securely without exposing keys
            print(f"[llm_nlu] Fallback triggered due to LLM error: {type(e).__name__}: {e}")

    # 2. Fallback to rule-based parser from nlu.py
    if rule_parser is not None:
        rule_result = rule_parser(message, df)
    else:
        from nlu import parse
        rule_result = parse(message, df)

    return rule_result, "rule_fallback"
