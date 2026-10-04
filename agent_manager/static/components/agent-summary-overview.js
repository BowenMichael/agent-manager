/**
 * agent-summary-overview.js
 * Multi-agent live dashboard component rendering at-a-glance summaries for all active sessions.
 */

class AgentSummaryOverview extends HTMLElement {
  constructor() {
    super();
    this._sessions = [];
  }

  connectedCallback() {
    this.render();
  }

  set sessions(data) {
    this._sessions = Array.isArray(data) ? data : [];
    this.render();
  }

  get sessions() {
    return this._sessions;
  }

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  formatDuration(seconds) {
    if (!seconds || seconds <= 0) return '0s';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  render() {
    const activeSessions = this._sessions.filter(s => !s.is_archived);

    this.innerHTML = `
      <div class="agent-summary-container">
        <div class="agent-summary-header">
          <h2>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="7" height="7"></rect>
              <rect x="14" y="3" width="7" height="7"></rect>
              <rect x="14" y="14" width="7" height="7"></rect>
              <rect x="3" y="14" width="7" height="7"></rect>
            </svg>
            Active Agents Live Dashboard
          </h2>
          <span class="summary-count-badge">${activeSessions.length} Running / Active</span>
        </div>

        ${activeSessions.length === 0 ? `
          <div class="summary-empty-state">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: 12px; opacity: 0.5;">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <p>No active agent sessions found.</p>
            <small>Dispatch an issue from the Project Board or launch an agent to view real-time status.</small>
          </div>
        ` : `
          <div class="agent-summary-grid">
            ${activeSessions.map(session => this.renderCard(session)).join('')}
          </div>
        `}
      </div>
    `;

    this.querySelectorAll('.summary-card').forEach(card => {
      card.addEventListener('click', () => {
        const sessionId = card.getAttribute('data-session-id');
        if (sessionId) {
          if (typeof window.selectSession === 'function') {
            window.selectSession(sessionId);
          } else {
            this.dispatchEvent(new CustomEvent('session-selected', { detail: { sessionId }, bubbles: true }));
          }
        }
      });
    });
  }

  renderCard(s) {
    const isStalled = s.is_stalled;
    const status = s.status || 'UNKNOWN';
    const statusClass = `tag-${status.toLowerCase()}`;
    const quotaPct = Math.min(100, Math.round(s.quota_percent || 0));
    let fillClass = '';
    if (quotaPct >= 80) fillClass = 'fill-danger';
    else if (quotaPct >= 50) fillClass = 'fill-warn';

    const stage = s.workflow_stage || 'DIRECT';
    const turnCount = s.turn_count || 0;
    const maxTurns = s.max_turns || 15;
    const duration = this.formatDuration(s.duration_seconds);
    const activity = s.current_activity || 'IDLE';

    return `
      <div class="summary-card ${isStalled ? 'stalled' : ''}" data-session-id="${this.escapeHtml(s.session_id)}">
        <div class="summary-card-header">
          <div class="summary-card-title-area">
            <div class="summary-card-id">#${s.issue_number || 'ADHOC'} • ${this.escapeHtml(s.repo || 'unknown')}</div>
            <div class="summary-card-title" title="${this.escapeHtml(s.title || '')}">${this.escapeHtml(s.title || 'Untitled Session')}</div>
          </div>
          <div class="summary-card-badges">
            <span class="status-tag ${statusClass}">${this.escapeHtml(status)}</span>
            ${isStalled ? '<span class="status-tag tag-paused" style="background:rgba(239,68,68,0.2);color:#f87171;">STALLED</span>' : ''}
          </div>
        </div>

        <div class="summary-activity-box">
          <div class="summary-activity-label">
            <span class="summary-pulse ${isStalled ? 'pulse-red' : ''}"></span>
            Current Activity [Stage: ${this.escapeHtml(stage)}]
          </div>
          <div class="summary-activity-text" title="${this.escapeHtml(activity)}">
            ${this.escapeHtml(activity)}
          </div>
        </div>

        <div class="summary-meta-grid">
          <div class="summary-meta-item">
            <span class="label">Turns</span>
            <span class="val">${turnCount} / ${maxTurns}</span>
          </div>
          <div class="summary-meta-item">
            <span class="label">Duration</span>
            <span class="val">${duration}</span>
          </div>
          <div class="summary-meta-item">
            <span class="label">Tokens</span>
            <span class="val">${(s.total_tokens || s.token_count || 0).toLocaleString()}</span>
          </div>
        </div>

        <div class="summary-progress-wrapper">
          <div class="summary-progress-header">
            <span>Session Budget Quota</span>
            <span>${quotaPct}%</span>
          </div>
          <div class="summary-progress-bar">
            <div class="summary-progress-fill ${fillClass}" style="width: ${quotaPct}%;"></div>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('agent-summary-overview', AgentSummaryOverview);
