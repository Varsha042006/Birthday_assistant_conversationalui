// CIUX Birthday Assistant — Version 5 (Voice Conversational Interface)
// Web Speech API (ASR) + SpeechSynthesis (TTS) + Unified Backend

const chat = document.getElementById('chat');
const form = document.getElementById('chat-form');
const question = document.getElementById('question');
const trace = document.getElementById('trace');
const resetBtn = document.getElementById('reset-btn');
const micBtn = document.getElementById('mic-btn');
const voiceStatus = document.getElementById('voice-status');
const voiceStatusText = document.getElementById('voice-status-text');
const ttsToggle = document.getElementById('tts-toggle');
const stopTtsBtn = document.getElementById('stop-tts-btn');
const transcriptBar = document.getElementById('transcript-bar');
const transcriptText = document.getElementById('transcript-text');

let recognition = null;
let isListening = false;
let preferredVoice = null;

// ========================================================
// 1. UI & Message Helpers
// ========================================================

function addMessage(text, role) {
  const row = document.createElement('div');
  row.className = `message ${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  row.appendChild(bubble);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
}

function showThinking() {
  const row = document.createElement('div');
  row.className = 'message bot thinking-row';
  row.id = 'thinking-bubble';
  const bubble = document.createElement('div');
  bubble.className = 'bubble thinking';
  bubble.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
  row.appendChild(bubble);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
}

function removeThinking() {
  const el = document.getElementById('thinking-bubble');
  if (el) el.remove();
}

function setVoiceStatus(state, message) {
  if (!voiceStatus || !voiceStatusText) return;
  voiceStatus.className = `voice-status status-${state}`;
  voiceStatusText.textContent = message;
}

function updateDebugPanel(debug, state, asrInfo) {
  if (!debug && !state && !asrInfo) {
    trace.textContent = 'No dialogue output returned.';
    return;
  }
  const parserUsed = (debug && debug.parser === 'llm')
    ? 'LLM Parser (OpenAI)'
    : ((debug && debug.parser === 'system') ? 'System' : 'Rule-Based Fallback');

  const intent = (debug && debug.intent) || 'unknown';
  const rawEntities = JSON.stringify((debug && debug.raw_entities) || {}, null, 2);
  const enrichedEntities = JSON.stringify((debug && debug.enriched_entities) || {}, null, 2);
  const personId = (debug && debug.person_id) ? debug.person_id : 'None';
  const stateDisplay = JSON.stringify(state || {}, null, 2);
  const pendingStatus = (state && state.pending_clarification) ? 'ACTIVE (Awaiting user choice)' : 'None';
  const asrDisplay = asrInfo ? `ASR Transcript: "${asrInfo.transcript}" (confidence: ${asrInfo.confidence || 'N/A'})\n` : '';

  trace.textContent = [
    asrDisplay,
    `Active Parser: ${parserUsed}`,
    `Detected Intent: ${intent}`,
    `Resolved Person_ID: ${personId}`,
    ``,
    `Raw Entities:`,
    rawEntities,
    ``,
    `Enriched / Grounded Entities:`,
    enrichedEntities,
    ``,
    `Dialogue State (Session):`,
    stateDisplay,
    ``,
    `Pending Clarification: ${pendingStatus}`
  ].filter(Boolean).join('\n');
}

// ========================================================
// 2. Speech Synthesis (TTS)
// ========================================================

function loadVoices() {
  if (!('speechSynthesis' in window)) return;
  const voices = window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return;

  // 1. Prefer Indian English voice (en-IN)
  preferredVoice = voices.find(v => v.lang === 'en-IN' || v.lang === 'en_IN');
  // 2. Fallback to any English voice
  if (!preferredVoice) {
    preferredVoice = voices.find(v => v.lang.startsWith('en-'));
  }
  if (!preferredVoice) {
    preferredVoice = voices[0];
  }
}

if ('speechSynthesis' in window) {
  window.speechSynthesis.onvoiceschanged = loadVoices;
  loadVoices();
}

function cleanTextForSpeech(text) {
  // Convert bullet points, dashes, and lists into natural pauses for speech synthesis
  return text
    .replace(/•/g, '')
    .replace(/[—–]/g, ', ')
    .replace(/\n+/g, '. ')
    .trim();
}

function speakResponse(text) {
  if (!('speechSynthesis' in window)) {
    console.warn('[TTS] Speech synthesis not supported in this browser.');
    return;
  }
  if (!ttsToggle || !ttsToggle.checked) {
    return;
  }

  // Cancel any previously playing speech
  window.speechSynthesis.cancel();

  const cleanText = cleanTextForSpeech(text);
  if (!cleanText) return;

  const utterance = new SpeechSynthesisUtterance(cleanText);
  if (preferredVoice) {
    utterance.voice = preferredVoice;
  }
  utterance.lang = (preferredVoice && preferredVoice.lang) || 'en-IN';
  utterance.rate = 1.0;
  utterance.pitch = 1.0;

  utterance.onstart = () => {
    setVoiceStatus('speaking', 'Speaking...');
    if (stopTtsBtn) stopTtsBtn.style.display = 'inline-flex';
  };

  utterance.onend = () => {
    setVoiceStatus('ready', 'Ready');
    if (stopTtsBtn) stopTtsBtn.style.display = 'none';
  };

  utterance.onerror = (e) => {
    console.error('[TTS] Speech synthesis error:', e);
    setVoiceStatus('ready', 'Ready');
    if (stopTtsBtn) stopTtsBtn.style.display = 'none';
  };

  window.speechSynthesis.speak(utterance);
}

function stopSpeaking() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
  setVoiceStatus('ready', 'Ready');
  if (stopTtsBtn) stopTtsBtn.style.display = 'none';
}

if (stopTtsBtn) {
  stopTtsBtn.addEventListener('click', stopSpeaking);
}

// ========================================================
// 3. Speech Recognition (ASR)
// ========================================================

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

function initSpeechRecognition() {
  if (!SpeechRecognition) {
    setVoiceStatus('unsupported', 'Speech recognition not supported in browser');
    if (micBtn) {
      micBtn.disabled = true;
      micBtn.title = 'Speech recognition not supported in this browser';
    }
    return null;
  }

  const sr = new SpeechRecognition();
  sr.lang = 'en-IN';
  sr.interimResults = false;
  sr.maxAlternatives = 1;
  sr.continuous = false;

  sr.onstart = () => {
    isListening = true;
    micBtn.classList.add('listening');
    setVoiceStatus('listening', 'Listening... Speak now');
    if (transcriptBar) transcriptBar.style.display = 'none';
    // Stop any ongoing TTS when user begins speaking
    stopSpeaking();
  };

  sr.onresult = (event) => {
    const transcript = event.results[0][0].transcript.trim();
    const confidence = event.results[0][0].confidence;
    console.log('[ASR] Recognized:', transcript, 'confidence:', confidence);

    if (transcript) {
      // 1. Put recognized text into chat input field
      question.value = transcript;
      // 2. Display recognized transcript preview
      if (transcriptBar && transcriptText) {
        transcriptText.textContent = `"${transcript}"`;
        transcriptBar.style.display = 'flex';
      }
      // 3. Submit question via existing sendMsg() function
      sendMsg(transcript, {transcript, confidence});
    }
  };

  sr.onerror = (event) => {
    console.error('[ASR] Recognition error:', event.error);
    isListening = false;
    micBtn.classList.remove('listening');

    let msg = 'Recognition error';
    if (event.error === 'not-allowed') {
      msg = 'Microphone permission denied';
      addMessage('Microphone access was denied. Please allow microphone permissions in your browser address bar.', 'bot');
    } else if (event.error === 'no-speech') {
      msg = 'No speech detected';
    } else if (event.error === 'audio-capture') {
      msg = 'Microphone unavailable';
    } else if (event.error === 'network') {
      msg = 'Recognition network error';
    }
    setVoiceStatus('error', msg);
    setTimeout(() => setVoiceStatus('ready', 'Ready'), 4000);
  };

  sr.onend = () => {
    isListening = false;
    micBtn.classList.remove('listening');
    // If not speaking, return status to Ready
    if (voiceStatusText && voiceStatusText.textContent.includes('Listening')) {
      setVoiceStatus('ready', 'Ready');
    }
  };

  return sr;
}

recognition = initSpeechRecognition();

function toggleSpeechRecognition() {
  if (!recognition) {
    alert('Speech recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge.');
    return;
  }
  if (isListening) {
    recognition.stop();
  } else {
    try {
      recognition.start();
    } catch (e) {
      console.warn('[ASR] start() error:', e);
    }
  }
}

if (micBtn) {
  micBtn.addEventListener('click', toggleSpeechRecognition);
}

// ========================================================
// 4. Core sendMsg() & Communication
// ========================================================

async function sendMsg(text, asrInfo = null) {
  text = (text || '').trim();
  if (!text) return;

  addMessage(text, 'user');
  question.value = '';
  question.disabled = true;
  setVoiceStatus('processing', 'Processing...');
  showThinking();

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    removeThinking();

    const answer = data.answer || 'No answer returned.';
    addMessage(answer, 'bot');
    updateDebugPanel(data.debug, data.state, asrInfo);

    // Read response aloud if voice output is enabled
    speakResponse(answer);
  } catch (error) {
    removeThinking();
    addMessage(`Error: ${error.message}`, 'bot');
    setVoiceStatus('ready', 'Ready');
  } finally {
    question.disabled = false;
    question.focus();
  }
}

// Alias for backwards compatibility with V1-V4
const ask = sendMsg;
window.sendMsg = sendMsg;
window.ask = ask;

// ========================================================
// 5. Form & Reset Event Handlers
// ========================================================

form.addEventListener('submit', (e) => {
  e.preventDefault();
  sendMsg(question.value);
});

async function handleReset() {
  stopSpeaking();
  try {
    const response = await fetch('/api/reset', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'}
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const msg = data.message || 'Conversation context has been reset.';
    addMessage(msg, 'bot');
    if (transcriptBar) transcriptBar.style.display = 'none';
    updateDebugPanel({parser: 'system', intent: 'reset', raw_entities: {}, enriched_entities: {}}, {});
    speakResponse(msg);
  } catch (error) {
    addMessage(`Reset error: ${error.message}`, 'bot');
  }
}

if (resetBtn) {
  resetBtn.addEventListener('click', handleReset);
}

document.querySelectorAll('.chip').forEach((button) => {
  if (button.id !== 'reset-btn') {
    button.addEventListener('click', () => sendMsg(button.dataset.q));
  }
});

// Welcome message
addMessage('Hello! I am Version 5 (Voice Conversational Interface). You can ask questions by typing or speaking using the microphone!', 'bot');
