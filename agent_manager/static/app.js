// State
let sessions = [];
let activeSessionId = null;
let ws = null;
let currentStreamingBubble = null;

// DOM Elements
const connectionStatus = document.getElementById('connection-status');
const sessionsList = document.getElementById('sessions-list');
const sessionsEmpty = document.getElementById('sessions-empty');
const sessionsCount = document.getElementById('sessions-count');

const statActive = document.getElementById('stat-active');
const statCompleted = document.getElementById('stat-completed');
const statTokens = document.getElementById('stat-tokens');

const consoleEmpty = document.getElementById('console-empty');
const consoleActive = document.getElementById('console-active');

const currentStatusTag = document.getElementById('current-status-tag');
const currentTitle = document.getElementById('current-title');
const currentRepo = document.getElementById('current-repo');
const currentBranch = document.getElementById('current-branch');
const currentWorktree = document.getElementById('current-worktree');
const turnCounter = document.getElementById('turn-counter');

const transcriptViewport = document.getElementById('transcript-viewport');
const transcriptStream = document.getElementById('transcript-stream');
const streamAnchor = document.getElementById('stream-anchor');

const contextInput = document.getElementById('context-input');
const btnSendContext = document.getElementById('btn-send-context');
const btnStopCurrent = document.getElementById('btn-stop-current');
const btnDoneCurrent = document.getElementById('btn-done-current');

// Modals
const modalSimulate = document.getElementById('modal-simulate');
const btnSimulateModal = document.getElementById('btn-simulate-modal');
const btnCloseSimulate = document.getElementById('btn-close-simulate');
const btnCancelSimulate = document.getElementById('btn-cancel-simulate');
const btnSubmitSimulate = document.getElementById('btn-submit-simulate');

const modalLaunch = document.getElementById('modal-launch');
const btnNewAgentModal = document.getElementById('btn-new-agent-modal');
const btnCloseLaunch = document.getElementById('btn-close-launch');
const btnCancelLaunch = document.getElementById('btn-cancel-launch');
const btnSubmitLaunch = document.getElementById('btn-submit-launch');

const btnCopyWebhook = document.getElementById('btn-copy-webhook');
const webhookUrlDisplay = document.getElementById('webhook-url-display');

// Setup Webhook URL display
webhookUrlDisplay.textContent = `${window.location.origin}/api/webhooks/github`;
btnCopyWebhook.addEventListener('click', () => {
  navigator.clipboard.writeText(webhookUrlDisplay.textContent);
  btnCopyWebhook.textContent = 'Copied!';
  setTimeout(() => btnCopyWebhook.textContent = 'Copy', 2000);
});

