// agent_manager/static/modules/actions.js
// Handles user action triggers (stop, interrupt, sync, restart, terminal, done, compact, archive)

async function archiveAgent(sessionId) {
  if (!sessionId) return;
  try {
    await safeFetchJson(`/api/agents/${sessionId}/archive`, { method: 'POST' });
    const s = window.sessions.find(item => item.session_id === sessionId);
    if (s) {
      s.is_archived = true;
      if (s.status === 'RUNNING' || s.status === 'INITIALIZING') s.status = 'STOPPED';
    }
    renderSessionsList();
    updateStats();
    if (window.activeSessionId === sessionId) updateActiveSessionView(s);
    showToast('Agent session archived successfully.');
  } catch (err) {
    alert('Error archiving agent: ' + extractErrorMessage(err));
  }
}

async function unarchiveAgent(sessionId) {
  if (!sessionId) return;
  try {
    await safeFetchJson(`/api/agents/${sessionId}/unarchive`, { method: 'POST' });
    const s = window.sessions.find(item => item.session_id === sessionId);
    if (s) {
      s.is_archived = false;
      s.archived_at = null;
    }
    renderSessionsList();
    updateStats();
    if (window.activeSessionId === sessionId) updateActiveSessionView(s);
    showToast('Agent session restored to active list.');
  } catch (err) {
    alert('Error unarchiving agent: ' + extractErrorMessage(err));
  }
}

