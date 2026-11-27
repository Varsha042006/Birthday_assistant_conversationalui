# Version 5 (V5) Testing & Evaluation Report

**Course:** UE24CS3540 – Conversational Interfaces and UX  
**Project:** CIUX Birthday Assistant — Version 5 (Voice Edition)  
**Date:** 2026-11-22  

---

## 1. ASR vs NLU Error Separation

A crucial UX principle in conversational systems is identifying the exact layer responsible when an error occurs:

1. **ASR Error (Speech Recognition):** The microphone failed to capture or transcribe the utterance accurately (e.g. user said *"Rahul Patil"*, but ASR output *"Raghul Patel"*).
2. **NLU Error (Natural Language Understanding):** ASR transcribed the words correctly, but the parser assigned the wrong intent or failed to extract entities.
3. **Dialogue State Error:** NLU extracted entities correctly, but context carry-over failed to retain prior parameters.
4. **Database Query Error:** State was correct, but the spreadsheet lookup failed to find matching rows.
5. **TTS Error (Speech Synthesis):** The text answer was correct, but the vocalization was garbled or cut off.

V5 surfaces the live **ASR Transcript Preview** directly in the UI so users and evaluators can immediately distinguish between speech recognition errors and backend parsing errors.

---

## 2. Checkpoint Test Results (Step 8)

### Checkpoint 1: Basic Voice Question
* **Spoken Query:** `"Any birthdays tomorrow?"`
* **Expected Transcript:** `"Any birthdays tomorrow?"`
* **ASR Layer:** Captured accurately (`en-IN`).
* **NLU Layer:** `intent: "birthday_search"`, `relative_date: "tomorrow"`.
* **Database Result:** Compares DOB against tomorrow's calendar date.
* **TTS Layer:** Vocalized aloud using system Indian English voice.
* **Status:** **PASS**

### Checkpoint 2: Person Name Recognition
* **Spoken Query:** `"When is Rahul Patil's birthday?"`
* **Expected Transcript:** `"When is Rahul Patil's birthday?"`
* **ASR Layer:** Captured accurately.
* **NLU & Grounding Layer:** `person_name: "Rahul Patil"`, grounded to `Person_ID: "P004"`.
* **Database Result:** `"Rahul Patil's birthday is 18 September 2004."`
* **TTS Layer:** Spoken aloud clearly.
* **Status:** **PASS**

### Checkpoint 3: Multi-Turn Voice Follow-up
* **Spoken Query 1:** `"Any nephew birthdays in September?"`
  * **Result:** Returns Bharath Rao, Rahul Patil, Nikhil Bhat. State stores `relationship: "Nephew"`, `month: 9`.
* **Spoken Query 2:** `"What about October?"`
  * **Result:** Context carry-over retains `relationship = Nephew`, updates `month = 10`.
  * **Database Result:** Returns Nikhil Hegde (October nephew).
  * **TTS Layer:** Reads October nephew results aloud.
* **Status:** **PASS**

### Checkpoint 4: Disable Speech Output
* **Action:** Uncheck `"Read responses aloud"` checkbox in UI.
* **Spoken Query:** `"Where does Rahul Patil stay?"`
* **Result:** Text response appears in chat (`"Rahul Patil stays in Bengaluru."`).
* **Audio:** Zero audio playback played.
* **Action:** Re-check `"Read responses aloud"` $\rightarrow$ Subsequent answers resume vocal playback.
* **Status:** **PASS**

---

## 3. Voice Edge Cases & Resilience

| Edge Case | Expected System Behavior | Verified Result | Status |
| :--- | :--- | :--- | :--- |
| **Microphone Permission Denied** | Surface clear message advising user to allow permissions; keep text input enabled. | Status shows *"Microphone permission denied"*; text chat remains 100% usable. | **PASS** |
| **No Speech Detected** | Reset microphone state without hanging in a stuck listening state. | Resets status to *"Ready"* after timeout; mic button returns to normal. | **PASS** |
| **Stop Speaking Button** | Immediately halt active TTS speech synthesis. | `window.speechSynthesis.cancel()` halts audio instantly; hides stop button. | **PASS** |
| **Rapid Consecutive Clicks** | Prevent multiple simultaneous recognition sessions. | `isListening` flag guards against double-starting ASR. | **PASS** |
| **Voice Followed by Typed Text** | Dialogue state is shared regardless of input modality. | Type follow-up after speaking; context seamlessly preserved across modalities. | **PASS** |
| **Typed Text Followed by Voice** | Dialogue state is preserved when switching from typing to speaking. | Speak follow-up after typing; context seamlessly carried forward. | **PASS** |

---

## 4. Automated Test Suite Summary

All **68 automated tests** in `birthday-assistant-v5/tests` pass:
* `test_v5_endpoints.py` (5 passed)
* `test_llm_nlu.py` (11 passed)
* `test_v4_conversations.py` (7 passed)
* `test_dialogue.py` (14 passed)
* `test_nlu.py` (13 passed)
* `test_service.py` (13 passed)
* `test_v3_conversations.py` (5 passed)
