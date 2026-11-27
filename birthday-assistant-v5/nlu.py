import re
import calendar
from typing import Any, Dict, Optional
import pandas as pd

# Standard month name to number mapping
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTH_ABBRS = {name.lower(): i for i, name in enumerate(calendar.month_abbr) if name}

# Common relationship aliases and plural forms
CANONICAL_RELATIONSHIP_ALIASES = {
    "wife": "Wife", "wives": "Wife", "spouse": "Wife",
    "father": "Father", "dad": "Father", "appa": "Father", "fathers": "Father",
    "mother": "Mother", "mom": "Mother", "amma": "Mother", "mothers": "Mother",
    "brother": "Brother", "brothers": "Brother",
    "sister": "Sister", "sisters": "Sister",
    "nephew": "Nephew", "nephews": "Nephew",
    "niece": "Niece", "nieces": "Niece",
    "uncle": "Uncle", "uncles": "Uncle",
    "aunt": "Aunt", "aunts": "Aunt",
    "cousin": "Cousin", "cousins": "Cousin",
    "friend": "Friend", "friends": "Friend",
    "colleague": "Colleague", "colleagues": "Colleague",
    "student": "Student", "students": "Student",
    "neighbour": "Neighbour", "neighbours": "Neighbour",
    "neighbor": "Neighbour", "neighbors": "Neighbour",
    "sister-in-law": "Sister-in-law", "sisters-in-law": "Sister-in-law",
    "brother-in-law": "Brother-in-law", "brothers-in-law": "Brother-in-law"
}


def _match_word(pattern_word: str, text: str) -> bool:
    """Case-insensitive exact word/phrase boundary matching."""
    escaped = re.escape(pattern_word.strip().lower())
    # Handle possessives such as Rahul's or wife's
    regex = rf"(?<!\w){escaped}(?:'s)?(?!\w)"
    return re.search(regex, text.lower()) is not None


def extract_month(text: str) -> Optional[int]:
    """Extract calendar month (1-12) from utterance if explicitly mentioned."""
    # Check full names first
    for name, num in MONTHS.items():
        if _match_word(name, text):
            # Guard against modal verb "may I..." if not asking about May
            if name == "may":
                if re.search(r"\bmay\s+(i|we|you|they|he|she)\b", text.lower()):
                    continue
            return num
    # Check 3-letter abbreviations (e.g. sep, oct, dec)
    for abbr, num in MONTH_ABBRS.items():
        if len(abbr) >= 3 and _match_word(abbr, text):
            if abbr == "may":
                continue
            return num
    return None


def extract_person(text: str, df: Optional[pd.DataFrame]) -> tuple[Optional[str], Optional[str]]:
    """
    Match Name and Nickname against utterance using word boundaries.
    Prefers longer name matches over shorter ones.
    Returns (person_id, person_name) or (None, None).
    """
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None, None

    candidates = []
    for _, row in df.iterrows():
        p_id = str(row.get("Person_ID", "")).strip()
        full_name = str(row.get("Name", "")).strip()
        nickname = str(row.get("Nickname", "")).strip()

        if full_name:
            candidates.append((full_name, p_id, full_name))
        if nickname and nickname.lower() != full_name.lower():
            candidates.append((nickname, p_id, full_name))

    # Prefer longer name matches first (e.g., "Rahul Patil" before "Rahul")
    candidates.sort(key=lambda c: len(c[0]), reverse=True)

    text_lower = text.lower()
    for match_term, p_id, canonical_name in candidates:
        if len(match_term) < 2:
            continue
        escaped = re.escape(match_term.lower())
        regex = rf"(?<!\w){escaped}(?:'s)?(?!\w)"
        if re.search(regex, text_lower):
            return p_id, canonical_name

    return None, None


def extract_relationship(text: str, df: Optional[pd.DataFrame]) -> Optional[str]:
    """
    Extract relationship canonical label from utterance.
    Supports relationship values from Excel and common plural/alias forms.
    """
    relationship_map = dict(CANONICAL_RELATIONSHIP_ALIASES)

    # Dynamically incorporate relationships present in the dataset
    if df is not None and isinstance(df, pd.DataFrame) and "Relationship" in df.columns:
        for rel in df["Relationship"].dropna().unique():
            rel_str = str(rel).strip()
            if not rel_str:
                continue
            rel_lower = rel_str.lower()
            if rel_lower not in relationship_map:
                relationship_map[rel_lower] = rel_str
            plural = f"{rel_lower}s"
            if plural not in relationship_map:
                relationship_map[plural] = rel_str

    # Sort aliases by length descending so multi-word aliases match before shorter ones
    for alias in sorted(relationship_map.keys(), key=len, reverse=True):
        if _match_word(alias, text):
            return relationship_map[alias]

    return None


