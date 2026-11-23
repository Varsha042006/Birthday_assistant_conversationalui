# CIUX Birthday Assistant — Version 3 (V3)

**GM University · School of Computer Science and Technology**  
**Course:** UE24CS3540 — Conversational Interfaces and UX  
**Version:** V3 — Dialogue State, Context and Clarification  

Version 3 extends Version 2's Intent & Entity NLU by introducing **Dialogue State Management**, **Context Carry-Over**, **Ambiguity Detection**, **Clarification Resolution**, and **Session Reset**.

---

## Architecture Overview

```
User Message
     ↓
Flask app.py (/api/chat)
     ↓
dialogue.py: Check Reset? → Check Pending Clarification?
     ↓
nlu.py: parse(message, df)
     ↓
dialogue.py: enrich_with_context(parsed, state)
     ↓
dialogue.py: detect_ambiguity(enriched, df)
     ↓ (If ambiguous) → Generate clarification prompt & save candidate IDs to session
     ↓ (If clear)
service.py: execute(enriched, df)
     ↓
dialogue.py: update_state(enriched, state)
     ↓
JSON Response: { answer, debug, state } → Browser Chat UI
```

---

## Project Structure

```
birthday-assistant-v3/
├── app.py                     # Flask session-enabled controller with chat & reset endpoints
├── dialogue.py                # Dialogue state, context carry-over & clarification resolution
├── nlu.py                     # Rule-based intent classification & entity extraction
├── service.py                 # Spreadsheet filtering & response generation
├── requirements.txt           # Dependencies (Flask, pandas, openpyxl, pytest)
├── README.md                  # V3 documentation
├── data/
│   └── people.xlsx            # 100 synthetic contact records (single source of truth)
├── templates/
│   └── index.html             # Chat UI with live Dialogue State & NLU debug panel
├── static/
│   ├── chat.js                # Frontend chat logic, multi-turn handling & reset button
│   └── style.css              # Academic theme styling
└── tests/
    ├── test_dialogue.py       # Unit tests for dialogue state, ambiguity & clarification
    ├── test_v3_conversations.py # Multi-turn checkpoint integration tests
    ├── test_nlu.py            # Preserved NLU tests from V2
    └── test_service.py        # Preserved Service tests from V2
```

---

## Setup & Running on Windows PowerShell

```powershell
# 1. Navigate to the V3 folder
cd E:\projects\CIUX_Birthday_Assistant_V1\birthday-assistant-v3

# 2. Run the automated test suite
python -m pytest tests -v -s

# 3. Start the Flask server
python app.py
```

Open **`http://127.0.0.1:5000`** in your browser.

---

## Verified Multi-Turn Conversations

1. **Month Context Carry-Over:**
   * User: *"Any nephew birthdays in September?"* → Assistant lists September nephews (Rahul Patil, Nikhil Bhat, Bharath Rao).
   * User: *"What about October?"* → Assistant retains `relationship = Nephew`, replaces month with October, and returns Nikhil Hegde (October nephew).

2. **Ambiguity & Clarification:**
   * User: *"When is my nephew's birthday?"* → Assistant detects 12 matching nephews and lists them, asking which person is meant.
   * User: *"Nikhil"* → Assistant resolves to Nikhil Hegde and returns *"Nikhil Hegde's birthday is 3 October 2001."*

3. **Relationship Context Carry-Over:**
   * User: *"Birthdays in September."* → Assistant lists all September birthdays.
   * User: *"What about nieces?"* → Assistant retains `month = 9`, updates `relationship = Niece`, and lists September nieces (Ananya Patil, Nayana Joshi, Asha M).

4. **Conversation Reset:**
   * User: *"Birthdays in September."* → Displays September birthdays.
   * User: *"Reset the conversation."* (or click **Reset Conversation** button) → Confirms reset and clears session state.
   * User: *"What about October?"* → Interpreted independently without previous filters, returning all October birthdays.

