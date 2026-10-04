// Sessions List & Dashboard View Module

function getFilteredSessions() {
  if (window.currentFilter === 'active') {
    return window.sessions.filter(s => !s.is_archived);
  } else if (window.currentFilter === 'archived') {
    return window.sessions.filter(s => !!s.is_archived);
  }
  return window.sessions;
}

function updateStats() {
  const statActive = document.getElementById('stat-active');
  const statCompleted = document.getElementById('stat-completed');
  const statTokens = document.getElementById('stat-tokens');
  const sessionsCount = document.getElementById('sessions-count');
  const globalDashboard = document.getElementById('global-dashboard');

  const activeCount = window.sessions.filter(s => !s.is_archived && (s.status === 'RUNNING' || s.status === 'INITIALIZING')).length;
  const compCount = window.sessions.filter(s => s.status === 'COMPLETED').length;
  const totalTokens = window.sessions.reduce((acc, s) => acc + (s.token_count || 0), 0);

  if (statActive) statActive.textContent = activeCount;
  if (statCompleted) statCompleted.textContent = compCount;
  if (statTokens) statTokens.textContent = totalTokens;

  const totalActive = window.sessions.filter(s => !s.is_archived).length;
  const totalArchived = window.sessions.filter(s => !!s.is_archived).length;
  const countActiveEl = document.getElementById('count-filter-active');
  const countArchivedEl = document.getElementById('count-filter-archived');
  const countAllEl = document.getElementById('count-filter-all');
  if (countActiveEl) countActiveEl.textContent = totalActive;
  if (countArchivedEl) countArchivedEl.textContent = totalArchived;
  if (countAllEl) countAllEl.textContent = window.sessions.length;

  const filtered = getFilteredSessions();
  if (sessionsCount) sessionsCount.textContent = filtered.length;

  if (globalDashboard) {
    globalDashboard.sessions = window.sessions;
  }
}

function renderSessionsList() {
  const sessionsList = document.getElementById('sessions-list');
  const sessionsEmpty = document.getElementById('sessions-empty');
  if (!sessionsList) return;

  const filtered = getFilteredSessions();

  if (filtered.length === 0) {
    if (sessionsEmpty) {
      sessionsEmpty.classList.remove('hidden');
      const emptyP = sessionsEmpty.querySelector('p');
      if (emptyP) {
        if (window.currentFilter === 'archived') emptyP.textContent = 'No archived agents.';
        else if (window.currentFilter === 'active') emptyP.textContent = 'No active agents.';
        else emptyP.textContent = 'No agents recorded yet.';
      }
    }
  } else {
    if (sessionsEmpty) sessionsEmpty.classList.add('hidden');
  }

  const existingCards = sessionsList.querySelectorAll('.session-card');
  existingCards.forEach(c => c.remove());

  filtered.forEach(session => {
    const card = document.createElement('div');
    card.className = `session-card ${session.session_id === window.activeSessionId ? 'selected' : ''} ${session.is_archived ? 'card-archived' : ''}`;
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

function showDashboardView() {
  window.activeSessionId = null;
  document.querySelectorAll('.session-card').forEach(c => c.classList.remove('selected'));
  const consoleActive = document.getElementById('console-active');
  const consoleEmpty = document.getElementById('console-empty');
  const globalDashboard = document.getElementById('global-dashboard');

  if (consoleActive) consoleActive.classList.add('hidden');
  if (consoleEmpty) consoleEmpty.classList.add('hidden');
  if (globalDashboard) {
    globalDashboard.classList.remove('hidden');
    globalDashboard.sessions = window.sessions;
  }
}

function selectSession(sessionId) {
  window.activeSessionId = sessionId;
  window.currentStreamingBubble = null;

  document.querySelectorAll('.session-card').forEach(c => {
    c.classList.toggle('selected', c.dataset.id === sessionId);
  });

  const session = window.sessions.find(s => s.session_id === sessionId);
  if (!session) return;

  const globalDashboard = document.getElementById('global-dashboard');
  const consoleActive = document.getElementById('console-active');
  const consoleEmpty = document.getElementById('console-empty');

  if (globalDashboard) globalDashboard.classList.add('hidden');
  if (consoleEmpty) consoleEmpty.classList.add('hidden');
  if (consoleActive) consoleActive.classList.remove('hidden');

  updateActiveSessionView(session);
  renderTranscript(session);
}

window.getFilteredSessions = getFilteredSessions;
window.updateStats = updateStats;
window.renderSessionsList = renderSessionsList;
window.showDashboardView = showDashboardView;
window.selectSession = selectSession;