// WebSocket Connection
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/agents`;
  
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    connectionStatus.classList.add('connected');
    connectionStatus.querySelector('.status-text').textContent = 'Live Connected';
    // Start heartbeat
    setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping');
    }, 15000);
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleWsMessage(msg);
    } catch (e) {
      // Ignore pong
    }
  };

  ws.onclose = () => {
    connectionStatus.classList.remove('connected');
    connectionStatus.querySelector('.status-text').textContent = 'Disconnected • Reconnecting...';
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => {
    ws.close();
  };
}

function handleWsMessage(msg) {
  switch (msg.type) {
    case 'init':
      sessions = msg.data || [];
      renderSessionsList();
      updateStats();
      if (sessions.length > 0 && !activeSessionId) {
        selectSession(sessions[0].session_id);
      }
      break;

    case 'session_created':
      sessions.unshift(msg.data);
      renderSessionsList();
      updateStats();
      if (!activeSessionId) {
        selectSession(msg.data.session_id);
      }
      break;

    case 'session_updated':
      const updatedIdx = sessions.findIndex(s => s.session_id === msg.data.session_id);
      if (updatedIdx !== -1) {
        sessions[updatedIdx] = msg.data;
      } else {
        sessions.unshift(msg.data);
      }
      renderSessionsList();
      updateStats();
      if (activeSessionId === msg.data.session_id) {
        updateActiveSessionView(msg.data);
      }
      break;

    case 'message_added':
      const { session_id, message } = msg.data;
      const targetSession = sessions.find(s => s.session_id === session_id);
      if (targetSession) {
        targetSession.messages.push(message);
        if (message.role === 'TOOL_CALL') targetSession.turn_count++;
      }
      if (activeSessionId === session_id) {
        currentStreamingBubble = null;
        renderMessageItem(message);
        scrollToBottom();
      }
      break;

    case 'token_stream':
      const { session_id: sId, token } = msg.data;
      const s = sessions.find(s => s.session_id === sId);
      if (s) s.token_count = (s.token_count || 0) + 1;
      updateStats();

      if (activeSessionId === sId) {
        handleTokenStream(token);
        scrollToBottom();
      }
      break;
  }
}

function handleTokenStream(token) {
  if (!currentStreamingBubble) {
    currentStreamingBubble = document.createElement('div');
    currentStreamingBubble.className = 'msg-bubble msg-agent';
    currentStreamingBubble.innerHTML = `<span class="msg-role-tag">AGENT (STREAMING)</span><div class="msg-content"></div>`;
    transcriptStream.appendChild(currentStreamingBubble);
  }
  const contentEl = currentStreamingBubble.querySelector('.msg-content');
  contentEl.textContent += token;
}

function updateStats() {
  const activeCount = sessions.filter(s => s.status === 'RUNNING' || s.status === 'INITIALIZING').length;
  const compCount = sessions.filter(s => s.status === 'COMPLETED').length;
  const totalTokens = sessions.reduce((acc, s) => acc + (s.token_count || 0), 0);

  statActive.textContent = activeCount;
  statCompleted.textContent = compCount;
  statTokens.textContent = totalTokens;
  sessionsCount.textContent = sessions.length;
}

function renderSessionsList() {
  if (sessions.length === 0) {
    sessionsEmpty.classList.remove('hidden');
    return;
  }
  sessionsEmpty.classList.add('hidden');

  // Preserve scroll
  const existingCards = sessionsList.querySelectorAll('.session-card');
  existingCards.forEach(c => c.remove());

  sessions.forEach(session => {
    const card = document.createElement('div');
    card.className = `session-card ${session.session_id === activeSessionId ? 'selected' : ''}`;
    card.dataset.id = session.session_id;

    const statusBadgeClass = getStatusBadgeClass(session.status);

    card.innerHTML = `
      <div class="card-top">
        <span class="card-status-badge ${statusBadgeClass}">${session.status}</span>
        <span class="card-time">${formatTime(session.started_at)}</span>
      </div>
      <div class="card-title">${escapeHtml(session.title)}</div>
      <div class="card-bottom">
        <span>${session.issue_number ? '#' + session.issue_number : 'ad-hoc'}</span>
        <span>${session.turn_count || 0} turns • ${session.token_count || 0} tok</span>
      </div>
    `;

    card.addEventListener('click', () => selectSession(session.session_id));
    sessionsList.appendChild(card);
  });
}

function selectSession(sessionId) {
  activeSessionId = sessionId;
  currentStreamingBubble = null;

  document.querySelectorAll('.session-card').forEach(c => {
    c.classList.toggle('selected', c.dataset.id === sessionId);
  });

  const session = sessions.find(s => s.session_id === sessionId);
  if (!session) return;

  consoleEmpty.classList.add('hidden');
  consoleActive.classList.remove('hidden');

  updateActiveSessionView(session);
  renderTranscript(session);
}

function updateActiveSessionView(session) {
  currentStatusTag.textContent = session.status;
  currentStatusTag.className = `status-tag ${getStatusBadgeClass(session.status).replace('badge-', 'tag-')}`;
  currentTitle.textContent = session.title;
  currentRepo.textContent = session.repo;
  currentBranch.textContent = session.git_branch || 'main';
  currentWorktree.textContent = session.worktree_path ? session.worktree_path.split(/[\\/]/).slice(-2).join('/') : 'in-repo';
  turnCounter.textContent = `Turns: ${session.turn_count || 0} • Tokens: ${session.token_count || 0}`;

  btnStopCurrent.disabled = (session.status === 'STOPPED' || session.status === 'COMPLETED' || session.status === 'FAILED');
  updateOverviewPanel(session);
}

function renderTranscript(session) {
  transcriptStream.innerHTML = '';
  session.messages.forEach(msg => {
    renderMessageItem(msg);
  });
  scrollToBottom();
}

function renderMessageItem(msg) {
  const bubble = document.createElement('div');
  
  if (msg.role === 'USER') {
    bubble.className = 'msg-bubble msg-user';
    bubble.innerHTML = `<span class="msg-role-tag">USER CONTEXT</span>${formatContent(msg.content)}`;
  } else if (msg.role === 'AGENT') {
    bubble.className = 'msg-bubble msg-agent';
    bubble.innerHTML = `<span class="msg-role-tag">AGENT RESPONSE</span>${formatContent(msg.content)}`;
  } else if (msg.role === 'THOUGHT') {
    bubble.className = 'msg-bubble msg-thought';
    bubble.innerHTML = `<span class="msg-role-tag">THINKING TRACE</span>${formatContent(msg.content)}`;
  } else if (msg.role === 'TOOL_RESULT' || msg.tool_name === 'agy_terminal') {
    bubble.className = 'msg-terminal';
    bubble.innerHTML = `
      <div class="terminal-header">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
        <span>AGY TERMINAL LOG</span>
      </div>
      <div class="terminal-body">${escapeHtml(msg.content)}</div>
    `;
  } else if (msg.role === 'TOOL_CALL') {
    bubble.className = 'msg-tool';
    bubble.innerHTML = `
      <div class="tool-header">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
        <span>TOOL EXECUTION: ${escapeHtml(msg.tool_name || 'tool')}</span>
      </div>
      <div class="tool-args">${escapeHtml(msg.content)}</div>
    `;
  } else if (msg.role === 'SYSTEM') {
    bubble.className = 'msg-bubble msg-system';
    bubble.innerHTML = `<strong>SYSTEM:</strong> ${escapeHtml(msg.content)}`;
  }

  transcriptStream.appendChild(bubble);
}

function scrollToBottom(smooth = false) {
  if (transcriptViewport) {
    if (smooth) {
      transcriptViewport.scrollTo({ top: transcriptViewport.scrollHeight, behavior: 'smooth' });
    } else {
      transcriptViewport.scrollTop = transcriptViewport.scrollHeight;
    }
  }
}

// Action: Stop Current Agent
btnStopCurrent.addEventListener('click', async () => {
  if (!activeSessionId) return;
  if (!confirm('Are you sure you want to stop this agent? Execution will halt immediately.')) return;

  btnStopCurrent.disabled = true;
  btnStopCurrent.textContent = 'Stopping...';

  try {
    const res = await fetch(`/api/agents/${activeSessionId}/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'Stopped manually from UI Control Plane' })
    });
    const data = await res.json();
    console.log(data);
  } catch (err) {
    alert('Failed to stop agent: ' + err.message);
  } finally {
    btnStopCurrent.textContent = 'Stop Agent';
  }
});

