import os
import sys
import json
from pathlib import Path

# Add project root
V4_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(V4_DIR))

import pandas as pd
from dotenv import load_dotenv
load_dotenv(V4_DIR / ".env")

from llm_nlu import call_llm, ground_entities, parse_with_fallback, get_gemini_client, NLUOutputModel
from service import execute

DATA_PATH = V4_DIR / "data" / "people.xlsx"
df = pd.read_excel(DATA_PATH, sheet_name="People")
df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce")

TEST_QUESTIONS = [
    "Do I need to wish any nephew during September?",
    "Are there people from my sibling family celebrating next month?",
    "I was wondering whether Rahul has a birthday coming soon.",
    "Could you check if anyone among my cousins was born in the final month of the year?"
]


def run_evaluation():
    print("=" * 70)
    print("CIUX BIRTHDAY ASSISTANT - V4 EVALUATION (GEMINI & FALLBACK)")
    print("=" * 70)

    client = get_gemini_client()
    has_real_key = client is not None
    print(f"Gemini Client Configured: {has_real_key}")
    if has_real_key:
        print(f"Active Model: {os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')}")
    else:
        print("Note: GEMINI_API_KEY is currently placeholder. Live calls require your actual key in .env.")

    print("\n" + "-" * 70)
    print("PART 1: TESTING THE 4 EXACT MANDATORY QUESTIONS")
    print("-" * 70)

    for i, q in enumerate(TEST_QUESTIONS, 1):
        print(f"\n[Test Case {i}] Question: \"{q}\"")

        gemini_called = False
        raw_json_str = None
        validation_status = None
        parsed_dict = None
        parser_used = None

        if has_real_key:
            try:
                gemini_called = True
                parsed_dict = call_llm(q)
                raw_json_str = json.dumps(parsed_dict, indent=2)
                validation_status = "PASSED (Validated against NLUOutputModel Pydantic schema)"
                parser_used = "llm (Gemini)"
            except Exception as e:
                print(f"  Gemini call failed with error: {e}")
                parsed_dict, parser_used = parse_with_fallback(q, df)
                raw_json_str = "N/A (Failed before output)"
                validation_status = f"FAILED ({type(e).__name__})"
        else:
            # Fallback mode
            parsed_dict, parser_used = parse_with_fallback(q, df)
            validation_status = "N/A (Processed via rule fallback)"

        # Grounding against Excel
        grounded = ground_entities(parsed_dict, df)
        grounding_result = grounded["entities"]

        # Final answer from service.py
        answer = execute(grounded, df)

        print(f"  • Gemini API Called:    {gemini_called}")
        if gemini_called:
            print(f"  • Raw JSON Output:\n{raw_json_str}")
        print(f"  • Schema Validation:    {validation_status}")
        print(f"  • Excel Grounding:      {json.dumps(grounding_result)}")
        print(f"  • Parser Used:          {parser_used}")
        print(f"  • Final Answer:\n    {answer.replace(chr(10), chr(10) + '    ')}")

    print("\n" + "-" * 70)
    print("PART 2: DEDICATED FALLBACK VERIFICATION TEST")
    print("-" * 70)
    print("Simulating API unavailability / missing key...")
    saved_key = os.environ.get("GEMINI_API_KEY")
    os.environ["GEMINI_API_KEY"] = ""  # Force fallback
    fb_parsed, fb_parser = parse_with_fallback("Do I need to wish any nephew during September?", df)
    fb_grounded = ground_entities(fb_parsed, df)
    fb_answer = execute(fb_grounded, df)
    if saved_key:
        os.environ["GEMINI_API_KEY"] = saved_key

    print(f"  • Question:             \"Do I need to wish any nephew during September?\"")
    print(f"  • Parser Used:          {fb_parser} (Expected: rule_fallback)")
    print(f"  • Fallback Intent:      {fb_parsed.get('intent')}")
    print(f"  • Fallback Entities:    {fb_grounded.get('entities')}")
    print(f"  • Fallback Answer:\n    {fb_answer.replace(chr(10), chr(10) + '    ')}")
    assert fb_parser == "rule_fallback", "Fallback test failed!"
    print("  • Fallback Status:      VERIFIED (Rule fallback successfully engaged)")

    print("\n" + "=" * 70)
    print("EVALUATION COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    run_evaluation()
