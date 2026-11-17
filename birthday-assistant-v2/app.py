from pathlib import Path
import pandas as pd
from flask import Flask, jsonify, render_template, request
from nlu import parse
from service import execute

app = Flask(__name__)

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


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = payload.get("message", "")
    parsed = parse(message, PEOPLE)
    answer = execute(parsed, PEOPLE)
    return jsonify({
        "answer": answer,
        "debug": parsed
    })


@app.get("/api/health")
def health():
    return jsonify(status="ok", records=len(PEOPLE), version="V2")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