// Action: Inject Context
async function sendContext() {
  const text = contextInput.value.trim();
  if (!text || !activeSessionId) return;

  btnSendContext.disabled = true;
  btnSendContext.textContent = 'Sending...';

  try {
    const res = await fetch(`/api/agents/${activeSessionId}/context`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ context: text })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to inject context');
    }
    contextInput.value = '';
  } catch (err) {
    alert('Error injecting context: ' + err.message);
  } finally {
    btnSendContext.disabled = false;
    btnSendContext.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg> Send Context`;
  }
}

btnSendContext.addEventListener('click', sendContext);
contextInput.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === 'Enter') {
    e.preventDefault();
    sendContext();
  }
});

// Modal Logic: Simulate Webhook
btnSimulateModal.addEventListener('click', () => modalSimulate.classList.remove('hidden'));
btnCloseSimulate.addEventListener('click', () => modalSimulate.classList.add('hidden'));
btnCancelSimulate.addEventListener('click', () => modalSimulate.classList.add('hidden'));

btnSubmitSimulate.addEventListener('click', async () => {
  const issueNum = parseInt(document.getElementById('sim-issue-num').value) || 6;
  const issueTitle = document.getElementById('sim-issue-title').value;
  const issueBody = document.getElementById('sim-issue-body').value;

  btnSubmitSimulate.disabled = true;
  btnSubmitSimulate.textContent = 'Simulating...';

  try {
    const res = await fetch('/api/webhooks/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_type: 'issues',
        action: 'labeled',
        label: 'agent:ready',
        issue_number: issueNum,
        issue_title: issueTitle,
        issue_body: issueBody,
        repo: 'BowenMichael/f1-frontend'
      })
    });
    const data = await res.json();
    modalSimulate.classList.add('hidden');
    if (data.session) {
      selectSession(data.session.session_id);
    }
  } catch (err) {
    alert('Failed to simulate webhook: ' + err.message);
  } finally {
    btnSubmitSimulate.disabled = false;
    btnSubmitSimulate.textContent = 'Simulate & Spawn Agent';
  }
});

// Modal Logic: Manual Launch Agent
btnNewAgentModal.addEventListener('click', () => modalLaunch.classList.remove('hidden'));
btnCloseLaunch.addEventListener('click', () => modalLaunch.classList.add('hidden'));
btnCancelLaunch.addEventListener('click', () => modalLaunch.classList.add('hidden'));

btnSubmitLaunch.addEventListener('click', async () => {
  const repo = document.getElementById('launch-repo').value;
  const issueNumVal = document.getElementById('launch-issue-num').value;
  const prompt = document.getElementById('launch-prompt').value.trim();

  if (!prompt) {
    alert('Please enter task instructions or prompt');
    return;
  }

  btnSubmitLaunch.disabled = true;
  btnSubmitLaunch.textContent = 'Spawning...';

  try {
    const res = await fetch('/api/agents/spawn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        repo: repo,
        issue_number: issueNumVal ? parseInt(issueNumVal) : null,
        prompt: prompt
      })
    });
    const session = await res.json();
    modalLaunch.classList.add('hidden');
    selectSession(session.session_id);
  } catch (err) {
    alert('Failed to launch agent: ' + err.message);
  } finally {
    btnSubmitLaunch.disabled = false;
    btnSubmitLaunch.textContent = 'Spawn Agent';
  }
});

// Utility Helpers
function getStatusBadgeClass(status) {
  switch (status) {
    case 'RUNNING': return 'badge-running';
    case 'IN_REVIEW': return 'badge-in-review';
    case 'COMPLETED': return 'badge-completed';
    case 'STOPPED': return 'badge-stopped';
    case 'PAUSED': return 'badge-paused';
    default: return 'badge-paused';
  }
}

function formatTime(isoStr) {
  if (!isoStr) return '';
  const date = new Date(isoStr);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
}

function formatContent(str) {
  if (!str) return '';
  // Basic markdown-like line break and code escaping
  return escapeHtml(str).replace(/\n/g, '<br>');
}

// Initial Boot
connectWebSocket();

// Settings Modal Logic
const modalSettings = document.getElementById('modal-settings');
const btnSettingsModal = document.getElementById('btn-settings-modal');
const btnCloseSettings = document.getElementById('btn-close-settings');
const btnCancelSettings = document.getElementById('btn-cancel-settings');
const btnSaveSettings = document.getElementById('btn-save-settings');
const inputGeminiKey = document.getElementById('input-gemini-key');
const keyStatusDisplay = document.getElementById('key-status-display');
const apiKeyBanner = document.getElementById('api-key-banner');
const btnBannerConfigure = document.getElementById('btn-banner-configure');

async function checkApiKeyStatus() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    if (data.has_gemini_api_key) {
      apiKeyBanner.classList.add('hidden');
      keyStatusDisplay.textContent = 'Active: ' + data.masked_gemini_api_key;
      keyStatusDisplay.style.color = 'var(--accent-green)';
    } else {
      apiKeyBanner.classList.remove('hidden');
      keyStatusDisplay.textContent = 'Not configured';
      keyStatusDisplay.style.color = 'var(--accent-amber)';
    }
  } catch (e) {
    console.error('Failed to fetch settings:', e);
  }
}

btnSettingsModal.addEventListener('click', () => {
  modalSettings.classList.remove('hidden');
  checkApiKeyStatus();
});
btnBannerConfigure.addEventListener('click', () => {
  modalSettings.classList.remove('hidden');
  checkApiKeyStatus();
});
btnCloseSettings.addEventListener('click', () => modalSettings.classList.add('hidden'));
btnCancelSettings.addEventListener('click', () => modalSettings.classList.add('hidden'));

btnSaveSettings.addEventListener('click', async () => {
  const selectedMode = document.querySelector('input[name="agy_execution_mode"]:checked')?.value || 'web_stream';
  const selectedModel = document.getElementById('select-default-model')?.value || 'gemini-3.1-pro-high';
  const maxTokens = parseInt(document.getElementById('input-max-tokens')?.value || '150000', 10);
  const key = inputGeminiKey.value.trim();

  btnSaveSettings.disabled = true;
  btnSaveSettings.textContent = 'Saving...';
  try {
    const payload = {
      agy_mode: selectedMode,
      default_model: selectedModel,
      max_session_tokens: maxTokens
    };
    if (key) {
      payload.gemini_api_key = key;
    }
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    modalSettings.classList.add('hidden');
    inputGeminiKey.value = '';
    await checkApiKeyStatus();
  } catch (err) {
    alert('Failed to save settings: ' + err.message);
  } finally {
    btnSaveSettings.disabled = false;
    btnSaveSettings.textContent = 'Save Settings';
  }
});

// Check on boot
checkApiKeyStatus();

// Action: Sync Board
const btnSyncBoard = document.getElementById('btn-sync-board');
if (btnSyncBoard) {
  btnSyncBoard.addEventListener('click', async () => {
    btnSyncBoard.classList.add('spinning');
    try {
      await fetch('/api/board/sync', { method: 'POST' });
      // Fetch fresh sessions
      const res = await fetch('/api/agents');
      sessions = await res.json();
      renderSessionsList();
      updateStats();
    } catch (e) {
      console.error('Board sync error:', e);
    } finally {
      setTimeout(() => btnSyncBoard.classList.remove('spinning'), 600);
    }
  });
}

// Action: Restart Current Agent
const btnRestartCurrent = document.getElementById('btn-restart-current');
if (btnRestartCurrent) {
  btnRestartCurrent.addEventListener('click', async () => {
    if (!activeSessionId) return;
    if (!confirm('Are you sure you want to refresh & restart this agent session?')) return;

    btnRestartCurrent.disabled = true;
    btnRestartCurrent.innerHTML = `<svg class="spinning" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg> Restarting...`;

    try {
      const res = await fetch(`/api/agents/${activeSessionId}/restart`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error('Failed to restart agent');
      const updated = await res.json();
      const idx = sessions.findIndex(s => s.session_id === updated.session_id);
      if (idx !== -1) sessions[idx] = updated;
      selectSession(updated.session_id);
    } catch (err) {
      alert('Error restarting agent: ' + err.message);
    } finally {
      btnRestartCurrent.disabled = false;
      btnRestartCurrent.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg> Restart Agent`;
    }
  });
}


