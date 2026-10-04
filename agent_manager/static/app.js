
// ---- Quota limit notifications ----
if ('Notification' in window && Notification.permission === 'default') {
  Notification.requestPermission().catch(() => {});
}
function showQuotaToast(data) {
  const stack = document.getElementById('toast-stack');
  const label = data.issue_number ? `${data.repo} #${data.issue_number}` : data.title;
  if (stack) {
    const t = document.createElement('div');
    t.className = 'toast-quota';
    t.innerHTML = `<div class="toast-title">🚫 Quota limit reached — ${escapeHtml(label || '')}</div><div class="toast-body">${escapeHtml(data.message || '')}</div>`;
    t.addEventListener('click', () => { selectSession(data.session_id); t.remove(); });
    stack.appendChild(t);
    setTimeout(() => t.remove(), 20000);
  }
  if ('Notification' in window && Notification.permission === 'granted') {
    const n = new Notification('Agent quota limit reached', { body: `${label}: ${data.message || ''}`.slice(0, 200) });
    n.onclick = () => { window.focus(); selectSession(data.session_id); };
  }
  document.title = '🚫 Quota hit — Agent Manager';
}
function renderQuotaBanner(session) {
  const banner = document.getElementById('quota-alert-banner');
  if (!banner) return;
  if (session && session.quota_exceeded) {
    banner.classList.remove('hidden');
    document.getElementById('quota-alert-text').textContent =
      (session.quota_message || 'The model provider rejected the request.') + ' Your work is preserved.';
  } else {
    banner.classList.add('hidden');
  }
}
document.addEventListener('DOMContentLoaded', () => {
  const btnSettings = document.getElementById('btn-quota-settings');
  const btnResume = document.getElementById('btn-quota-resume');
  if (btnSettings) btnSettings.addEventListener('click', () => {
    const s = document.getElementById('btn-settings') || document.querySelector('[id*="settings"]');
    if (s) s.click();
  });
  if (btnResume) btnResume.addEventListener('click', async () => {
    if (!activeSessionId) return;
    await fetch(`/api/agents/${activeSessionId}/resume`, { method: 'POST' });
    document.title = 'Agent Manager';
  });

  // Global listener for interactive file viewer badges
  document.addEventListener('click', (e) => {
    const badge = e.target.closest('.file-clickable-badge');
    if (badge) {
      const filePath = badge.getAttribute('data-filepath');
      const startLine = badge.getAttribute('data-startline');
      const endLine = badge.getAttribute('data-endline');
      if (filePath && activeSessionId && typeof window.openFileViewer === 'function') {
        window.openFileViewer(activeSessionId, filePath, { startLine, endLine });
      }
    }
  });
});

// Agent Activity & Stall Tracking
const agentActivityBar = document.getElementById('agent-activity-bar');
const activitySpinner = document.getElementById('activity-spinner');
const activityText = document.getElementById('activity-text');
const btnInterrupt = document.getElementById('btn-interrupt');

if (btnInterrupt) {
  btnInterrupt.addEventListener('click', async () => {
    if (!activeSessionId) return;
    btnInterrupt.disabled = true;
    btnInterrupt.textContent = 'Interrupting...';
    try {
      const data = await safeFetchJson(`/api/agents/${activeSessionId}/interrupt`, { method: 'POST' });
      console.log('Interrupted:', data);
    } catch (err) {
      alert('Error interrupting agent: ' + extractErrorMessage(err));
    } finally {
      btnInterrupt.disabled = false;
      btnInterrupt.textContent = 'Interrupt & Re-prompt';
    }
  });
}

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

let currentFilter = 'active'; // 'active' | 'archived' | 'all'