def parse(message: str, people: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    Natural Language Understanding layer.
    Extracts structured intent and entities from a user message.

    Returns:
    {
        "intent": "birthday_search" | "count_birthdays" | "upcoming_birthdays" | "person_place" | "unknown",
        "entities": {
            "person_id": str,
            "person_name": str,
            "relationship": str,
            "month": int,
            "relative_date": str,
            "relative_month": str
        }
    }
    """
    cleaned = (message or "").strip()
    if not cleaned:
        return {"intent": "unknown", "entities": {}}

    text_lower = cleaned.lower()

    # 0. Out-of-domain / unsupported topics (e.g. death, murder, illness, unrelated events)
    unsupported_pattern = r"\b(die|died|death|dying|murder|murdered|murdering|kill|killed|killing|dead|passed\s+away|suicide|crime|shot|stabbed|funeral|accident|hospital|hospitalized|disease|illness|marry|married|wedding|divorce|divorced)\b"
    if re.search(unsupported_pattern, text_lower):
        return {"intent": "unknown", "entities": {}}

    entities: Dict[str, Any] = {}

    # 1. Entity Extraction: Person (Name / Nickname) -> Person_ID
    p_id, p_name = extract_person(cleaned, people)
    if p_id and p_name:
        entities["person_id"] = p_id
        entities["person_name"] = p_name

    # 2. Entity Extraction: Relationship
    rel = extract_relationship(cleaned, people)
    if rel:
        entities["relationship"] = rel

    # 3. Entity Extraction: Relative Month ("next month")
    if re.search(r"\bnext\s+month\b", text_lower):
        entities["relative_month"] = "next"
    else:
        # 4. Entity Extraction: Calendar Month (1-12)
        month_num = extract_month(cleaned)
        if month_num is not None:
            entities["month"] = month_num

    # 5. Entity Extraction: Relative Date ("tomorrow")
    if re.search(r"\btomorrow\b", text_lower):
        entities["relative_date"] = "tomorrow"

    # ==========================================
    # Intent Classification
    # ==========================================

    # A. person_place: Location / Where does person live or stay
    place_keywords = ["stay", "stays", "staying", "live", "lives", "living", "reside", "resides", "place of stay", "place"]
    has_place_verb = any(_match_word(k, text_lower) for k in place_keywords)
    has_where = bool(re.search(r"\bwhere\b", text_lower))

    if (has_where and (has_place_verb or "person_id" in entities or "relationship" in entities)) or \
       (has_place_verb and ("person_id" in entities or "relationship" in entities)):
        return {"intent": "person_place", "entities": entities}

    # B. count_birthdays: Queries asking how many birthdays exist or counting them
    count_pattern = r"\b(how\s+many|count|number\s+of|total\s+number\s+of|total\s+count)\b"
    if re.search(count_pattern, text_lower):
        return {"intent": "count_birthdays", "entities": entities}

    # C. upcoming_birthdays: Upcoming or soon-to-occur birthdays (not specific month queries)
    upcoming_pattern = r"\b(upcoming|coming\s+up|soon|near\s+future|coming\s+birthdays)\b"
    if re.search(upcoming_pattern, text_lower) and "relative_month" not in entities and "month" not in entities:
        return {"intent": "upcoming_birthdays", "entities": entities}

    # D. birthday_search: Asking for a birthday, listing birthdays by date/month/relationship
    birthday_pattern = r"\b(birthday|birthdays|bday|bdays|b-day|b-days|born|dob|date\s+of\s+birth)\b"
    has_birthday_word = bool(re.search(birthday_pattern, text_lower))

    if has_birthday_word or \
       ("person_id" in entities and (has_birthday_word or not re.search(r"\b(did|does|is|was|will|can|why|how)\b", text_lower))) or \
       "relative_month" in entities or \
       "relative_date" in entities or \
       ("month" in entities and ("relationship" in entities or re.search(r"\b(show|any|who|whose|list|tell|what|find|is\s+there|are\s+there)\b", text_lower))) or \
       ("relationship" in entities and has_birthday_word):
        return {"intent": "birthday_search", "entities": entities}

    # E. Unsupported or unrelated queries
    return {"intent": "unknown", "entities": entities}