function initActionButtons() {
  const btnCopyWebhook = document.getElementById('btn-copy-webhook');
  const webhookUrlDisplay = document.getElementById('webhook-url-display');
  if (btnCopyWebhook && webhookUrlDisplay) {
    webhookUrlDisplay.textContent = `${window.location.origin}/api/webhooks/github`;
    btnCopyWebhook.addEventListener('click', () => {
      navigator.clipboard.writeText(webhookUrlDisplay.textContent);
      btnCopyWebhook.textContent = 'Copied!';
      setTimeout(() => btnCopyWebhook.textContent = 'Copy', 2000);
    });
  }

  const btnSendContext = document.getElementById('btn-send-context');
  const contextInput = document.getElementById('context-input');
  if (btnSendContext) btnSendContext.addEventListener('click', sendContext);
  if (contextInput) {
    contextInput.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        sendContext();
      }
    });
  }

  const btnStopCurrent = document.getElementById('btn-stop-current');
  if (btnStopCurrent) {
    btnStopCurrent.addEventListener('click', async () => {
      if (!window.activeSessionId) return;
      if (!confirm('Are you sure you want to stop this agent? Execution will halt immediately.')) return;
      btnStopCurrent.disabled = true;
      btnStopCurrent.textContent = 'Stopping...';
      try {
        await safeFetchJson(`/api/agents/${window.activeSessionId}/stop`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: 'Stopped manually from UI Control Plane' })
        });
      } catch (err) {
        alert('Failed to stop agent: ' + extractErrorMessage(err));
      } finally {
        btnStopCurrent.textContent = 'Stop Agent';
      }
    });
  }

  const btnInterrupt = document.getElementById('btn-interrupt');
  if (btnInterrupt) {
    btnInterrupt.addEventListener('click', async () => {
      if (!window.activeSessionId) return;
      btnInterrupt.disabled = true;
      btnInterrupt.textContent = 'Interrupting...';
      try {
        await safeFetchJson(`/api/agents/${window.activeSessionId}/interrupt`, { method: 'POST' });
      } catch (err) {
        alert('Error interrupting agent: ' + extractErrorMessage(err));
      } finally {
        btnInterrupt.disabled = false;
        btnInterrupt.textContent = 'Interrupt & Re-prompt';
      }
    });
  }

  const btnSyncBoard = document.getElementById('btn-sync-board');
  if (btnSyncBoard) {
    btnSyncBoard.addEventListener('click', async () => {
      btnSyncBoard.classList.add('spinning');
      try {
        await safeFetchJson('/api/board/sync', { method: 'POST' });
        window.sessions = await safeFetchJson('/api/agents') || [];
        renderSessionsList();
        updateStats();
      } catch (e) {
        console.error('Board sync error:', e);
      } finally {
        setTimeout(() => btnSyncBoard.classList.remove('spinning'), 600);
      }
    });
  }

  const btnRestartCurrent = document.getElementById('btn-restart-current');
  if (btnRestartCurrent) {
    btnRestartCurrent.addEventListener('click', async () => {
      if (!window.activeSessionId) return;
      if (!confirm('Are you sure you want to refresh & restart this agent session?')) return;
      btnRestartCurrent.disabled = true;
      btnRestartCurrent.textContent = 'Restarting...';
      try {
        const updated = await safeFetchJson(`/api/agents/${window.activeSessionId}/restart`, { method: 'POST' });
        const idx = window.sessions.findIndex(s => s.session_id === updated.session_id);
        if (idx !== -1) window.sessions[idx] = updated;
        selectSession(updated.session_id);
      } catch (err) {
        alert('Error restarting agent: ' + extractErrorMessage(err));
      } finally {
        btnRestartCurrent.disabled = false;
        btnRestartCurrent.textContent = 'Restart Agent';
      }
    });
  }

  const btnOpenTerminal = document.getElementById('btn-open-terminal');
  if (btnOpenTerminal) {
    btnOpenTerminal.addEventListener('click', async () => {
      if (!window.activeSessionId) return;
      try {
        btnOpenTerminal.disabled = true;
        btnOpenTerminal.textContent = 'Launching...';
        await safeFetchJson(`/api/agents/${window.activeSessionId}/launch-terminal`, { method: 'POST' });
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

  const btnDoneCurrent = document.getElementById('btn-done-current');
  if (btnDoneCurrent) {
    btnDoneCurrent.addEventListener('click', async () => {
      if (!window.activeSessionId) return;
      const s = window.sessions.find(item => item.session_id === window.activeSessionId);
      const label = s && s.issue_number ? `Issue #${s.issue_number}` : 'this agent task';
      if (!confirm(`Move ${label} to 'Done' on the GitHub Project Board and complete this session?`)) return;
      btnDoneCurrent.disabled = true;
      btnDoneCurrent.textContent = 'Completing...';
      try {
        await safeFetchJson(`/api/agents/${window.activeSessionId}/complete`, { method: 'POST' });
      } catch (err) {
        alert('Error completing agent: ' + extractErrorMessage(err));
      } finally {
        btnDoneCurrent.disabled = false;
        btnDoneCurrent.textContent = 'Mark Done';
      }
    });
  }

  const filterTabs = document.querySelectorAll('.filter-tab');
  filterTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      filterTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      window.currentFilter = tab.dataset.filter || 'active';
      const sidebarTitle = document.getElementById('sidebar-title');
      if (sidebarTitle) {
        if (window.currentFilter === 'archived') sidebarTitle.textContent = 'Archived Sessions';
        else if (window.currentFilter === 'all') sidebarTitle.textContent = 'All Sessions';
        else sidebarTitle.textContent = 'Active Sessions';
      }
      renderSessionsList();
      updateStats();
    });
  });

  const btnArchiveCurrent = document.getElementById('btn-archive-current');
  if (btnArchiveCurrent) {
    btnArchiveCurrent.addEventListener('click', async () => {
      if (!window.activeSessionId) return;
      if (!confirm('Archive this agent session? It will be hidden from the active list.')) return;
      await archiveAgent(window.activeSessionId);
    });
  }

  const btnUnarchiveCurrent = document.getElementById('btnUnarchiveCurrent');
  if (btnUnarchiveCurrent) {
    btnUnarchiveCurrent.addEventListener('click', async () => {
      if (!window.activeSessionId) return;
      await unarchiveAgent(window.activeSessionId);
    });
  }

  const btnCompactCurrent = document.getElementById('btn-compact-current');
  if (btnCompactCurrent) {
    btnCompactCurrent.addEventListener('click', async () => {
      if (!window.activeSessionId) return;
      btnCompactCurrent.disabled = true;
      btnCompactCurrent.textContent = 'Compacting...';
      try {
        await safeFetchJson(`/api/agents/${window.activeSessionId}/compact`, { method: 'POST' });
        showToast('Chat compacted and compressed successfully!');
      } catch (err) {
        alert('Error compacting chat: ' + extractErrorMessage(err));
      } finally {
        btnCompactCurrent.disabled = false;
        btnCompactCurrent.textContent = 'Compact Chat';
      }
    });
  }

  const btnShowDashboard = document.getElementById('btn-show-dashboard');
  if (btnShowDashboard) {
    btnShowDashboard.addEventListener('click', (e) => {
      e.preventDefault();
      if (typeof window.showDashboardView === 'function') window.showDashboardView();
    });
  }

  const btnShowProjects = document.getElementById('btn-show-projects');
  if (btnShowProjects) {
    btnShowProjects.addEventListener('click', (e) => {
      e.preventDefault();
      if (typeof window.showProjectsView === 'function') window.showProjectsView();
    });
  }

  const btnHeaderProjects = document.getElementById('btn-header-projects');
  if (btnHeaderProjects) {
    btnHeaderProjects.addEventListener('click', (e) => {
      e.preventDefault();
      if (typeof window.showProjectsView === 'function') window.showProjectsView();
    });
  }

  const btnHeaderCron = document.getElementById('btn-header-cron');
  if (btnHeaderCron) {
    btnHeaderCron.addEventListener('click', (e) => {
      e.preventDefault();
      if (typeof window.showCronView === 'function') window.showCronView();
    });
  }

  const btnHeaderTelemetry = document.getElementById('btn-header-telemetry');
  if (btnHeaderTelemetry) {
    btnHeaderTelemetry.addEventListener('click', (e) => {
      e.preventDefault();
      if (typeof window.showTelemetryView === 'function') window.showTelemetryView();
    });
  }

  const statPillTokens = document.getElementById('stat-pill-tokens');
  if (statPillTokens) {
    statPillTokens.addEventListener('click', (e) => {
      e.preventDefault();
      if (typeof window.showTelemetryView === 'function') window.showTelemetryView();
    });
  }
}

window.archiveAgent = archiveAgent;
window.unarchiveAgent = unarchiveAgent;
window.initActionButtons = initActionButtons;
