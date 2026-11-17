const chat = document.getElementById('chat');
const form = document.getElementById('chat-form');
const question = document.getElementById('question');
const trace = document.getElementById('trace');

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

function updateDebugPanel(debug) {
  if (!debug) {
    trace.textContent = 'No NLU output returned.';
    return;
  }
  const intent = debug.intent || 'unknown';
  const entities = JSON.stringify(debug.entities || {}, null, 4);
  trace.textContent = `Intent: ${intent}\n\nEntities:\n${entities}`;
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
    updateDebugPanel(data.debug);
  } catch (error) {
    addMessage(`Error: ${error.message}`, 'bot');
  } finally {
    question.disabled = false;
    question.focus();
  }
}

form.addEventListener('submit', e => {
  e.preventDefault();
  ask(question.value);
});

document.querySelectorAll('.chip').forEach(button => {
  button.addEventListener('click', () => ask(button.dataset.q));
});

addMessage('Hello! I am Version 2 (Intent & Entity Based NLU). Ask me about birthdays or locations.', 'bot');

