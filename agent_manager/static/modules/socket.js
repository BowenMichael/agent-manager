// WebSocket Connection & Real-Time Event Dispatcher Module

function connectWebSocket() {
  const connectionStatus = document.getElementById('connection-status');
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/agents`;
  
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    if (connectionStatus) {
      connectionStatus.classList.add('connected');
      connectionStatus.querySelector('.status-text').textContent = 'Live Connected';
    }
    setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping');
    }, 15000);
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleWsMessage(msg);
    } catch (e) {}
  };

  ws.onclose = () => {
    if (connectionStatus) {
      connectionStatus.classList.remove('connected');
      connectionStatus.querySelector('.status-text').textContent = 'Disconnected • Reconnecting...';
    }
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => ws.close();
  window.ws = ws;
}

let currentThoughtBubble = null;
let thoughtStartTime = null;
let thoughtTimerInterval = null;

function handleWsMessage(msg) {
  switch (msg.type) {
    case 'init':
      window.sessions = msg.data || [];
      renderSessionsList();
      updateStats();
      if (window.sessions.length > 0 && !window.activeSessionId) {
        const visible = getFilteredSessions();
        if (visible.length > 0) selectSession(visible[0].session_id);
        else selectSession(window.sessions[0].session_id);
      }
      break;

    case 'session_created':
      window.sessions.unshift(msg.data);
      renderSessionsList();
      updateStats();
      if (!window.activeSessionId) selectSession(msg.data.session_id);
      break;

    case 'session_updated':
      const updatedIdx = window.sessions.findIndex(s => s.session_id === msg.data.session_id);
      if (updatedIdx !== -1) window.sessions[updatedIdx] = msg.data;
      else window.sessions.unshift(msg.data);
      renderSessionsList();
      updateStats();
      if (window.activeSessionId === msg.data.session_id) updateActiveSessionView(msg.data);
      break;

    case 'session_deleted':
      const deletedIdx = window.sessions.findIndex(s => s.session_id === msg.data.session_id);
      if (deletedIdx !== -1) window.sessions.splice(deletedIdx, 1);
      if (window.activeSessionId === msg.data.session_id) {
        window.activeSessionId = null;
        const visible = getFilteredSessions();
        if (visible.length > 0) selectSession(visible[0].session_id);
        else showDashboardView();
      }
      renderSessionsList();
      updateStats();
      break;

    case 'message_added':
      const { session_id, message } = msg.data;
      const targetSession = window.sessions.find(s => s.session_id === session_id);
      if (targetSession) {
        targetSession.messages.push(message);
        if (message.role === 'TOOL_CALL') targetSession.turn_count++;
      }
      if (window.activeSessionId === session_id) {
        finalizeThoughtBubble();
        if (window.currentStreamingBubble) {
          window.currentStreamingBubble.remove();
          window.currentStreamingBubble = null;
        }
        renderMessageItem(message);
        scrollToBottom();
      }
      break;

    case 'quota_alert':
      showQuotaToast(msg.data);
      break;

    case 'settings_updated':
      if (typeof loadSettings === 'function') loadSettings();
      break;

    case 'thought_delta':
      const { session_id: thoughtSid, delta: thoughtDelta, model: thoughtModel } = msg.data;
      if (window.activeSessionId === thoughtSid) {
        handleThoughtStream(thoughtDelta, thoughtModel);
        scrollToBottom();
      }
      break;

    case 'token_stream':
      const { session_id: sId, token } = msg.data;
      const s = window.sessions.find(item => item.session_id === sId);
      if (s) s.token_count = (s.token_count || 0) + 1;
      updateStats();
      if (window.activeSessionId === sId) {
        handleTokenStream(token);
        scrollToBottom();
      }
      break;
  }
}

function handleThoughtStream(delta, model = 'Gemini 3.1 Pro') {
  const transcriptStream = document.getElementById('transcript-stream');
  if (!transcriptStream) return;

  if (!currentThoughtBubble) {
    thoughtStartTime = Date.now();
    currentThoughtBubble = document.createElement('div');
    currentThoughtBubble.className = 'msg-bubble msg-thought-live';
    currentThoughtBubble.innerHTML = `
      <div class="thought-header">
        <span class="thought-icon pulse-glow">🧠</span>
        <span class="thought-label">${escapeHtml(model).toUpperCase()} (LIVE REASONING)</span>
        <span class="thought-timer" id="live-thought-timer">Thinking: 1s</span>
      </div>
      <div class="thought-body live-thought-text"></div>
    `;
    transcriptStream.appendChild(currentThoughtBubble);

    if (thoughtTimerInterval) clearInterval(thoughtTimerInterval);
    thoughtTimerInterval = setInterval(() => {
      const timerEl = currentThoughtBubble ? currentThoughtBubble.querySelector('#live-thought-timer') : null;
      if (timerEl && thoughtStartTime) {
        const secs = Math.max(1, Math.floor((Date.now() - thoughtStartTime) / 1000));
        timerEl.textContent = `Thinking: ${secs}s`;
      }
    }, 1000);
  }

  const textEl = currentThoughtBubble.querySelector('.live-thought-text');
  if (textEl) textEl.textContent += delta;
}

function finalizeThoughtBubble() {
  if (thoughtTimerInterval) {
    clearInterval(thoughtTimerInterval);
    thoughtTimerInterval = null;
  }
  if (currentThoughtBubble) {
    const timer = currentThoughtBubble.querySelector('.thought-timer');
    if (timer && thoughtStartTime) {
      const elapsed = Math.max(1, Math.round((Date.now() - thoughtStartTime) / 1000));
      timer.textContent = `Completed in ${elapsed}s`;
    }
    currentThoughtBubble.classList.remove('msg-thought-live');
    currentThoughtBubble.classList.add('msg-thought');
    currentThoughtBubble = null;
  }
}

function handleTokenStream(token) {
  const transcriptStream = document.getElementById('transcript-stream');
  if (!transcriptStream) return;
  if (!window.currentStreamingBubble) {
    window.currentStreamingBubble = document.createElement('div');
    window.currentStreamingBubble.className = 'msg-bubble msg-agent streaming';
    window.currentStreamingBubble.innerHTML = `<span class="msg-role-tag">AGENT STREAMING</span><div class="stream-content"></div>`;
    transcriptStream.appendChild(window.currentStreamingBubble);
  }
  const streamBody = window.currentStreamingBubble.querySelector('.stream-content');
  if (streamBody) streamBody.textContent += token;
}

window.connectWebSocket = connectWebSocket;
window.handleWsMessage = handleWsMessage;
window.handleThoughtStream = handleThoughtStream;
window.finalizeThoughtBubble = finalizeThoughtBubble;
window.handleTokenStream = handleTokenStream;