// Open/Re-launch visible terminal button
const btnOpenTerminal = document.getElementById('btn-open-terminal');
if (btnOpenTerminal) {
  btnOpenTerminal.addEventListener('click', async () => {
    if (!activeSessionId) return;
    try {
      btnOpenTerminal.disabled = true;
      btnOpenTerminal.textContent = 'Launching...';
      const res = await fetch(`/api/agents/${activeSessionId}/launch-terminal`, { method: 'POST' });
      const data = await res.json();
      btnOpenTerminal.textContent = 'Terminal Opened!';
      setTimeout(() => {
        btnOpenTerminal.disabled = false;
        btnOpenTerminal.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg> Launch Terminal';
      }, 3000);
    } catch (e) {
      alert('Could not launch terminal: ' + e.message);
      btnOpenTerminal.disabled = false;
    }
  });
}


// Helper: Format token count nicely (e.g. 24.5k)
function formatTokens(num) {
  if (!num || num === 0) return '0';
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
  return num.toLocaleString();
}

// Helper: Format duration seconds
function formatDuration(sec) {
  if (!sec || sec <= 0) return '0s';
  const s = Math.round(sec);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m > 0) return `${m}m ${rem}s`;
  return `${s}s`;
}

// Update the Overview Side Panel with live analysis
function updateOverviewPanel(session) {
  if (!session) return;

  const msgs = session.messages || [];
  let toolCalls = 0;
  let cmdsRun = 0;
  const filesTouched = new Set();
  const toolCounts = {};
  const recentActions = [];
  let latestActivity = 'Agent initialized. Analyzing task objective and codebase...';
  let latestSub = 'Status: ' + session.status;

  // Scan messages in reverse to find recent actions & latest activity
  for (let i = msgs.length - 1; i >= 0; i--) {
    const m = msgs[i];
    if (m.role === 'TOOL_CALL') {
      toolCalls++;
      const tName = m.tool_name || 'tool';
      toolCounts[tName] = (toolCounts[tName] || 0) + 1;

      let actionDesc = tName;
      let icon = '⚡';

      if (tName === 'run_command') {
        cmdsRun++;
        icon = '💻';
        const cmd = m.tool_args?.CommandLine || m.tool_args?.command || '';
        actionDesc = 'Ran: ' + (cmd.length > 40 ? cmd.substring(0, 37) + '...' : cmd);
      } else if (tName === 'view_file') {
        icon = '📄';
        const file = m.tool_args?.AbsolutePath || m.tool_args?.path || '';
        const baseName = file.split(/[\\/]/).pop();
        filesTouched.add(baseName);
        actionDesc = 'Viewed ' + baseName;
      } else if (tName === 'write_to_file' || tName === 'replace_file_content' || tName === 'multi_replace_file_content') {
        icon = '📝';
        const file = m.tool_args?.TargetFile || m.tool_args?.path || '';
        const baseName = file.split(/[\\/]/).pop();
        filesTouched.add(baseName);
        actionDesc = 'Edited ' + baseName;
      } else if (tName === 'call_mcp_tool') {
        icon = '🔌';
        actionDesc = 'MCP ' + (m.tool_args?.ToolName || 'tool');
      }

      if (recentActions.length < 4) {
        recentActions.push({ icon, desc: actionDesc, time: m.timestamp });
      }

      if (latestActivity === 'Agent initialized. Analyzing task objective and codebase...') {
        latestActivity = actionDesc;
        latestSub = 'Tool: ' + tName;
      }
    } else if (m.role === 'AGENT' && latestActivity === 'Agent initialized. Analyzing task objective and codebase...') {
      latestActivity = m.content.substring(0, 80) + '...';
      latestSub = 'Thinking / Synthesizing';
    }
  }

  // 1. Current Activity Highlight
  const elSummary = document.getElementById('overview-activity-summary');
  const elSub = document.getElementById('overview-activity-sub');
  const elBadge = document.getElementById('overview-badge');
  if (elSummary) elSummary.textContent = latestActivity;
  if (elSub) elSub.textContent = latestSub;
  if (elBadge) {
    elBadge.textContent = session.status === 'RUNNING' ? 'EXECUTING' : session.status;
    elBadge.style.color = session.status === 'COMPLETED' ? 'var(--accent-green)' : (session.status === 'RUNNING' ? 'var(--accent-cyan)' : 'var(--accent-amber)');
  }

  // 2. Workflow Milestones
  const msBranchText = document.getElementById('ms-branch-text');
  if (msBranchText) msBranchText.textContent = session.git_branch || 'main';

  const msToolProgress = document.getElementById('ms-tool-progress');
  if (msToolProgress) {
    msToolProgress.textContent = `${toolCalls} tool turns completed`;
  }

  const stepExec = document.getElementById('ms-step-exec');
  const stepVerify = document.getElementById('ms-step-verify');
  const stepPr = document.getElementById('ms-step-pr');

  if (session.status === 'COMPLETED') {
    if (stepExec) stepExec.className = 'milestone-step step-done';
    if (stepVerify) stepVerify.className = 'milestone-step step-done';
    if (stepPr) stepPr.className = 'milestone-step step-done';
  } else if (session.status === 'RUNNING') {
    if (stepExec) stepExec.className = 'milestone-step step-active';
    if (cmdsRun > 10 && stepVerify) stepVerify.className = 'milestone-step step-active';
  }

  // 3. Telemetry Stats Grid
  const elToolCalls = document.getElementById('stat-tool-calls');
  const elCmdsRun = document.getElementById('stat-cmds-run');
  const elFiles = document.getElementById('stat-files-touched');
  const elTurns = document.getElementById('stat-agent-turns');

  if (elToolCalls) elToolCalls.textContent = toolCalls;
  if (elCmdsRun) elCmdsRun.textContent = cmdsRun;
  if (elFiles) elFiles.textContent = filesTouched.size;
  if (elTurns) elTurns.textContent = session.turn_count || toolCalls;

  // Tool tags breakdown
  const toolContainer = document.getElementById('tools-tags-container');
  if (toolContainer) {
    toolContainer.innerHTML = '';
    const entries = Object.entries(toolCounts);
    if (entries.length === 0) {
      toolContainer.innerHTML = '<span style="font-size: 0.7rem; color: var(--text-dim); font-style: italic;">No tools invoked yet</span>';
    } else {
      entries.forEach(([name, count]) => {
        const chip = document.createElement('span');
        chip.className = 'tool-chip';
        chip.innerHTML = `${name}: <strong>${count}</strong>`;
        toolContainer.appendChild(chip);
      });
    }
  }

  // 4. Usage & Token Telemetry Box
  const totalToks = session.total_tokens || session.token_count || 0;
  const inputToks = session.input_tokens || 0;
  const outputToks = session.output_tokens || 0;
  const thinkingToks = session.thinking_tokens || 0;
  const duration = session.duration_seconds || 0;

  const elTotalToks = document.getElementById('usage-total-tokens');
  const elInputToks = document.getElementById('usage-input-tokens');
  const elOutputToks = document.getElementById('usage-output-tokens');
  const elThinkingToks = document.getElementById('usage-thinking-tokens');
  const elDuration = document.getElementById('usage-duration');

  if (elTotalToks) elTotalToks.textContent = formatTokens(totalToks);
  if (elInputToks) elInputToks.textContent = formatTokens(inputToks);
  if (elOutputToks) elOutputToks.textContent = formatTokens(outputToks);
  if (elThinkingToks) elThinkingToks.textContent = formatTokens(thinkingToks);
  if (elDuration) elDuration.textContent = formatDuration(duration);

  // Quota percentage and limit tracking
  const maxTokens = session.max_tokens || 150000;
  const pct = Math.min(100, Math.round(((totalToks / maxTokens) * 100) * 10) / 10);
  const elQuotaPct = document.getElementById('usage-quota-percent');
  const elQuotaFill = document.getElementById('usage-quota-fill');
  const elTokensRatio = document.getElementById('usage-tokens-ratio');
  const elQuotaStatus = document.getElementById('usage-quota-status');

  if (elQuotaPct) elQuotaPct.textContent = pct + '%';
  if (elTokensRatio) elTokensRatio.textContent = `${totalToks.toLocaleString()} / ${maxTokens.toLocaleString()} tokens`;

  if (elQuotaFill) {
    elQuotaFill.style.width = pct + '%';
    if (pct >= 90) {
      elQuotaFill.className = 'quota-bar-fill danger';
      if (elQuotaStatus) { elQuotaStatus.textContent = 'CRITICAL / LIMIT'; elQuotaStatus.style.color = 'var(--accent-red)'; }
    } else if (pct >= 70) {
      elQuotaFill.className = 'quota-bar-fill warning';
      if (elQuotaStatus) { elQuotaStatus.textContent = 'HIGH'; elQuotaStatus.style.color = 'var(--accent-amber)'; }
    } else {
      elQuotaFill.className = 'quota-bar-fill';
      if (elQuotaStatus) { elQuotaStatus.textContent = 'HEALTHY'; elQuotaStatus.style.color = 'var(--accent-green)'; }
    }
  }

  // Handle Resume button visibility
  const btnResume = document.getElementById('btn-resume-current');
  if (btnResume) {
    if (session.status === 'PAUSED') {
      btnResume.classList.remove('hidden');
    } else {
      btnResume.classList.add('hidden');
    }
  }

  // 5. Recent Actions Feed
  const actionsList = document.getElementById('recent-actions-list');
  if (actionsList) {
    actionsList.innerHTML = '';
    if (recentActions.length === 0) {
      actionsList.innerHTML = '<li class="action-item-empty">Listening for agent actions...</li>';
    } else {
      recentActions.forEach(act => {
        const li = document.createElement('li');
        li.className = 'action-item';
        li.innerHTML = `<span class="action-item-icon">${act.icon}</span><span title="${act.desc}">${act.desc}</span>`;
        actionsList.appendChild(li);
      });
    }
  }
}