function handleWsMessage(msg) {
  switch (msg.type) {
    case 'init':
      sessions = msg.data || [];
      renderSessionsList();
      updateStats();
      if (sessions.length > 0 && !activeSessionId) {
        const visible = getFilteredSessions();
        if (visible.length > 0) {
          selectSession(visible[0].session_id);
        } else {
          selectSession(sessions[0].session_id);
        }
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

    case 'session_deleted':
      const deletedIdx = sessions.findIndex(s => s.session_id === msg.data.session_id);
      if (deletedIdx !== -1) {
        sessions.splice(deletedIdx, 1);
      }
      if (activeSessionId === msg.data.session_id) {
        activeSessionId = null;
        const visible = getFilteredSessions();
        if (visible.length > 0) {
          selectSession(visible[0].session_id);
        } else {
          consoleActive.classList.add('hidden');
          consoleEmpty.classList.remove('hidden');
        }
      }
      renderSessionsList();
      updateStats();
      break;

    case 'message_added':
      const { session_id, message } = msg.data;
      const targetSession = sessions.find(s => s.session_id === session_id);
      if (targetSession) {
        targetSession.messages.push(message);
        if (message.role === 'TOOL_CALL') targetSession.turn_count++;
      }
      if (activeSessionId === session_id) {
        finalizeThoughtBubble();
        if (currentStreamingBubble) {
          currentStreamingBubble.remove();
          currentStreamingBubble = null;
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
      if (activeSessionId === thoughtSid) {
        handleThoughtStream(thoughtDelta, thoughtModel);
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

let currentThoughtBubble = null;
let thoughtStartTime = null;
let thoughtTimerInterval = null;

function handleThoughtStream(delta, model = 'Gemini 3.1 Pro') {
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
  if (textEl) {
    textEl.textContent += delta;
  }
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
  finalizeThoughtBubble();
  if (!currentStreamingBubble) {
    currentStreamingBubble = document.createElement('div');
    currentStreamingBubble.className = 'msg-bubble msg-agent';
    currentStreamingBubble.innerHTML = `<span class="msg-role-tag">AGENT (STREAMING)</span><div class="msg-content"></div>`;
    transcriptStream.appendChild(currentStreamingBubble);
  }
  const contentEl = currentStreamingBubble.querySelector('.msg-content');
  contentEl.textContent += token;
}

function getFilteredSessions() {
  if (currentFilter === 'active') {
    return sessions.filter(s => !s.is_archived);
  } else if (currentFilter === 'archived') {
    return sessions.filter(s => !!s.is_archived);
  }
  return sessions;
}

function updateStats() {
  const activeCount = sessions.filter(s => !s.is_archived && (s.status === 'RUNNING' || s.status === 'INITIALIZING')).length;
  const compCount = sessions.filter(s => s.status === 'COMPLETED').length;
  const totalTokens = sessions.reduce((acc, s) => acc + (s.token_count || 0), 0);

  statActive.textContent = activeCount;
  statCompleted.textContent = compCount;
  statTokens.textContent = totalTokens;

  // Filter badge counts
  const totalActive = sessions.filter(s => !s.is_archived).length;
  const totalArchived = sessions.filter(s => !!s.is_archived).length;
  const countActiveEl = document.getElementById('count-filter-active');
  const countArchivedEl = document.getElementById('count-filter-archived');
  const countAllEl = document.getElementById('count-filter-all');
  if (countActiveEl) countActiveEl.textContent = totalActive;
  if (countArchivedEl) countArchivedEl.textContent = totalArchived;
  if (countAllEl) countAllEl.textContent = sessions.length;

  const filtered = getFilteredSessions();
  sessionsCount.textContent = filtered.length;
}

function renderSessionsList() {
  const filtered = getFilteredSessions();

  if (filtered.length === 0) {
    sessionsEmpty.classList.remove('hidden');
    const emptyP = sessionsEmpty.querySelector('p');
    if (emptyP) {
      if (currentFilter === 'archived') {
        emptyP.textContent = 'No archived agents.';
      } else if (currentFilter === 'active') {
        emptyP.textContent = 'No active agents.';
      } else {
        emptyP.textContent = 'No agents recorded yet.';
      }
    }
  } else {
    sessionsEmpty.classList.add('hidden');
  }

  // Preserve scroll & remove old cards
  const existingCards = sessionsList.querySelectorAll('.session-card');
  existingCards.forEach(c => c.remove());

  filtered.forEach(session => {
    const card = document.createElement('div');
    card.className = `session-card ${session.session_id === activeSessionId ? 'selected' : ''} ${session.is_archived ? 'card-archived' : ''}`;
    card.dataset.id = session.session_id;

    const statusBadgeClass = session.is_archived ? 'badge-archived' : getStatusBadgeClass(session.status);
    const badgeText = session.is_archived ? '📦 ARCHIVED' : (session.quota_exceeded ? '🚫 QUOTA' : session.status);

    card.innerHTML = `
      <div class="card-top">
        <span class="card-status-badge ${session.quota_exceeded && !session.is_archived ? 'badge-quota' : statusBadgeClass}">${badgeText}</span>
        ${session.is_compacted ? '<span class="badge-compacted" title="Chat compacted">📦 COMPACT</span>' : ''}
        <div class="session-card-actions">
          <span class="card-time">${formatTime(session.started_at)}</span>
          ${session.is_archived 
            ? `<button class="card-action-btn btn-quick-unarchive" title="Restore agent" data-id="${session.session_id}">📂</button>`
            : `<button class="card-action-btn btn-quick-archive" title="Archive agent" data-id="${session.session_id}">📦</button>`
          }
        </div>

      </div>
      <div class="card-title">${escapeHtml(session.title)}</div>
      ${session.status === 'RUNNING' ? `
        <div class="card-live-activity" title="${escapeHtml(session.current_activity || 'Reasoning & executing...')}">
          <span class="pulse-indicator-purple"></span>
          <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(session.current_activity || 'Reasoning & executing...')}</span>
        </div>
      ` : ''}
      <div class="card-bottom">
        <span>${session.issue_number ? '#' + session.issue_number : 'ad-hoc'}</span>
        <span>${session.turn_count || 0} turns • ${session.token_count || 0} tok</span>
      </div>
    `;

    // Quick action buttons inside card
    const quickArchiveBtn = card.querySelector('.btn-quick-archive');
    if (quickArchiveBtn) {
      quickArchiveBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        archiveAgent(session.session_id);
      });
    }
    const quickUnarchiveBtn = card.querySelector('.btn-quick-unarchive');
    if (quickUnarchiveBtn) {
      quickUnarchiveBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        unarchiveAgent(session.session_id);
      });
    }

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
  renderQuotaBanner(session);
  // Update live activity status & hang indicator
  if (agentActivityBar && activityText) {
    if (session.is_stalled) {
      agentActivityBar.classList.add('stalled');
      activitySpinner.style.display = 'inline-block';
      activityText.textContent = session.current_activity || '⚠️ Agent is taking longer than expected. You can type below to re-prompt or click Interrupt.';
      if (btnInterrupt) btnInterrupt.classList.remove('hidden');
    } else if (session.status === 'RUNNING') {
      agentActivityBar.classList.remove('stalled');
      activitySpinner.style.display = 'inline-block';
      activityText.innerHTML = `<span class="pulse-indicator-purple" style="margin-right: 6px;"></span><strong>${escapeHtml(session.model || 'Agent')}:</strong> ${escapeHtml(session.current_activity || 'Reasoning & executing...')}`;
      if (btnInterrupt) btnInterrupt.classList.add('hidden');
    } else if (session.status === 'IN_REVIEW') {
      agentActivityBar.classList.remove('stalled');
      activitySpinner.style.display = 'none';
      activityText.textContent = '💬 Turn complete. Waiting for your input or review.';
      if (btnInterrupt) btnInterrupt.classList.add('hidden');
    } else {
      agentActivityBar.classList.remove('stalled');
      activitySpinner.style.display = 'none';
      activityText.textContent = `Status: ${session.status}`;
      if (btnInterrupt) btnInterrupt.classList.add('hidden');
    }
  }

  currentStatusTag.textContent = session.status;
  currentStatusTag.className = `status-tag ${getStatusBadgeClass(session.status).replace('badge-', 'tag-')}`;

  const currentArchivedTag = document.getElementById('current-archived-tag');
  if (currentArchivedTag) {
    if (session.is_archived) {
      currentArchivedTag.classList.remove('hidden');
    } else {
      currentArchivedTag.classList.add('hidden');
    }
  }

  const btnArchiveCurrent = document.getElementById('btn-archive-current');
  const btnUnarchiveCurrent = document.getElementById('btn-unarchive-current');
  if (btnArchiveCurrent && btnUnarchiveCurrent) {
    if (session.is_archived) {
      btnArchiveCurrent.classList.add('hidden');
      btnUnarchiveCurrent.classList.remove('hidden');
    } else {
      btnArchiveCurrent.classList.remove('hidden');
      btnUnarchiveCurrent.classList.add('hidden');
    }
  }

  currentTitle.textContent = session.title;
  currentRepo.textContent = session.repo;
  currentBranch.textContent = session.git_branch || 'main';
  currentWorktree.textContent = session.worktree_path ? session.worktree_path.split(/[\\/]/).slice(-2).join('/') : 'in-repo';
  turnCounter.textContent = `Turns: ${session.turn_count || 0} • Tokens: ${session.token_count || 0}`;

  const currentModelTag = document.getElementById('current-model-tag');
  const currentEffortTag = document.getElementById('current-effort-tag');
  const currentPipelineTag = document.getElementById('current-pipeline-tag');
  if (currentModelTag) currentModelTag.textContent = session.model || 'gemini-3.8-flash';
  if (currentEffortTag) currentEffortTag.textContent = `effort: ${session.effort || 'high'}`;
  if (currentPipelineTag) {
    if (session.workflow_pipeline_enabled) {
      currentPipelineTag.textContent = `PIPELINE: ${session.workflow_stage || 'ACTIVE'}`;
      currentPipelineTag.classList.remove('hidden');
    } else {
      currentPipelineTag.textContent = 'MODE: DIRECT';
    }
  }

  btnStopCurrent.disabled = (session.status === 'STOPPED' || session.status === 'COMPLETED' || session.status === 'FAILED' || session.is_archived);
  updateOverviewPanel(session);
  if (typeof window.updateAgentTabsContext === 'function') {
    window.updateAgentTabsContext(session.session_id);
  }
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
    const tName = msg.tool_name || 'Terminal';
    const isGenericDone = !msg.content || msg.content.trim() === 'Done';
    const headerLabel = isGenericDone ? `AGY TERMINAL: ${escapeHtml(tName).toUpperCase()}` : `AGY TERMINAL LOG: ${escapeHtml(tName).toUpperCase()}`;
    if (typeof window.createCommandOutputUI === 'function') {
      const outputCard = window.createCommandOutputUI(msg.content, headerLabel);
      bubble.appendChild(outputCard);
    } else {
      bubble.innerHTML = `
        <div class="terminal-header">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
          <span>${headerLabel}</span>
        </div>
        <div class="terminal-body">${escapeHtml(msg.content)}</div>
      `;
    }
  } else if (msg.role === 'TOOL_CALL') {
    bubble.className = 'msg-tool';
    const tName = msg.tool_name || 'tool';
    const args = msg.tool_args || {};

    let targetBadge = '';
    let actionDesc = '';

    if (tName === 'view_file') {
      const p = args.AbsolutePath || args.path || '';
      const base = p.split(/[\\/]/).pop() || '';
      const startLine = args.StartLine || '';
      const endLine = args.EndLine || '';
      targetBadge = base ? `<span class="tool-tag-file file-clickable-badge" data-filepath="${escapeHtml(p)}" data-startline="${escapeHtml(String(startLine))}" data-endline="${escapeHtml(String(endLine))}" title="Click to view file in interactive viewer">📄 ${escapeHtml(base)}</span>` : '';
      const lineRange = (startLine && endLine) ? ` (lines ${startLine}-${endLine})` : '';
      const action = args.toolAction || args.toolSummary || '';
      actionDesc = action ? `${action}: ${p}${lineRange}` : `${p}${lineRange}`;
    } else if (tName === 'replace_file_content' || tName === 'write_to_file' || tName === 'multi_replace_file_content') {
      const p = args.TargetFile || args.path || '';
      const base = p.split(/[\\/]/).pop() || '';
      const icon = tName === 'write_to_file' ? '📝 Create' : '✏️ Edit';
      targetBadge = base ? `<span class="tool-tag-file file-clickable-badge" data-filepath="${escapeHtml(p)}" title="Click to view file in interactive viewer">${icon}: ${escapeHtml(base)}</span>` : '';
      const instr = args.Instruction || args.Description || args.toolAction || args.toolSummary || '';
      actionDesc = instr ? `${p} - ${instr}` : p;
    } else if (tName === 'run_command') {
      const cmd = args.CommandLine || args.command || '';
      targetBadge = `<span class="tool-tag-cmd">💻 Shell</span>`;
      const summary = args.toolSummary || args.toolAction || '';
      actionDesc = summary ? `${summary}: ${cmd}` : cmd;
    } else if (tName === 'call_mcp_tool') {
      const sub = args.ToolName || 'tool';
      const server = args.ServerName ? `[${args.ServerName}] ` : '';
      targetBadge = `<span class="tool-tag-mcp">🔌 MCP ${escapeHtml(server + sub)}</span>`;
      const subArgs = args.Arguments ? JSON.stringify(args.Arguments) : '';
      actionDesc = subArgs ? `${sub}(${subArgs})` : sub;
    }

    const headerTitle = targetBadge || `<span>TOOL EXECUTION: ${escapeHtml(tName)}</span>`;
    const bodyContent = actionDesc ? escapeHtml(actionDesc) : escapeHtml(msg.content);

    bubble.innerHTML = `
      <div class="tool-header">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
        <span>TOOL EXECUTION: ${escapeHtml(tName)}</span>
        ${targetBadge}
      </div>
      <div class="tool-args">${bodyContent}</div>
    `;

    // Render interactive visual diff for file edit/create tools
    if (typeof window.createDiffViewerUI === 'function') {
      if (tName === 'replace_file_content' && (args.TargetContent || args.ReplacementContent)) {
        const diffBlock = window.createDiffViewerUI(args.TargetContent || '', args.ReplacementContent || '');
        bubble.appendChild(diffBlock);
      } else if (tName === 'write_to_file' && args.CodeContent) {
        const diffBlock = window.createDiffViewerUI('', args.CodeContent || '');
        bubble.appendChild(diffBlock);
      }
    }
  } else if (msg.role === 'SYSTEM') {
    if (msg.content && msg.content.includes('Chat Compacted & Compressed')) {
      bubble.className = 'msg-bubble msg-compacted';
      bubble.innerHTML = `
        <div class="msg-compacted-header">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 14 10 14 10 20"></polyline><polyline points="20 10 14 10 14 4"></polyline><line x1="14" y1="10" x2="21" y2="3"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg>
          <span>CHAT COMPACTED & COMPRESSED (TOKEN OPTIMIZATION)</span>
        </div>
        <div class="msg-compacted-body">${formatContent(msg.content.replace('📦 **Chat Compacted & Compressed (Token Optimization)**\n', ''))}</div>
      `;
    } else {
      bubble.className = 'msg-bubble msg-system';
      bubble.innerHTML = `<strong>SYSTEM:</strong> ${escapeHtml(msg.content)}`;
    }
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
    const data = await safeFetchJson(`/api/agents/${activeSessionId}/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'Stopped manually from UI Control Plane' })
    });
    console.log(data);
  } catch (err) {
    alert('Failed to stop agent: ' + extractErrorMessage(err));
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
    await safeFetchJson(`/api/agents/${activeSessionId}/context`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ context: text })
    });
    contextInput.value = '';
  } catch (err) {
    alert('Error injecting context: ' + extractErrorMessage(err));
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
const simEventType = document.getElementById('sim-event-type');
const simGroupTitle = document.getElementById('sim-group-title');
const simGroupBody = document.getElementById('sim-group-body');
const simGroupComment = document.getElementById('sim-group-comment');

if (simEventType) {
  simEventType.addEventListener('change', () => {
    if (simEventType.value === 'issue_comment') {
      if (simGroupTitle) simGroupTitle.classList.add('hidden');
      if (simGroupBody) simGroupBody.classList.add('hidden');
      if (simGroupComment) simGroupComment.classList.remove('hidden');
    } else {
      if (simGroupTitle) simGroupTitle.classList.remove('hidden');
      if (simGroupBody) simGroupBody.classList.remove('hidden');
      if (simGroupComment) simGroupComment.classList.add('hidden');
    }
  });
}

btnSimulateModal.addEventListener('click', () => modalSimulate.classList.remove('hidden'));
btnCloseSimulate.addEventListener('click', () => modalSimulate.classList.add('hidden'));
btnCancelSimulate.addEventListener('click', () => modalSimulate.classList.add('hidden'));

btnSubmitSimulate.addEventListener('click', async () => {
  const eventType = simEventType ? simEventType.value : 'issues';
  const issueNum = parseInt(document.getElementById('sim-issue-num').value) || 6;
  const issueTitle = document.getElementById('sim-issue-title').value;
  const issueBody = document.getElementById('sim-issue-body').value;
  const commentBody = document.getElementById('sim-comment-body') ? document.getElementById('sim-comment-body').value : '';

  btnSubmitSimulate.disabled = true;
  btnSubmitSimulate.textContent = 'Simulating...';

  try {
    const payload = eventType === 'issue_comment' ? {
      event_type: 'issue_comment',
      action: 'created',
      issue_number: issueNum,
      comment_body: commentBody,
      commenter: 'reviewer',
      repo: 'BowenMichael/f1-frontend'
    } : {
      event_type: 'issues',
      action: 'labeled',
      label: 'agent:ready',
      issue_number: issueNum,
      issue_title: issueTitle,
      issue_body: issueBody,
      repo: 'BowenMichael/f1-frontend'
    };

    const data = await safeFetchJson('/api/webhooks/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    modalSimulate.classList.add('hidden');
    if (data.session) {
      selectSession(data.session.session_id);
    } else if (data.result && data.result.session_id) {
      selectSession(data.result.session_id);
    }
  } catch (err) {
    alert('Failed to simulate webhook: ' + extractErrorMessage(err));
  } finally {
    btnSubmitSimulate.disabled = false;
    btnSubmitSimulate.textContent = 'Simulate Webhook';
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
    const session = await safeFetchJson('/api/agents/spawn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        repo: repo,
        issue_number: issueNumVal ? parseInt(issueNumVal) : null,
        prompt: prompt
      })
    });
    modalLaunch.classList.add('hidden');
    selectSession(session.session_id);
  } catch (err) {
    alert('Failed to launch agent: ' + extractErrorMessage(err));
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
  if (typeof window.renderMarkdown === 'function') {
    return window.renderMarkdown(str);
  }
  // Basic markdown-like line break and code escaping fallback
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

function showToast(msg, type = 'info') {
  const stack = document.getElementById('toast-stack');
  if (stack) {
    const t = document.createElement('div');
    t.className = 'toast-quota';
    t.style.borderLeft = type === 'error' ? '4px solid #ef4444' : '4px solid #10b981';
    t.innerHTML = `<div class="toast-title" style="color: ${type === 'error' ? '#ef4444' : '#10b981'}; font-weight: 700;">${type === 'error' ? '⚠️ Error' : '✅ Settings Saved'}</div><div class="toast-body">${escapeHtml(msg)}</div>`;
    stack.appendChild(t);
    setTimeout(() => t.remove(), 6000);
  }
}

async function loadSettings() {
  try {
    const data = await safeFetchJson('/api/settings');
    if (!data) return;

    // API Key status
    if (data.has_gemini_api_key) {
      if (apiKeyBanner) apiKeyBanner.classList.add('hidden');
      if (keyStatusDisplay) {
        keyStatusDisplay.textContent = 'Active: ' + data.masked_gemini_api_key;
        keyStatusDisplay.style.color = 'var(--accent-green)';
      }
    } else {
      if (apiKeyBanner) apiKeyBanner.classList.remove('hidden');
      if (keyStatusDisplay) {
        keyStatusDisplay.textContent = 'Not configured';
        keyStatusDisplay.style.color = 'var(--accent-amber)';
      }
    }

    // Default Model & Effort
    const selectModel = document.getElementById('select-default-model');
    const selectEffort = document.getElementById('select-default-effort');
    const badgeModel = document.getElementById('current-model-badge');
    const badgeEffort = document.getElementById('current-effort-badge');
    const checkOverage = document.getElementById('check-allow-overage');
    const inputMaxTokens = document.getElementById('input-max-tokens');

    if (selectModel && data.default_model) {
      let matched = false;
      for (const opt of selectModel.options) {
        if (opt.value === data.default_model) {
          selectModel.value = data.default_model;
          matched = true;
          break;
        }
      }
      if (!matched) {
        const base = data.default_model.replace(/-(low|medium|high|xhigh|max)$/, '');
        for (const opt of selectModel.options) {
          if (opt.value === base) {
            selectModel.value = base;
            matched = true;
            break;
          }
        }
      }
    }

    if (selectEffort && data.default_effort) {
      selectEffort.value = data.default_effort;
    }

    if (badgeModel && data.default_model) {
      badgeModel.textContent = data.default_model;
    }

    if (badgeEffort && data.default_effort) {
      badgeEffort.textContent = data.default_effort;
    }

    if (checkOverage && typeof data.allow_overage_credits === 'boolean') {
      checkOverage.checked = data.allow_overage_credits;
    }

    if (inputMaxTokens && data.max_session_tokens) {
      inputMaxTokens.value = data.max_session_tokens;
    }

    const checkAutoCompact = document.getElementById('check-auto-compact');
    if (checkAutoCompact && typeof data.compact_completed_chat === 'boolean') {
      checkAutoCompact.checked = data.compact_completed_chat;
    }

    const checkGuardrails = document.getElementById('check-guardrails-enabled');
    const guardrailsStatus = document.getElementById('guardrails-toggle-status');
    const guardrailsWarning = document.getElementById('guardrails-warning-note');
    const topbarGuardrailsBadge = document.getElementById('badge-guardrails-status');

    function updateGuardrailsUI(enabled) {
      if (guardrailsStatus) {
        if (enabled) {
          guardrailsStatus.textContent = 'Active';
          guardrailsStatus.style.background = 'rgba(16, 185, 129, 0.15)';
          guardrailsStatus.style.color = '#34d399';
          guardrailsStatus.style.borderColor = 'rgba(16, 185, 129, 0.3)';
        } else {
          guardrailsStatus.textContent = 'Disabled';
          guardrailsStatus.style.background = 'rgba(239, 68, 68, 0.2)';
          guardrailsStatus.style.color = '#f87171';
          guardrailsStatus.style.borderColor = 'rgba(239, 68, 68, 0.4)';
        }
      }
      if (guardrailsWarning) {
        if (enabled) {
          guardrailsWarning.classList.add('hidden');
        } else {
          guardrailsWarning.classList.remove('hidden');
        }
      }
      if (topbarGuardrailsBadge) {
        if (enabled) {
          topbarGuardrailsBadge.classList.add('hidden');
        } else {
          topbarGuardrailsBadge.classList.remove('hidden');
        }
      }
    }

    if (checkGuardrails) {
      const isEnabled = typeof data.guardrails_enabled === 'boolean' ? data.guardrails_enabled : true;
      checkGuardrails.checked = isEnabled;
      updateGuardrailsUI(isEnabled);

      if (!checkGuardrails.dataset.listenerBound) {
        checkGuardrails.dataset.listenerBound = 'true';
        checkGuardrails.addEventListener('change', () => {
          updateGuardrailsUI(checkGuardrails.checked);
        });
      }
    }

    const checkAutoMerge = document.getElementById('check-auto-merge');
    if (checkAutoMerge && typeof data.auto_merge_enabled === 'boolean') {
      checkAutoMerge.checked = data.auto_merge_enabled;
    }

    if (topbarGuardrailsBadge && !topbarGuardrailsBadge.dataset.listenerBound) {
      topbarGuardrailsBadge.dataset.listenerBound = 'true';
      topbarGuardrailsBadge.addEventListener('click', () => {
        modalSettings.classList.remove('hidden');
        loadSettings();
      });
    }

    const checkWorkflowPipeline = document.getElementById('check-workflow-pipeline');
    if (checkWorkflowPipeline && typeof data.workflow_pipeline_enabled === 'boolean') {
      checkWorkflowPipeline.checked = data.workflow_pipeline_enabled;
    }

    const selSumModel = document.getElementById('select-pipeline-sum-model');
    if (selSumModel && data.pipeline_summary_model) selSumModel.value = data.pipeline_summary_model;

    const selSumEffort = document.getElementById('select-pipeline-sum-effort');
    if (selSumEffort && data.pipeline_summary_effort) selSumEffort.value = data.pipeline_summary_effort;

    const selPlanModel = document.getElementById('select-pipeline-plan-model');
    if (selPlanModel && data.pipeline_planning_model) selPlanModel.value = data.pipeline_planning_model;

    const selPlanEffort = document.getElementById('select-pipeline-plan-effort');
    if (selPlanEffort && data.pipeline_planning_effort) selPlanEffort.value = data.pipeline_planning_effort;

    const selImplModel = document.getElementById('select-pipeline-impl-model');
    if (selImplModel && data.pipeline_implementation_model) selImplModel.value = data.pipeline_implementation_model;

    const selImplEffort = document.getElementById('select-pipeline-impl-effort');
    if (selImplEffort && data.pipeline_implementation_effort) selImplEffort.value = data.pipeline_implementation_effort;

    // Mode
    if (data.agy_mode === 'terminal') {
      const modeTerm = document.getElementById('mode-terminal');
      if (modeTerm) modeTerm.checked = true;
    } else {
      const modeWeb = document.getElementById('mode-webstream');
      if (modeWeb) modeWeb.checked = true;
    }

    // Quota display
    if (data.quota_status) {
      const quotaTitle = document.getElementById('settings-quota-title');
      const quotaTag = document.getElementById('settings-quota-tag');
      const quotaDesc = document.getElementById('settings-quota-desc');
      if (data.quota_status.subscription_quota_reached) {
        if (quotaTitle) quotaTitle.innerHTML = '<span>⚠️</span> Antigravity Quota Reached';
        if (quotaTag) {
          quotaTag.textContent = 'QUOTA LIMITED';
          quotaTag.style.background = 'rgba(239, 68, 68, 0.2)';
          quotaTag.style.color = '#f87171';
          quotaTag.style.border = '1px solid #ef4444';
        }
        if (quotaDesc) {
          quotaDesc.innerHTML = `Baseline quota reached. ${data.allow_overage_credits ? '<strong>AI Credit Overages are active</strong> to prevent interruptions.' : 'Enable <strong>AI Credit Overages</strong> or switch models below.'}`;
        }
      } else {
        if (quotaTitle) quotaTitle.innerHTML = '<span>✅</span> Antigravity Subscription Active';
        if (quotaTag) {
          quotaTag.textContent = 'FRESH QUOTA';
          quotaTag.style.background = 'rgba(16, 185, 129, 0.2)';
          quotaTag.style.color = '#34d399';
          quotaTag.style.border = '1px solid #10b981';
        }
        if (quotaDesc) {
          quotaDesc.innerHTML = `<strong>Google Antigravity Subscription</strong> is active and verified.<br>${data.allow_overage_credits ? 'AI Credit Overages (useG1Credits) enabled.' : 'Zero API key needed.'}`;
        }
      }
    }

    // Target Repository
    const inputRepo = document.getElementById('setting-default-repo');
    const launchRepo = document.getElementById('launch-repo');
    if (data.default_repo) {
      if (inputRepo) inputRepo.value = data.default_repo;
      if (launchRepo) launchRepo.value = data.default_repo;
    }
  } catch (e) {
    console.error('Failed to load settings:', e);
  }
}

// Initial settings load on page startup
loadSettings();

btnSettingsModal.addEventListener('click', () => {
  modalSettings.classList.remove('hidden');
  loadSettings();
});
btnBannerConfigure.addEventListener('click', () => {
  modalSettings.classList.remove('hidden');
  loadSettings();
});
btnCloseSettings.addEventListener('click', () => modalSettings.classList.add('hidden'));
btnCancelSettings.addEventListener('click', () => modalSettings.classList.add('hidden'));

const selectDefaultModelEl = document.getElementById('select-default-model');
if (selectDefaultModelEl) {
  selectDefaultModelEl.addEventListener('change', () => {
    const badgeModel = document.getElementById('current-model-badge');
    if (badgeModel) badgeModel.textContent = selectDefaultModelEl.value;
  });
}

const selectDefaultEffortEl = document.getElementById('select-default-effort');
if (selectDefaultEffortEl) {
  selectDefaultEffortEl.addEventListener('change', () => {
    const badgeEffort = document.getElementById('current-effort-badge');
    if (badgeEffort) badgeEffort.textContent = selectDefaultEffortEl.value;
  });
}

btnSaveSettings.addEventListener('click', async () => {
  const selectedMode = document.querySelector('input[name="agy_execution_mode"]:checked')?.value || 'web_stream';
  const selectedModel = document.getElementById('select-default-model')?.value || 'gemini-3.8-flash';
  const selectedEffort = document.getElementById('select-default-effort')?.value || 'high';
  const allowOverage = document.getElementById('check-allow-overage')?.checked ?? true;
  const maxTokens = parseInt(document.getElementById('input-max-tokens')?.value || '150000', 10);
  const autoCompact = document.getElementById('check-auto-compact')?.checked ?? true;
  const guardrailsEnabled = document.getElementById('check-guardrails-enabled')?.checked ?? true;
  const autoMergeEnabled = document.getElementById('check-auto-merge')?.checked ?? false;
  const workflowPipeline = document.getElementById('check-workflow-pipeline')?.checked ?? false;
  const sumModel = document.getElementById('select-pipeline-sum-model')?.value || 'gemini-3.8-flash';
  const sumEffort = document.getElementById('select-pipeline-sum-effort')?.value || 'low';
  const planModel = document.getElementById('select-pipeline-plan-model')?.value || 'gemini-3.1-pro';
  const planEffort = document.getElementById('select-pipeline-plan-effort')?.value || 'high';
  const implModel = document.getElementById('select-pipeline-impl-model')?.value || 'gemini-3.8-flash';
  const implEffort = document.getElementById('select-pipeline-impl-effort')?.value || 'low';
  const repoVal = document.getElementById('setting-default-repo')?.value?.trim();
  const key = inputGeminiKey?.value.trim();

  btnSaveSettings.disabled = true;
  btnSaveSettings.textContent = 'Saving...';
  try {
    const payload = {
      agy_mode: selectedMode,
      default_model: selectedModel,
      default_effort: selectedEffort,
      effort_level: selectedEffort,
      allow_overage_credits: allowOverage,
      max_session_tokens: maxTokens,
      compact_completed_chat: autoCompact,
      guardrails_enabled: guardrailsEnabled,
      auto_merge_enabled: autoMergeEnabled,
      workflow_pipeline_enabled: workflowPipeline,
      pipeline_summary_model: sumModel,
      pipeline_summary_effort: sumEffort,
      pipeline_planning_model: planModel,
      pipeline_planning_effort: planEffort,
      pipeline_implementation_model: implModel,
      pipeline_implementation_effort: implEffort
    };
    if (repoVal) {
      payload.default_repo = repoVal;
    }
    if (key) {
      payload.gemini_api_key = key;
    }
    const data = await safeFetchJson('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    modalSettings.classList.add('hidden');
    if (inputGeminiKey) inputGeminiKey.value = '';

    // Update badges
    const badgeModel = document.getElementById('current-model-badge');
    const badgeEffort = document.getElementById('current-effort-badge');
    if (badgeModel && data.default_model) badgeModel.textContent = data.default_model;
    if (badgeEffort && data.default_effort) badgeEffort.textContent = data.default_effort;

    showToast(`Settings saved! Model: ${data.default_model} (${data.default_effort} effort). Will apply on next prompt.`);
    await loadSettings();
  } catch (err) {
    showToast('Failed to save settings: ' + extractErrorMessage(err), 'error');
  } finally {
    btnSaveSettings.disabled = false;
    btnSaveSettings.textContent = 'Save Settings';
  }
});


// Check on boot
loadSettings();


// Action: Sync Board
const btnSyncBoard = document.getElementById('btn-sync-board');
if (btnSyncBoard) {
  btnSyncBoard.addEventListener('click', async () => {
    btnSyncBoard.classList.add('spinning');
    try {
      await safeFetchJson('/api/board/sync', { method: 'POST' });
      // Fetch fresh sessions
      sessions = await safeFetchJson('/api/agents') || [];
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
      const updated = await safeFetchJson(`/api/agents/${activeSessionId}/restart`, {
        method: 'POST'
      });
      const idx = sessions.findIndex(s => s.session_id === updated.session_id);
      if (idx !== -1) sessions[idx] = updated;
      selectSession(updated.session_id);
    } catch (err) {
      alert('Error restarting agent: ' + extractErrorMessage(err));
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
      await safeFetchJson(`/api/agents/${activeSessionId}/launch-terminal`, { method: 'POST' });
      btnOpenTerminal.textContent = 'Terminal Opened!';
      setTimeout(() => {
        btnOpenTerminal.disabled = false;
        btnOpenTerminal.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg> Launch Terminal';
      }, 3000);
    } catch (e) {
      alert('Could not launch terminal: ' + extractErrorMessage(e));
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
      await safeFetchJson(`/api/agents/${activeSessionId}/resume`, { method: 'POST' });
      setTimeout(() => {
        btnResumeCurrent.disabled = false;
        btnResumeCurrent.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Resume';
      }, 1000);
    } catch (e) {
      alert('Could not resume agent: ' + extractErrorMessage(e));
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
      await safeFetchJson(`/api/agents/${activeSessionId}/complete`, {
        method: 'POST'
      });
    } catch (err) {
      alert('Error completing agent: ' + extractErrorMessage(err));
    } finally {
      btnDoneCurrent.disabled = false;
      btnDoneCurrent.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> Mark Done`;
    }
  });
}

// Archive & Unarchive API actions
async function archiveAgent(sessionId) {
  if (!sessionId) return;
  try {
    await safeFetchJson(`/api/agents/${sessionId}/archive`, { method: 'POST' });
    const s = sessions.find(item => item.session_id === sessionId);
    if (s) {
      s.is_archived = true;
      if (s.status === 'RUNNING' || s.status === 'INITIALIZING') s.status = 'STOPPED';
    }
    renderSessionsList();
    updateStats();
    if (activeSessionId === sessionId) {
      updateActiveSessionView(s);
    }
    showToast('Agent session archived successfully.');
  } catch (err) {
    alert('Error archiving agent: ' + extractErrorMessage(err));
  }
}

async function unarchiveAgent(sessionId) {
  if (!sessionId) return;
  try {
    await safeFetchJson(`/api/agents/${sessionId}/unarchive`, { method: 'POST' });
    const s = sessions.find(item => item.session_id === sessionId);
    if (s) {
      s.is_archived = false;
      s.archived_at = null;
    }
    renderSessionsList();
    updateStats();
    if (activeSessionId === sessionId) {
      updateActiveSessionView(s);
    }
    showToast('Agent session restored to active list.');
  } catch (err) {
    alert('Error unarchiving agent: ' + extractErrorMessage(err));
  }
}

// Filter Tab Click Handlers
const filterTabs = document.querySelectorAll('.filter-tab');
filterTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    filterTabs.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    currentFilter = tab.dataset.filter || 'active';
    const sidebarTitle = document.getElementById('sidebar-title');
    if (sidebarTitle) {
      if (currentFilter === 'archived') sidebarTitle.textContent = 'Archived Sessions';
      else if (currentFilter === 'all') sidebarTitle.textContent = 'All Sessions';
      else sidebarTitle.textContent = 'Active Sessions';
    }
    renderSessionsList();
    updateStats();
  });
});

