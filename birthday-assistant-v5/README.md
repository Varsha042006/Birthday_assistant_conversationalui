# CIUX Birthday Assistant — Version 5 (V5) Voice Edition

**GM University · School of Computer Science and Technology**  
**Course:** UE24CS3540 — Conversational Interfaces and UX  
**Version:** V5 — Voice Conversational Interface  

---

## 1. What V5 Adds Over V4

Version 4 introduced LLM-assisted semantic parsing and grounded structured queries. However, interaction was limited exclusively to keyboard typing.

**Version 5 introduces a complete multimodal Voice Conversational Interface:**
* **Speech Input (ASR):** Users can speak their questions naturally through the microphone using the browser's built-in Web Speech API configured for **Indian English (`en-IN`)**.
* **Speech Output (TTS):** The assistant reads answers aloud using browser `SpeechSynthesis`, preferring an Indian English voice.
* **Unified Conversational Backend:** Both typed and spoken queries flow through the exact same `sendMsg()` function, Flask `/chat` endpoint, LLM NLU parser, dialogue state engine, and Excel database.
* **Full User Agency & Privacy:** Audio recordings are **never** uploaded or saved to the Flask backend; users can toggle "Read responses aloud" ON or OFF at any time.

---

## 2. Speech Technology Concepts

### Automatic Speech Recognition (ASR)
ASR converts spoken acoustic signals captured by the microphone into written text.
* **Standard:** W3C Web Speech API (`window.SpeechRecognition` / `window.webkitSpeechRecognition`).
* **Configuration:**
  * `lang = 'en-IN'`: Optimizes phonetic recognition for Indian English accents and names (e.g., *Rahul*, *Nikhil*, *Patil*, *Gowda*, *Bengaluru*).
  * `interimResults = false`: Captures the finalized transcript only.
  * `continuous = false`: Automatically stops listening as soon as the user completes their utterance.
* **Execution Flow:** The user clicks **Speak** $\rightarrow$ browser requests microphone permission $\rightarrow$ user speaks $\rightarrow$ transcript is extracted and placed into the input field $\rightarrow$ `sendMsg(transcript)` submits the query to `/chat`.

### Text-to-Speech (TTS)
TTS synthesizes written text into spoken audio output.
* **Standard:** `SpeechSynthesisUtterance` and `window.speechSynthesis`.
* **Voice Selection:** Scans system voices on startup and selects an `en-IN` voice (e.g. *Microsoft Heera*, *Google English India*), falling back gracefully to another standard English voice if unavailable.
* **Formatting Cleanup:** Cleans bullet points and dashes into natural conversational pauses prior to vocalization.
* **Interruption Control:** Previous speech is canceled with `speechSynthesis.cancel()` before new responses are read. A dedicated **Stop Speaking** button allows immediate interruption.

---

## 3. Privacy & Architecture Rules

```
                      [Browser Frontend]                                  [Flask Backend]
  ┌────────────────────────────────────────────────────────┐          ┌───────────────────────┐
  │  Microphone (Speech)                                   │          │                       │
  │        │                                               │          │                       │
  │        ▼                                               │          │                       │
  │  Web Speech API (en-IN ASR)                            │          │                       │
  │        │                                               │          │                       │
  │        ▼ [Text Transcript]                             │          │                       │
  │  sendMsg()  ───────────────── POST /api/chat ───────────────────► │  llm_nlu.py (Parser)  │
  │                                                        │          │          │            │
  │  Display in Chat UI ◄──────── JSON Response ───────────────────── │  dialogue.py (State)  │
  │        │                                               │          │          │            │
  │        ▼                                               │          │  service.py           │
  │  SpeechSynthesis (TTS en-IN)                           │          │          │            │
  │  (if toggle is enabled)                                │          │  people.xlsx (Ground) │
  └────────────────────────────────────────────────────────┘          └───────────────────────┘
```

1. **Zero Server Audio Storage:** Microphone audio is converted strictly within the client browser. No WAV/MP3 files are ever uploaded or stored on the Flask server.
2. **Identical Backend Pipeline:** Speech queries undergo the exact same intent classification, Excel grounding, dialogue context carry-over, ambiguity detection, and clarification resolution as typed text.
3. **No External Paid Speech APIs:** Relies strictly on native browser capabilities without requiring paid speech recognition tokens.

---

## 4. Browser Compatibility & Limitations

* **Recommended Browsers:** **Google Chrome** or **Microsoft Edge** (desktop and Android mobile).
* **Localhost & HTTPS Requirement:** Web browsers restrict microphone access to secure origins (`https://`) or `http://localhost` / `http://127.0.0.1`.
* **Remote Recognition Notice:** Google Chrome and Microsoft Edge may route ASR audio snippets through their respective cloud speech engines for transcription, depending on OS speech language packs.
* **Firefox / Safari:** Firefox desktop does not support the Web Speech Recognition API by default. When opened in an unsupported browser, the UI gracefully displays a clear status message and enables normal text chat.

---

## 5. Setup & Running on Windows PowerShell

```powershell
# 1. Navigate to the V5 project folder
cd E:\projects\CIUX_Birthday_Assistant_V1\birthday-assistant-v5

# 2. Run the automated test suite
python -m pytest tests -v -s

# 3. Start the Flask server
python app.py
```

Open your browser at **`http://127.0.0.1:5000`**.

---

## 6. How to Use Voice Features

1. **Speak a Question:** Click the **Speak** button (microphone icon). Speak clearly into your microphone (e.g. *"Any birthdays tomorrow?"* or *"When is Rahul Patil's birthday?"*).
2. **Stop Speaking:** Click **Stop Speaking** to halt the assistant's voice playback at any time.
3. **Disable Speech Output:** Uncheck **Read responses aloud**. Responses will continue to appear as text in the chat without audio playback.
4. **Follow-Up by Voice:** Speak *"Any nephew birthdays in September?"*, then speak *"What about October?"*. The assistant will retain the *Nephew* relationship filter across turns.