// Resume Agent button
const btnResumeCurrent = document.getElementById('btn-resume-current');
if (btnResumeCurrent) {
  btnResumeCurrent.addEventListener('click', async () => {
    if (!activeSessionId) return;
    try {
      btnResumeCurrent.disabled = true;
      btnResumeCurrent.textContent = 'Resuming...';
      const res = await fetch(`/api/agents/${activeSessionId}/resume`, { method: 'POST' });
      const data = await res.json();
      setTimeout(() => {
        btnResumeCurrent.disabled = false;
        btnResumeCurrent.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Resume';
      }, 1000);
    } catch (e) {
      alert('Could not resume agent: ' + e.message);
      btnResumeCurrent.disabled = false;
    }
  });
}

// Action: Mark Current Agent as Done
if (btnDoneCurrent) {
  btnDoneCurrent.addEventListener('click', async () => {
    if (!activeSessionId) return;
    const s = sessions.find(item => item.session_id === activeSessionId);
    const label = s && s.issue_number ? `Issue #${s.issue_number}` : 'this agent task';
    if (!confirm(`Move ${label} to 'Done' on the GitHub Project Board and complete this session?`)) return;

    btnDoneCurrent.disabled = true;
    btnDoneCurrent.textContent = 'Completing...';

    try {
      const res = await fetch(`/api/agents/${activeSessionId}/complete`, {
        method: 'POST'
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to complete agent');
    } catch (err) {
      alert('Error completing agent: ' + err.message);
    } finally {
      btnDoneCurrent.disabled = false;
      btnDoneCurrent.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> Mark Done`;
    }
  });
}