// Session Controls: Archive & Unarchive Buttons
const btnArchiveCurrent = document.getElementById('btn-archive-current');
if (btnArchiveCurrent) {
  btnArchiveCurrent.addEventListener('click', async () => {
    if (!activeSessionId) return;
    if (!confirm('Archive this agent session? It will be hidden from the active list.')) return;
    await archiveAgent(activeSessionId);
  });
}

const btnUnarchiveCurrent = document.getElementById('btn-unarchive-current');
if (btnUnarchiveCurrent) {
  btnUnarchiveCurrent.addEventListener('click', async () => {
    if (!activeSessionId) return;
    await unarchiveAgent(activeSessionId);
  });
}

// Action: Manual Compact Current Chat
const btnCompactCurrent = document.getElementById('btn-compact-current');
if (btnCompactCurrent) {
  btnCompactCurrent.addEventListener('click', async () => {
    if (!activeSessionId) return;
    btnCompactCurrent.disabled = true;
    btnCompactCurrent.textContent = 'Compacting...';
    try {
      await safeFetchJson(`/api/agents/${activeSessionId}/compact`, { method: 'POST' });
      showToast('Chat compacted and compressed successfully! Intermediate tokens condensed.');
    } catch (err) {
      alert('Error compacting chat: ' + extractErrorMessage(err));
    } finally {
      btnCompactCurrent.disabled = false;
      btnCompactCurrent.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 14 10 14 10 20"></polyline><polyline points="20 10 14 10 14 4"></polyline><line x1="14" y1="10" x2="21" y2="3"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg> Compact Chat`;
    }
  });
}

