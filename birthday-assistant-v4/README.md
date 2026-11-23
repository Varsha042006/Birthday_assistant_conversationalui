# CIUX Birthday Assistant — Version 4 (V4)

**GM University · School of Computer Science and Technology**  
**Course:** UE24CS3540 — Conversational Interfaces and UX  
**Version:** V4 — LLM-Assisted NLU with Grounded Structured Queries  

---

## 1. What V4 Adds Over V3

Version 3 relied on rigid regular expressions and keyword pattern matching. While V3 handled explicit phrasing well, it struggled with complex syntax, indirect questions, synonyms, and conversational paraphrasing (e.g. *"Do I need to wish any nephew during September?"* or *"Could you check if anyone among my cousins was born in the final month of the year?"*).

**Version 4 introduces a hybrid LLM/Rule architecture:**
* **LLM Semantic Parser (`llm_nlu.py`):** Uses an LLM solely to comprehend natural language and produce structured JSON query intents and entities.
* **No LLM Hallucination:** The LLM is **strictly forbidden** from generating facts, names, or dates.
* **Excel Grounding:** Extracted names, nicknames, and relationships are verified and grounded against the actual `people.xlsx` dataset, resolving canonical `Person_ID`s.
* **Deterministic Fallback:** If the LLM API key is omitted, unavailable, times out, or returns invalid JSON, the system smoothly falls back to the V3 rule-based parser without crashing.
* **Preserved V3 Dialogue Engine:** Multi-turn context carry-over, ambiguity detection, clarification prompts, and conversation reset remain fully operational.

---

## 2. Architecture & Pipeline

```
User Question
      │
      ▼
LLM NLU (llm_nlu.py) ──[Fallback on Error/No Key]──► Rule Parser (nlu.py)
      │                                                       │
      ▼                                                       ▼
Validate Structured JSON (Pydantic schema validation)
      │
      ▼
Ground Entities against Excel (Name/Nickname → Person_ID, Relationship_Group)
      │
      ▼
Apply Dialogue Context (enrich_with_context from dialogue.py)
      │
      ▼
Ambiguity Detection (detect_ambiguity: prompt clarification if multiple matches)
      │
      ▼
Service Layer (execute from service.py) ◄── people.xlsx (Single Source of Truth)
      │
      ▼
Factual Answer + Debug Payload (Parser Used, Intent, Entities, State)
      │
      ▼
Frontend Chat UI
```

---

## 3. Structured Output Schema

The semantic parser returns structured JSON with strictly validated fields:

```json
{
  "intent": "birthday_search",
  "entities": {
    "person_name": "Rahul Patil",
    "relationship": "Nephew",
    "month": 9,
    "relative_date": null,
    "relative_month": null,
    "place": null
  }
}
```

* **Allowed Intents:** `birthday_search`, `count_birthdays`, `upcoming_birthdays`, `person_place`, `unknown`.
* **Allowed Entities:** `person_name`, `relationship`, `month` (1-12), `relative_date`, `relative_month`, `place`.
* Unmentioned entities are set to `null`.

---

## 4. Excel Grounding & Factual Safety

1. **Person Matching:** When `person_name` is extracted, it is matched against `Name` and `Nickname` in `people.xlsx`.
2. **ID Resolution:** If exactly one person matches, their `Person_ID` (e.g. `P004`) is attached.
3. **Fictional Names:** If no person matches (e.g. *"Bruce Wayne"*), `person_id` remains `null`. No fake IDs are ever generated.
4. **Relationship Normalization:** Relationships are mapped to canonical title-case values or group values (e.g., `Sibling Family`) in `people.xlsx`.
5. **DOB & Place Safety:** The LLM never supplies dates of birth or locations; all dates and places come exclusively from the spreadsheet.

---

## 5. Configuration & Environment Variables

Copy `.env.example` to `.env`:

```powershell
cp .env.example .env
```

Configure your parameters:

```ini
# OpenAI API Key (optional - if omitted, system automatically uses Rule-Based Fallback)
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-4o-mini
# OPENAI_BASE_URL=https://api.openai.com/v1

# Flask session secret
SECRET_KEY=your-random-secret-key
```

*Note: Never commit `.env` or API credentials to version control. `.env` is listed in `.gitignore`.*

---

## 6. Installation & Running on Windows PowerShell

```powershell
# 1. Navigate to the V4 project directory
cd E:\projects\CIUX_Birthday_Assistant_V1\birthday-assistant-v4

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the automated test suite
python -m pytest tests -v -s

# 4. Start the Flask server
python app.py
```

Open your browser at **`http://127.0.0.1:5000`**.

---

## 7. Verified Test Checkpoints

| Query | Parser Used | Intent | Extracted & Grounded Entities | Factual Result from Excel |
| :--- | :--- | :--- | :--- | :--- |
| **"Do I need to wish any nephew during September?"** | LLM / Fallback | `birthday_search` | `relationship: "Nephew"`, `month: 9` | Lists Rahul Patil, Nikhil Bhat, Bharath Rao |
| **"Are there people from my sibling family celebrating next month?"** | LLM | `birthday_search` | `relationship: "Sibling Family"`, `relative_month: "next"` | Lists Varun Kumar (Nephew, Dec 17) |
| **"I was wondering whether Rahul has a birthday coming soon."** | LLM | `birthday_search` | `person_name: "Rahul Patil"`, `person_id: "P004"` | `"Rahul Patil's birthday is 18 September 2004."` |
| **"Could you check if anyone among my cousins was born in the final month of the year?"** | LLM | `birthday_search` | `relationship: "Cousin"`, `month: 12` | Lists Shreyas Desai (Cousin, Dec 16) |
| **"When is Bruce Wayne's birthday?"** | LLM / Fallback | `birthday_search` | `person_name: "Bruce Wayne"`, `person_id: null` | `"No matching birthdays found."` |
| **"What is the capital of France?"** | LLM / Fallback | `unknown` | `{}` | Fallback guidance message |
