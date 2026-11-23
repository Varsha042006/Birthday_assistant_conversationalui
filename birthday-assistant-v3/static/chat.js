const chat = document.getElementById('chat');
const form = document.getElementById('chat-form');
const question = document.getElementById('question');
const trace = document.getElementById('trace');
const resetBtn = document.getElementById('reset-btn');

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

function updateDebugPanel(debug, state) {
  if (!debug && !state) {
    trace.textContent = 'No dialogue output returned.';
    return;
  }
  const intent = (debug && debug.intent) || 'unknown';
  const rawEntities = JSON.stringify((debug && debug.raw_entities) || {}, null, 2);
  const enrichedEntities = JSON.stringify((debug && debug.enriched_entities) || {}, null, 2);
  const stateDisplay = JSON.stringify(state || {}, null, 2);
  const pendingStatus = (state && state.pending_clarification) ? 'ACTIVE (Awaiting user choice)' : 'None';

  trace.textContent = [
    `Detected Intent: ${intent}`,
    ``,
    `Extracted Entities (Current Turn):`,
    rawEntities,
    ``,
    `Enriched Entities (with Context):`,
    enrichedEntities,
    ``,
    `Dialogue State (Session):`,
    stateDisplay,
    ``,
    `Pending Clarification: ${pendingStatus}`
  ].join('\n');
}

async function ask(text) {
  text = text.trim();
  if (!text) return;
  addMessage(text, 'user');
  question.value = '';
  question.disabled = true;
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    addMessage(data.answer || 'No answer returned.', 'bot');
    updateDebugPanel(data.debug, data.state);
  } catch (error) {
    addMessage(`Error: ${error.message}`, 'bot');
  } finally {
    question.disabled = false;
    question.focus();
  }
}

async function handleReset() {
  try {
    const response = await fetch('/api/reset', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'}
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    addMessage(data.message || 'Conversation context has been reset.', 'bot');
    updateDebugPanel({intent: 'reset', raw_entities: {}, enriched_entities: {}}, {});
  } catch (error) {
    addMessage(`Reset error: ${error.message}`, 'bot');
  }
}

form.addEventListener('submit', e => {
  e.preventDefault();
  ask(question.value);
});

document.querySelectorAll('.chip').forEach(button => {
  if (button.id !== 'reset-btn') {
    button.addEventListener('click', () => ask(button.dataset.q));
  }
});

if (resetBtn) {
  resetBtn.addEventListener('click', handleReset);
}

addMessage('Hello! I am Version 3 (Dialogue State, Context & Clarification). Ask me about birthdays or try follow-up questions!', 'bot');