// ==========================================
// Token Telemetry & Timescales Modal
// ==========================================
let currentTelemetryData = null;
let activeTimescale = '24h';

const modalTelemetry = document.getElementById('modal-telemetry');
const btnTelemetryModal = document.getElementById('btn-telemetry-modal');
const btnCloseTelemetry = document.getElementById('btn-close-telemetry');
const btnRefreshTelemetry = document.getElementById('btn-refresh-telemetry');
const statPillTokens = document.getElementById('stat-pill-tokens');

async function fetchAndRenderTelemetry(timescale = activeTimescale) {
  try {
    currentTelemetryData = await safeFetchJson('/api/telemetry/tokens');
    renderTelemetryView(currentTelemetryData, timescale);
  } catch (err) {
    console.error('Error fetching telemetry:', extractErrorMessage(err));
  }
}

function renderTelemetryView(data, timescale) {
  if (!data || !data.summary) return;
  activeTimescale = timescale;

  const s = data.summary;
  let windowTokens = s.last_24h_tokens || 0;
  let windowLabel = 'Tokens consumed in last 24h';

  if (timescale === '1h') {
    windowTokens = s.last_1h_tokens || 0;
    windowLabel = 'Tokens consumed in last 1 hour';
  } else if (timescale === '7d') {
    windowTokens = s.last_7d_tokens || 0;
    windowLabel = 'Tokens consumed in last 7 days';
  } else if (timescale === '30d') {
    windowTokens = s.last_30d_tokens || 0;
    windowLabel = 'Tokens consumed in last 30 days';
  } else if (timescale === 'all') {
    windowTokens = s.all_time_tokens || 0;
    windowLabel = 'All-time cumulative tokens';
  }

  // Update Metric Cards
  const elWindowTokens = document.getElementById('telemetry-window-tokens');
  const elWindowLabel = document.getElementById('telemetry-window-label');
  const elAllTokens = document.getElementById('telemetry-all-tokens');
  const elCacheTokens = document.getElementById('telemetry-cache-tokens');
  const elSessionsCount = document.getElementById('telemetry-sessions-count');

  if (elWindowTokens) elWindowTokens.textContent = windowTokens.toLocaleString();
  if (elWindowLabel) elWindowLabel.textContent = windowLabel;
  if (elAllTokens) elAllTokens.textContent = (s.all_time_tokens || 0).toLocaleString();
  if (elCacheTokens) elCacheTokens.textContent = (s.all_time_cache_read_tokens || 0).toLocaleString();
  if (elSessionsCount) elSessionsCount.textContent = (s.total_sessions_tracked || 0).toLocaleString();

  // Render Trend Bars
  const barsContainer = document.getElementById('telemetry-bars-container');
  const trendTitle = document.getElementById('telemetry-trend-title');

  if (barsContainer) {
    barsContainer.innerHTML = '';
    let trendItems = [];

    if (timescale === '1h' || timescale === '24h') {
      if (trendTitle) trendTitle.textContent = '24-Hour Hourly Consumption Trend';
      trendItems = (data.hourly_trend || []).map(item => ({
        label: item.hour ? item.hour.split(' ')[1] : '',
        fullLabel: item.hour,
        tokens: item.tokens || 0
      }));
    } else {
      if (trendTitle) trendTitle.textContent = `${timescale === '7d' ? '7-Day' : '30-Day'} Daily Consumption Trend`;
      const days = timescale === '7d' ? 7 : 30;
      trendItems = (data.daily_trend || []).slice(-days).map(item => ({
        label: item.date ? item.date.slice(5) : '',
        fullLabel: item.date,
        tokens: item.tokens || 0
      }));
    }

    const maxToks = Math.max(...trendItems.map(i => i.tokens), 100);

    trendItems.forEach(item => {
      const col = document.createElement('div');
      col.className = 'telemetry-bar-col';
      col.title = `${item.fullLabel}: ${item.tokens.toLocaleString()} tokens`;

      const pct = Math.max(3, Math.round((item.tokens / maxToks) * 100));
      col.innerHTML = `
        <div class="telemetry-bar-fill" style="height: ${pct}%;"></div>
        <div style="font-size: 0.65rem; color: var(--text-dim); margin-top: 4px; text-align: center; white-space: nowrap;">${item.label}</div>
      `;
      barsContainer.appendChild(col);
    });
  }

  // Render Model Breakdown
  const modelList = document.getElementById('telemetry-model-list');
  if (modelList) {
    modelList.innerHTML = '';
    const models = data.model_breakdown || data.by_model || [];
    if (models.length === 0) {
      modelList.innerHTML = '<div style="font-size: 0.78rem; color: var(--text-dim);">No model metrics recorded yet.</div>';
    } else {
      models.forEach(m => {
        const row = document.createElement('div');
        row.className = 'breakdown-row';
        row.innerHTML = `
          <div class="breakdown-header">
            <span style="font-weight: 500; color: var(--text-primary);">${escapeHtml(m.model)}</span>
            <span style="color: var(--text-secondary);">${(m.tokens || 0).toLocaleString()} (${m.percentage}%)</span>
          </div>
          <div class="breakdown-track">
            <div class="breakdown-fill" style="width: ${m.percentage}%;"></div>
          </div>
        `;
        modelList.appendChild(row);
      });
    }
  }

  // Render Repo Breakdown
  const repoList = document.getElementById('telemetry-repo-list');
  if (repoList) {
    repoList.innerHTML = '';
    const repos = data.repo_breakdown || data.by_repo || [];
    if (repos.length === 0) {
      repoList.innerHTML = '<div style="font-size: 0.78rem; color: var(--text-dim);">No repository metrics recorded yet.</div>';
    } else {
      repos.forEach(r => {
        const row = document.createElement('div');
        row.className = 'breakdown-row';
        row.innerHTML = `
          <div class="breakdown-header">
            <span style="font-weight: 500; color: var(--text-primary);">${escapeHtml(r.repo)}</span>
            <span style="color: var(--text-secondary);">${(r.tokens || 0).toLocaleString()} (${r.percentage}%)</span>
          </div>
          <div class="breakdown-track">
            <div class="breakdown-fill" style="width: ${r.percentage}%; background: var(--accent-purple);"></div>
          </div>
        `;
        repoList.appendChild(row);
      });
    }
  }
}

