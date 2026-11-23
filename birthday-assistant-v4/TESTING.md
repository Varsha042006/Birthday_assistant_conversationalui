# Version 4 (V4) Testing & Evaluation Report

**Course:** UE24CS3540 – Conversational Interfaces and UX  
**Project:** CIUX Birthday Assistant — Version 4  
**Date of Evaluation:** 2026-11-22  

---

## 1. V3 vs V4 Comparative Analysis

| Query | V3 Rule Parser Result | V4 LLM Parser Result | Impact of V4 Upgrade |
| :--- | :--- | :--- | :--- |
| **"Do I need to wish any nephew during September?"** | Parsed via regex | Parsed semantically (`birthday_search`, `Nephew`, `month: 9`) | Smoothly understood without keyword rigidity |
| **"Are there people from my sibling family celebrating next month?"** | Missed `Sibling Family` group (only saw `next month`) | Extracted `relationship: "Sibling Family"` + `relative_month: "next"` | Grounds group relationships in Excel `Relationship_Group` |
| **"I was wondering whether Rahul has a birthday coming soon."** | Rule matched keyword `coming soon` | Extracted `person_name: "Rahul"` and resolved to `P004` (`Rahul Patil`) | Natural resolution of nicknames to canonical Person_ID |
| **"Could you check if anyone among my cousins was born in the final month of the year?"** | **FAILED:** Did not recognize *"final month of the year"* as December | **PASSED:** Extracted `month: 12` and `relationship: "Cousin"` | Understands ordinal and descriptive temporal phrases |
| **"Do I have any family members residing in Davanagere?"** | **FAILED:** Returned `unknown` | **PASSED:** Extracted `intent: "person_place"`, `place: "Davanagere"` | Correctly parses location lookup questions |

---

## 2. Checkpoint Test Cases (Step 9)

### Checkpoint 1: Nephew during September
* **User Message:** `"Do I need to wish any nephew during September?"`
* **Parsed Intent:** `birthday_search`
* **Extracted Entities:** `{"relationship": "Nephew", "month": 9}`
* **Person_ID Resolution:** Not applicable (filtered listing)
* **Parser Used:** `llm` (or `rule_fallback`)
* **Final Answer:**
  ```text
  Birthdays in September for relationship 'Nephew':
  • Bharath Rao — 2 September 2001 (Nephew)
  • Rahul Patil — 18 September 2004 (Nephew)
  • Nikhil Bhat — 25 September 2006 (Nephew)
  ```

### Checkpoint 2: Sibling Family Celebrating Next Month
* **User Message:** `"Are there people from my sibling family celebrating next month?"`
* **Parsed Intent:** `birthday_search`
* **Extracted Entities:** `{"relationship": "Sibling Family", "relative_month": "next"}`
* **Person_ID Resolution:** Group filter resolved against `Relationship_Group`
* **Parser Used:** `llm`
* **Final Answer:**
  ```text
  Birthdays next month (December) for relationship 'Sibling Family':
  • Varun Kumar — 17 December 2012 (Nephew)
  ```

### Checkpoint 3: Rahul Coming Soon
* **User Message:** `"I was wondering whether Rahul has a birthday coming soon."`
* **Parsed Intent:** `birthday_search`
* **Extracted Entities:** `{"person_name": "Rahul Patil", "person_id": "P004"}`
* **Person_ID Resolution:** `P004` (resolved from nickname "Rahul" to canonical name "Rahul Patil")
* **Parser Used:** `llm`
* **Final Answer:**
  ```text
  Rahul Patil's birthday is 18 September 2004.
  ```

### Checkpoint 4: Paraphrased Query (Final month of the year)
* **User Message:** `"Could you check if anyone among my cousins was born in the final month of the year?"`
* **Parsed Intent:** `birthday_search`
* **Extracted Entities:** `{"relationship": "Cousin", "month": 12}`
* **Person_ID Resolution:** Filtered query
* **Parser Used:** `llm`
* **Final Answer:**
  ```text
  Birthdays in December for relationship 'Cousin':
  • Shreyas Desai — 16 December 1977 (Cousin)
  ```

---

## 3. Robustness & Fallback Verification

1. **Non-Existent Person:**
   * Query: `"When is Bruce Wayne's birthday?"`
   * Result: `person_id` remains `null` (no fake ID generated). Answer: `"No matching birthdays found."`
2. **Ambiguous Person Name:**
   * Query: `"When is Nikhil's birthday?"`
   * Result: Ambiguity detected between Nikhil Hegde and Nikhil Bhat; clarification prompt safely triggered.
3. **Missing API Key / API Failure:**
   * Test: `OPENAI_API_KEY` unset or simulated network timeout.
   * Result: System seamlessly catches the error and executes `parse_with_fallback()` using the V3 rule-based parser. Debug response flags `parser: "rule_fallback"`. Zero crashes.
4. **Context Carry-Over & Reset:**
   * Query 1: `"Any nephew birthdays in September?"` $\rightarrow$ Lists September nephews.
   * Query 2: `"What about October?"` $\rightarrow$ Context retained (`Nephew`), month updated (`10`), lists Nikhil Hegde.
   * Query 3: `"Reset the conversation."` $\rightarrow$ Session wiped.
   * Query 4: `"What about October?"` $\rightarrow$ Clean independent query; lists all 12 October birthdays.
