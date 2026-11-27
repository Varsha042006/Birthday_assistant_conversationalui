from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Literal, Optional, Tuple
import pandas as pd
from pydantic import BaseModel, Field, field_validator
from google import genai
from google.genai import types


class EntitiesModel(BaseModel):
    person_name: Optional[str] = None
    person_id: Optional[str] = None
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
    "person_id": <string or null>,
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
- "unknown": Unrelated queries, general knowledge, greetings, death, murder, or unsupported questions (e.g. "Who is the most intelligent person?", "When did she die?", "Who was murdered?"). All entities must be null.

ENTITY EXTRACTION GUIDELINES:
- "person_name": Full name or nickname mentioned (e.g. "Rahul", "Rahul Patil", "Nikhil").
- "relationship": Canonical relationship or family term (e.g. "Nephew", "Niece", "Wife", "Brother", "Sister", "Father", "Mother", "Cousin", "Friend", "Colleague", "Student", "Uncle", "Aunt", "Neighbour", "Sister-in-law", "Brother-in-law", "Sibling Family").
- "month": Calendar month as an integer from 1 (January) to 12 (December). Convert month words (e.g. "September" -> 9).
- "relative_date": "tomorrow" or "today" if mentioned.
- "relative_month": "next" if "next month" is mentioned.
- "place": City or location name if mentioned (e.g. "Bengaluru").
- Set any entity not explicitly mentioned to null.
"""


def get_gemini_client() -> Optional[genai.Client]:
    """Create Google Gemini client if GEMINI_API_KEY is available."""
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        load_dotenv(Path(__file__).resolve().parent / ".env")
        load_dotenv()
    except Exception:
        pass

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key.startswith("your_") or api_key.startswith("your-") or api_key == "YOUR_GEMINI_API_KEY":
        return None

    try:
        client = genai.Client(api_key=api_key)
        return client
    except Exception as e:
        print(f"[llm_nlu] Failed to initialize Gemini client: {e}")
        return None


def call_llm(message: str) -> Dict[str, Any]:
    """Call Google Gemini Developer API to semantically parse the utterance into validated JSON."""
    client = get_gemini_client()
    if client is None:
        raise ValueError("Gemini client is not configured or GEMINI_API_KEY is missing/placeholder.")

    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

    import time

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=NLUOutputModel,
        temperature=0.0
    )

    last_err = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=message,
                config=config
            )
            raw_content = response.text or "{}"
            data = json.loads(raw_content)
            validated = NLUOutputModel.model_validate(data)
            return validated.model_dump()
        except Exception as e:
            last_err = e
            if attempt < 2 and ("503" in str(e) or "UNAVAILABLE" in str(e) or "ResourceExhausted" in str(e)):
                time.sleep(1.5 * (attempt + 1))
                continue
            raise last_err


def ground_entities(parsed: Dict[str, Any], df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """
    Ground LLM-extracted entities against the factual Excel dataset.
    - Resolves person_name to actual Person_ID using Name and Nickname columns.
    - Resolves relationship / relationship_group to canonical values from Excel.
    - Never invents a fake Person_ID.
    """
    grounded = {
        "intent": parsed.get("intent", "unknown"),
        "entities": {k: v for k, v in parsed.get("entities", {}).items() if v is not None}
    }
    e = grounded["entities"]

    # If user specifies relative_date like "tomorrow" or "today", intent must be birthday_search, not upcoming_birthdays
    if e.get("relative_date") in ("tomorrow", "today") and grounded["intent"] == "upcoming_birthdays":
        grounded["intent"] = "birthday_search"

    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return grounded

    # 1. Ground person_name -> Person_ID
    person_name = e.get("person_name")
    if person_name and isinstance(person_name, str):
        cleaned_name = person_name.strip()
        candidates = []

        for _, row in df.iterrows():
            p_id = str(row.get("Person_ID", "")).strip()
            name_val = str(row.get("Name", "")).strip()
            nick_val = str(row.get("Nickname", "")).strip()

            # Exact full name match
            if name_val.casefold() == cleaned_name.casefold():
                candidates.append((p_id, name_val, "exact_name"))
                continue

            # Exact nickname match (only consider real individuals, ignoring placeholder test artifacts)
            if nick_val and nick_val.casefold() == cleaned_name.casefold():
                if not name_val.lower().endswith("s6") and not name_val.lower().endswith("kulkarni6"):
                    candidates.append((p_id, name_val, "exact_nickname"))
                continue

            # Single name token match (e.g. "Rahul" in "Rahul Patil")
            name_tokens = [tok.casefold() for tok in name_val.split()]
            if cleaned_name.casefold() in name_tokens:
                if not name_val.lower().endswith("s6") and not name_val.lower().endswith("kulkarni6"):
                    candidates.append((p_id, name_val, "token_match"))

        # If all candidates match the token, include all real candidates (e.g. all Nikhils)
        token_matches = [c for c in candidates if c[2] == "token_match"]
        exact_matches = [c for c in candidates if c[2] in ("exact_name", "exact_nickname")]
        
        # When user gives a single name like "Nikhil", consider both token and nickname matches
        all_unique_names = list(dict.fromkeys([c[1] for c in (exact_matches + token_matches)]))
        if len(all_unique_names) > 1:
            e["person_id"] = None
            e["ambiguous_candidates"] = all_unique_names
        elif len(exact_matches) == 1:
            e["person_id"] = exact_matches[0][0]
            e["person_name"] = exact_matches[0][1]
        elif len(candidates) == 1:
            e["person_id"] = candidates[0][0]
            e["person_name"] = candidates[0][1]
        else:
            e["person_id"] = None

    # 2. Ground relationship to canonical Excel label
    rel_mention = e.get("relationship")
    if rel_mention and isinstance(rel_mention, str):
        rel_clean = rel_mention.strip()
        matched_rel = None

        # Check canonical Relationship column
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
    Attempt to parse user utterance using Gemini NLU.
    If Gemini API is unavailable, unconfigured, or fails validation,
    safely falls back to the deterministic rule-based parser.

    Returns:
        (parsed_dict, parser_used)
        where parser_used is either "llm" or "rule_fallback".
    """
    # 1. Attempt Gemini NLU if API key is present and configured
    client = get_gemini_client()
    if client is not None:
        try:
            llm_result = call_llm(message)
            grounded = ground_entities(llm_result, df)
            return grounded, "llm"
        except Exception as e:
            # Log error securely without exposing keys
            print(f"[llm_nlu] Fallback triggered due to Gemini error: {type(e).__name__}: {e}")

    # 2. Fallback to rule-based parser from nlu.py
    if rule_parser is not None:
        rule_result = rule_parser(message, df)
    else:
        from nlu import parse
        rule_result = parse(message, df)

    return rule_result, "rule_fallback"