// Open Telemetry Modal Handlers
if (btnTelemetryModal) {
  btnTelemetryModal.addEventListener('click', () => {
    if (modalTelemetry) modalTelemetry.classList.remove('hidden');
    fetchAndRenderTelemetry(activeTimescale);
  });
}

if (statPillTokens) {
  statPillTokens.addEventListener('click', () => {
    if (modalTelemetry) modalTelemetry.classList.remove('hidden');
    fetchAndRenderTelemetry(activeTimescale);
  });
}

if (btnCloseTelemetry) {
  btnCloseTelemetry.addEventListener('click', () => {
    if (modalTelemetry) modalTelemetry.classList.add('hidden');
  });
}

if (btnRefreshTelemetry) {
  btnRefreshTelemetry.addEventListener('click', () => {
    fetchAndRenderTelemetry(activeTimescale);
  });
}

if (modalTelemetry) {
  modalTelemetry.addEventListener('click', (e) => {
    if (e.target === modalTelemetry) modalTelemetry.classList.add('hidden');
  });
}

// Timescale Tab Switching
document.querySelectorAll('.telemetry-tabs .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.telemetry-tabs .tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const ts = btn.getAttribute('data-timescale') || '24h';
    if (currentTelemetryData) {
      renderTelemetryView(currentTelemetryData, ts);
    } else {
      fetchAndRenderTelemetry(ts);
    }
  });
});


