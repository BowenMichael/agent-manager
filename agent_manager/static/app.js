// Notification setup
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

// Global State
window.sessions = [];
window.activeSessionId = null;
window.currentFilter = 'active';
window.currentStreamingBubble = null;

function scrollToBottom(smooth = false) {
  const transcriptViewport = document.getElementById('transcript-viewport');
  if (transcriptViewport) {
    if (smooth) transcriptViewport.scrollTo({ top: transcriptViewport.scrollHeight, behavior: 'smooth' });
    else transcriptViewport.scrollTop = transcriptViewport.scrollHeight;
  }
}

function updateActiveSessionView(session) {
  renderQuotaBanner(session);
  const agentActivityBar = document.getElementById('agent-activity-bar');
  const activitySpinner = document.getElementById('activity-spinner');
  const activityText = document.getElementById('activity-text');
  const btnInterrupt = document.getElementById('btn-interrupt');
  const currentStatusTag = document.getElementById('current-status-tag');
  const currentTitle = document.getElementById('current-title');
  const currentRepo = document.getElementById('current-repo');
  const currentBranch = document.getElementById('current-branch');
  const currentWorktree = document.getElementById('current-worktree');
  const turnCounter = document.getElementById('turn-counter');
  const btnStopCurrent = document.getElementById('btn-stop-current');

  if (agentActivityBar && activityText) {
    if (session.is_stalled) {
      agentActivityBar.classList.add('stalled');
      if (activitySpinner) activitySpinner.style.display = 'inline-block';
      activityText.textContent = session.current_activity || '⚠️ Agent taking longer than expected.';
      if (btnInterrupt) btnInterrupt.classList.remove('hidden');
    } else if (session.status === 'RUNNING') {
      agentActivityBar.classList.remove('stalled');
      if (activitySpinner) activitySpinner.style.display = 'inline-block';
      activityText.innerHTML = `<span class="pulse-indicator-purple" style="margin-right: 6px;"></span><strong>${escapeHtml(session.model || 'Agent')}:</strong> ${escapeHtml(session.current_activity || 'Reasoning & executing...')}`;
      if (btnInterrupt) btnInterrupt.classList.add('hidden');
    } else if (session.status === 'IN_REVIEW') {
      agentActivityBar.classList.remove('stalled');
      if (activitySpinner) activitySpinner.style.display = 'none';
      activityText.textContent = '💬 Turn complete. Waiting for your input or review.';
      if (btnInterrupt) btnInterrupt.classList.add('hidden');
    } else {
      agentActivityBar.classList.remove('stalled');
      if (activitySpinner) activitySpinner.style.display = 'none';
      activityText.textContent = `Status: ${session.status}`;
      if (btnInterrupt) btnInterrupt.classList.add('hidden');
    }
  }

  if (currentStatusTag) {
    currentStatusTag.textContent = session.status;
    currentStatusTag.className = `status-tag ${getStatusBadgeClass(session.status).replace('badge-', 'tag-')}`;
  }

  const currentArchivedTag = document.getElementById('current-archived-tag');
  if (currentArchivedTag) {
    if (session.is_archived) currentArchivedTag.classList.remove('hidden');
    else currentArchivedTag.classList.add('hidden');
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

  if (currentTitle) currentTitle.textContent = session.title;
  if (currentRepo) currentRepo.textContent = session.repo;
  if (typeof updateGitHubHeaderLinks === 'function') updateGitHubHeaderLinks(session);
  if (currentBranch) currentBranch.textContent = session.git_branch || 'main';
  if (currentWorktree) currentWorktree.textContent = session.worktree_path ? session.worktree_path.split(/[\\/]/).slice(-2).join('/') : 'in-repo';
  if (turnCounter) turnCounter.textContent = `Turns: ${session.turn_count || 0} • Tokens: ${session.token_count || 0}`;

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

  if (btnStopCurrent) {
    btnStopCurrent.disabled = (session.status === 'STOPPED' || session.status === 'COMPLETED' || session.status === 'FAILED' || session.is_archived);
  }

  if (typeof updateOverviewPanel === 'function') updateOverviewPanel(session);
  if (typeof window.updateAgentTabsContext === 'function') window.updateAgentTabsContext(session.session_id);
}

// Context Actions: Send, Stop, Interrupt
async function sendContext() {
  const contextInput = document.getElementById('context-input');
  const btnSendContext = document.getElementById('btn-send-context');
  if (!contextInput) return;
  const text = contextInput.value.trim();
  if (!text || !window.activeSessionId) return;

  if (btnSendContext) {
    btnSendContext.disabled = true;
    btnSendContext.textContent = 'Sending...';
  }

  try {
    await safeFetchJson(`/api/agents/${window.activeSessionId}/context`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ context: text })
    });
    contextInput.value = '';
  } catch (err) {
    alert('Error injecting context: ' + extractErrorMessage(err));
  } finally {
    if (btnSendContext) {
      btnSendContext.disabled = false;
      btnSendContext.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg> Send Context`;
    }
  }
}

// Global initialization
document.addEventListener('DOMContentLoaded', () => {
  if (typeof window.initActionButtons === 'function') window.initActionButtons();

  // File viewer badge clicks
  document.addEventListener('click', (e) => {
    const badge = e.target.closest('.file-clickable-badge');
    if (badge) {
      const filePath = badge.getAttribute('data-filepath');
      const startLine = badge.getAttribute('data-startline');
      const endLine = badge.getAttribute('data-endline');
      if (filePath && window.activeSessionId && typeof window.openFileViewer === 'function') {
        window.openFileViewer(window.activeSessionId, filePath, { startLine, endLine });
      }
    }
  });

  // Initialize sub-modules
  if (typeof window.initSettingsEvents === 'function') window.initSettingsEvents();
  if (typeof window.initTelemetryEvents === 'function') window.initTelemetryEvents();
  if (typeof window.initModals === 'function') window.initModals();
  if (typeof window.loadSettings === 'function') window.loadSettings();

  if (typeof window.connectWebSocket === 'function') {
    window.connectWebSocket();
  }
});

window.showQuotaToast = showQuotaToast;
window.renderQuotaBanner = renderQuotaBanner;
window.scrollToBottom = scrollToBottom;
window.updateActiveSessionView = updateActiveSessionView;