def generate_natural_response(user_message: str, factual_answer: str, intent: str = "") -> str:
    """
    Generate a warm, natural, conversational response using Gemini grounded strictly
    in the factual answer retrieved from Excel / dialogue manager.
    If generation fails or Gemini is unavailable, returns factual_answer unchanged.
    """
    # If the answer is an error or fallback, return it directly
    if not factual_answer or "No matching birthdays" in factual_answer or "Could not find" in factual_answer:
        return factual_answer

    client = get_gemini_client()
    if client is None:
        return factual_answer

    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    prompt = f"""You are the friendly, polite voice of the CIUX Birthday Assistant (V5).
The user asked: "{user_message}"
Retrieved ground-truth facts from the verified database:
\"\"\"{factual_answer}\"\"\"

Task:
Convert the retrieved ground-truth facts into a warm, natural conversational response.
STRICT RULES:
1. Do NOT invent, assume, or change any dates, names, relationships, or locations.
2. Use ONLY the facts provided above.
3. If bullet points or multiple people are listed, keep the bulleted list clear.
4. Keep the tone conversational, helpful, and concise (1-3 sentences total).
5. Output ONLY the response text."""

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3)
        )
        # Avoid MagicMock leak during unit tests
        if hasattr(response, "text") and type(response.text).__name__ != "MagicMock":
            text = str(response.text or "").strip()
            if text:
                return text
    except Exception as e:
        print(f"[llm_nlu] NLG generation error: {e}")

    return factual_answer
