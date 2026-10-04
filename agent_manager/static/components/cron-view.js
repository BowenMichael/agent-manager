/**
 * cron-view.js
 * Autonomous Cron Dispatcher Execution & History Monitor Component.
 */
(function() {
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatTime(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + 
           ' (' + d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ')';
  } catch (e) {
    return isoStr;
  }
}

class CronView extends HTMLElement {
  constructor() {
    super();
    this.cronData = {
      is_running: false,
      last_run_at: null,
      next_run_at: null,
      history: []
    };
    this.loading = false;
    this.dispatching = false;
  }

  connectedCallback() {
    this.loadData();
  }

  async loadData() {
    this.loading = true;
    try {
      const res = await fetch('/api/cron/status');
      if (res.ok) {
        this.cronData = await res.json();
      }
    } catch (err) {
      console.error('Failed to load cron status:', err);
    } finally {
      this.loading = false;
      this.render();
    }
  }

  async triggerDispatch() {
    if (this.dispatching) return;
    this.dispatching = true;
    this.render();
    try {
      const res = await fetch('/api/cron/dispatch-now', { method: 'POST' });
      const data = await res.json();
      if (typeof window.showQuotaToast === 'function') {
        window.showQuotaToast(data.message || 'Cron cycle dispatched.');
      }
      await this.loadData();
    } catch (err) {
      alert('Error triggering cron dispatch: ' + err.message);
    } finally {
      this.dispatching = false;
      this.render();
    }
  }

  render() {
    const { is_running, last_run_at, next_run_at, history = [] } = this.cronData;
    const runs = [...history].reverse();

    this.innerHTML = `
      <div class="cron-view-container">
        <!-- Header -->
        <div class="cv-header">
          <div class="cv-title-group">
            <h2>
              <span>⏱️</span> Autonomous Cron Dispatcher & Run History
            </h2>
            <p>10-minute backlog promotion scheduler, agent concurrency guards, and self-update cycle.</p>
          </div>
          <div class="cv-header-actions">
            <button class="btn btn-secondary" id="cv-btn-refresh" ${this.loading ? 'disabled' : ''}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg>
              <span>${this.loading ? 'Refreshing...' : 'Refresh Status'}</span>
            </button>
            <button class="btn btn-primary" id="cv-btn-dispatch" ${this.dispatching ? 'disabled' : ''} style="display: flex; align-items: center; gap: 6px;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
              <span>${this.dispatching ? 'Dispatching Cycle...' : 'Run Dispatch Now'}</span>
            </button>
          </div>
        </div>

        <!-- Metrics Cards -->
        <div class="cv-stats-grid">
          <div class="cv-stat-card">
            <span class="cv-stat-label">Scheduler Status</span>
            <span class="cv-stat-value ${is_running ? 'green' : 'amber'}">
              ${is_running ? '🟢 Active (10m loop)' : '⏸️ Paused'}
            </span>
          </div>
          <div class="cv-stat-card">
            <span class="cv-stat-label">Last Execution</span>
            <span class="cv-stat-value cyan" style="font-size: 0.95rem;">${formatTime(last_run_at)}</span>
          </div>
          <div class="cv-stat-card">
            <span class="cv-stat-label">Next Scheduled Run</span>
            <span class="cv-stat-value purple" style="font-size: 0.95rem;">${formatTime(next_run_at)}</span>
          </div>
          <div class="cv-stat-card">
            <span class="cv-stat-label">Recorded Runs</span>
            <span class="cv-stat-value">${history.length}</span>
          </div>
        </div>

        <!-- Run History Table -->
        <div class="cv-table-wrapper">
          <table class="cv-table">
            <thead>
              <tr>
                <th style="width: 170px;">Execution Time</th>
                <th style="width: 130px;">Outcome</th>
                <th>Result & Details</th>
                <th style="width: 140px;">Backlog Count</th>
              </tr>
            </thead>
            <tbody>
              ${runs.length === 0 ? `
                <tr><td colspan="4" class="cv-empty">No cron runs recorded in memory yet.</td></tr>
              ` : runs.map(run => {
                const isDispatched = run.status === 'dispatched';
                const isSkipped = run.status === 'active_issue_present';
                const badgeClass = isDispatched ? 'dispatched' : isSkipped ? 'skipped' : 'idle';
                const badgeText = isDispatched ? '🚀 Dispatched' : isSkipped ? '⚡ Active Agent Skipped' : '📥 Backlog Empty';

                return `
                  <tr>
                    <td style="font-family: monospace; font-size: 0.76rem; color: var(--text-muted);">
                      ${formatTime(run.timestamp)}
                    </td>
                    <td>
                      <span class="cv-badge ${badgeClass}">${badgeText}</span>
                    </td>
                    <td>
                      <div style="display: flex; flex-direction: column; gap: 4px;">
                        <span style="font-weight: 500; font-size: 0.8rem; color: #f1f5f9;">
                          ${escapeHtml(run.message || '')}
                        </span>
                        ${run.promoted_issue ? `
                          <div style="font-size: 0.75rem; color: #38bdf8; display: flex; align-items: center; gap: 6px;">
                            <span>${run.promoted_issue.repo} #${run.promoted_issue.issue_number}</span>
                            <span style="color: var(--text-muted);">&bull;</span>
                            <span style="color: #cbd5e1;">${escapeHtml(run.promoted_issue.title || '')}</span>
                          </div>
                        ` : ''}
                      </div>
                    </td>
                    <td style="font-family: monospace; font-size: 0.78rem;">
                      ${run.remaining_backlog_count !== undefined ? run.remaining_backlog_count : (run.backlog_count !== undefined ? run.backlog_count : '—')} remaining
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;

    this.attachEventListeners();
  }

  attachEventListeners() {
    const refreshBtn = this.querySelector('#cv-btn-refresh');
    if (refreshBtn) {
      refreshBtn.onclick = () => this.loadData();
    }

    const dispatchBtn = this.querySelector('#cv-btn-dispatch');
    if (dispatchBtn) {
      dispatchBtn.onclick = () => this.triggerDispatch();
    }
  }
}

if (!customElements.get('cron-view')) {
  customElements.define('cron-view', CronView);
}
})();
