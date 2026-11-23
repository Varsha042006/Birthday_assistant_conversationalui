import os
from pathlib import Path
import werkzeug
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.1.5"

import pandas as pd
from flask import Flask, jsonify, render_template, request, session
from llm_nlu import parse_with_fallback
from service import execute
from dialogue import (
    create_clarification_prompt,
    detect_ambiguity,
    enrich_with_context,
    extract_result_ids,
    is_reset_command,
    resolve_clarification,
    update_state,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-ue24cs3540-v4")

DATA_PATH = Path(__file__).resolve().parent / "data" / "people.xlsx"


def load_people(path=DATA_PATH) -> pd.DataFrame:
    """Load people dataset and ensure DOB datetime formatting."""
    df = pd.read_excel(path, sheet_name="People")
    df = df.copy()
    df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce")
    for col in ["Name", "Nickname", "Place_of_Stay", "Relationship",
                "Relationship_Group", "Relationship_Detail"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
    return df


PEOPLE = load_people()


@app.get("/")
def index():
    return render_template("index.html", record_count=len(PEOPLE))


@app.post("/chat")
@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()

    # 1. Check for conversation reset command
    if is_reset_command(message):
        session.clear()
        return jsonify({
            "answer": "Conversation context has been reset. How can I help you?",
            "debug": {
                "parser": "system",
                "intent": "reset",
                "raw_entities": {},
                "enriched_entities": {}
            },
            "state": {}
        })

    state = dict(session.get("dialogue_state", {}))

    # 2. Check whether answering a pending clarification question
    pending = state.get("pending_clarification")
    if pending:
        success, candidate, prompt = resolve_clarification(message, pending, PEOPLE)
        if success and candidate:
            p_id = candidate["person_id"]
            row = PEOPLE[PEOPLE["Person_ID"] == p_id].iloc[0]
            dob = row["DOB"]
            answer = f"{row['Name']}'s birthday is {dob.day} {dob.strftime('%B %Y')}."

            # Update state with resolved candidate and clear pending clarification
            state["person_id"] = p_id
            state["person_name"] = candidate["name"]
            state["last_result_ids"] = [p_id]
            state.pop("pending_clarification", None)
            session["dialogue_state"] = state

            return jsonify({
                "answer": answer,
                "debug": {
                    "parser": "dialogue_manager",
                    "intent": "clarification_resolved",
                    "raw_entities": {"person_id": p_id, "person_name": candidate["name"]},
                    "enriched_entities": {"person_id": p_id, "person_name": candidate["name"]},
                    "person_id": p_id
                },
                "state": state
            })
        elif prompt and not success:
            # Check if user instead entered a completely new valid query
            test_parsed, _ = parse_with_fallback(message, PEOPLE)
            if test_parsed.get("intent") != "unknown":
                # User switched topics; clear pending clarification and continue below
                state.pop("pending_clarification", None)
            else:
                # Still attempting to clarify but ambiguous or unrecognized
                return jsonify({
                    "answer": prompt,
                    "debug": {
                        "parser": "dialogue_manager",
                        "intent": "clarification_pending",
                        "raw_entities": {},
                        "enriched_entities": {}
                    },
                    "state": state
                })

    # 3. Parse user message with LLM NLU (with automatic rule fallback)
    parsed, parser_used = parse_with_fallback(message, PEOPLE)

    # 4. Enrich parsed result with conversation context
    enriched = enrich_with_context(parsed, state)

    # 5. Ambiguity detection
    is_ambiguous, candidates = detect_ambiguity(enriched, PEOPLE)
    if is_ambiguous:
        rel = enriched["entities"]["relationship"]
        state["pending_clarification"] = {
            "intent": enriched["intent"],
            "relationship": rel,
            "candidates": candidates
        }
        session["dialogue_state"] = state
        clarification_msg = create_clarification_prompt(rel, candidates)
        return jsonify({
            "answer": clarification_msg,
            "debug": {
                "parser": parser_used,
                "intent": enriched["intent"],
                "raw_entities": parsed.get("entities", {}),
                "enriched_entities": enriched.get("entities", {}),
                "person_id": enriched.get("entities", {}).get("person_id"),
                "ambiguity": True
            },
            "state": state
        })

    # 6. Execute query using existing service layer
    answer = execute(enriched, PEOPLE)

    # 7. Update state with interaction results
    result_ids = extract_result_ids(enriched, PEOPLE)
    state = update_state(enriched, state, last_result_ids=result_ids)
    session["dialogue_state"] = state

    return jsonify({
        "answer": answer,
        "debug": {
            "parser": parser_used,
            "intent": enriched["intent"],
            "raw_entities": parsed.get("entities", {}),
            "enriched_entities": enriched.get("entities", {}),
            "person_id": enriched.get("entities", {}).get("person_id")
        },
        "state": state
    })


@app.post("/reset")
@app.post("/api/reset")
def reset():
    session.clear()
    return jsonify({
        "status": "ok",
        "message": "Conversation context has been reset.",
        "state": {}
    })


@app.get("/api/health")
def health():
    llm_enabled = bool(os.environ.get("OPENAI_API_KEY"))
    return jsonify(
        status="ok",
        records=len(PEOPLE),
        version="V4",
        llm_enabled=llm_enabled,
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
