/**
 * telemetry-view.js
 * Comprehensive Standalone Telemetry & Agent Performance Dashboard Component.
 * Adheres strictly to Anti-Monolith guidelines (< 250 lines).
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

class TelemetryView extends HTMLElement {
  constructor() {
    super();
    this.tokenData = null;
    this.reportData = null;
    this.activeTimescale = '24h';
    this.loading = false;
  }

  connectedCallback() {
    this.loadData();
  }

  async loadData() {
    this.loading = true;
    try {
      const [tokRes, repRes] = await Promise.all([
        fetch('/api/telemetry/tokens'),
        fetch('/api/telemetry/reports')
      ]);
      if (tokRes.ok) this.tokenData = await tokRes.json();
      if (repRes.ok) this.reportData = await repRes.json();
    } catch (err) {
      console.error('Failed to load telemetry data:', err);
    } finally {
      this.loading = false;
      this.render();
    }
  }

  render() {
    const s = this.tokenData?.summary || {};
    const rep = this.reportData || { summary: {}, recommendations: [], tool_usage: {}, session_performances: [] };
    const rSum = rep.summary || {};

    let windowTokens = s.last_24h_tokens || 0;
    let windowLabel = 'Tokens (Last 24h)';
    if (this.activeTimescale === '1h') { windowTokens = s.last_1h_tokens || 0; windowLabel = 'Tokens (Last 1h)'; }
    else if (this.activeTimescale === '7d') { windowTokens = s.last_7d_tokens || 0; windowLabel = 'Tokens (Last 7d)'; }
    else if (this.activeTimescale === '30d') { windowTokens = s.last_30d_tokens || 0; windowLabel = 'Tokens (Last 30d)'; }
    else if (this.activeTimescale === 'all') { windowTokens = s.all_time_tokens || 0; windowLabel = 'Tokens (All Time)'; }

    this.innerHTML = `
      <div class="telemetry-view-container">
        <div class="telemetry-header-bar">
          <div class="telemetry-title-group">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2.2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            <h2>Agent Telemetry & Optimization Reports</h2>
          </div>
          <div class="telemetry-tabs-wrapper">
            <div class="telemetry-tabs">
              <button class="tab-btn ${this.activeTimescale === '1h' ? 'active' : ''}" data-ts="1h">1h</button>
              <button class="tab-btn ${this.activeTimescale === '24h' ? 'active' : ''}" data-ts="24h">24h</button>
              <button class="tab-btn ${this.activeTimescale === '7d' ? 'active' : ''}" data-ts="7d">7d</button>
              <button class="tab-btn ${this.activeTimescale === '30d' ? 'active' : ''}" data-ts="30d">30d</button>
              <button class="tab-btn ${this.activeTimescale === 'all' ? 'active' : ''}" data-ts="all">All</button>
            </div>
            <button class="btn btn-secondary btn-refresh-telemetry" style="font-size:0.8rem; padding:6px 12px;">Refresh</button>
          </div>
        </div>

        <div class="telemetry-metrics-grid">
          <div class="telemetry-metric-card">
            <span class="telemetry-metric-label">${windowLabel}</span>
            <span class="telemetry-metric-val" style="color:var(--accent-cyan);">${windowTokens.toLocaleString()}</span>
          </div>
          <div class="telemetry-metric-card">
            <span class="telemetry-metric-label">Success Rate</span>
            <span class="telemetry-metric-val" style="color:#10b981;">${rSum.success_rate_percent || 0}%</span>
          </div>
          <div class="telemetry-metric-card">
            <span class="telemetry-metric-label">Avg Duration</span>
            <span class="telemetry-metric-val">${rSum.avg_duration_seconds || 0}s</span>
          </div>
          <div class="telemetry-metric-card">
            <span class="telemetry-metric-label">Avg Turns / Task</span>
            <span class="telemetry-metric-val">${rSum.avg_turn_count || 0}</span>
          </div>
          <div class="telemetry-metric-card">
            <span class="telemetry-metric-label">Total Tracked Tasks</span>
            <span class="telemetry-metric-val">${rSum.total_sessions || 0}</span>
          </div>
        </div>

        <div class="telemetry-panels-grid">
          <div class="telemetry-card">
            <div class="telemetry-card-title">Token Consumption Trend</div>
            <div id="telemetry-bars-box" style="display:flex; align-items:flex-end; gap:4px; height:110px; padding-top:8px; border-bottom:1px solid var(--border-color); overflow-x:auto;">
              ${this.renderBars()}
            </div>
          </div>
          <div class="telemetry-card">
            <div class="telemetry-card-title">Tool Usage Frequency</div>
            <div style="display:flex; flex-direction:column; gap:8px; max-height:160px; overflow-y:auto;">
              ${this.renderToolUsage(rep.tool_usage)}
            </div>
          </div>
        </div>

        <div class="telemetry-panels-grid">
          <div class="telemetry-card">
            <div class="telemetry-card-title">Actionable Optimization Insights (${(rep.recommendations || []).length})</div>
            <div style="display:flex; flex-direction:column; gap:8px; max-height:240px; overflow-y:auto;">
              ${this.renderRecommendations(rep.recommendations)}
            </div>
          </div>
          <div class="telemetry-card">
            <div class="telemetry-card-title">Recent Task Performance</div>
            <div style="overflow-x:auto; max-height:240px;">
              ${this.renderPerfTable(rep.session_performances)}
            </div>
          </div>
        </div>
      </div>
    `;

    this.bindEvents();
  }

  renderBars() {
    if (!this.tokenData) return '<div style="font-size:0.8rem; color:var(--text-dim);">No token data available.</div>';
    const isHourly = this.activeTimescale === '1h' || this.activeTimescale === '24h';
    const items = isHourly
      ? (this.tokenData.hourly_trend || []).map(i => ({ label: i.hour ? i.hour.split(' ')[1] : '', full: i.hour, toks: i.tokens || 0 }))
      : (this.tokenData.daily_trend || []).slice(this.activeTimescale === '7d' ? -7 : -30).map(i => ({ label: i.date ? i.date.slice(5) : '', full: i.date, toks: i.tokens || 0 }));
    const maxToks = Math.max(...items.map(i => i.toks), 100);

    return items.map(item => `
      <div class="telemetry-bar-col" title="${escapeHtml(item.full)}: ${item.toks.toLocaleString()} tokens">
        <div class="telemetry-bar-fill" style="height:${Math.max(3, Math.round((item.toks / maxToks) * 100))}%;"></div>
        <div style="font-size:0.65rem; color:var(--text-dim); margin-top:4px; text-align:center;">${escapeHtml(item.label)}</div>
      </div>
    `).join('');
  }

  renderToolUsage(toolUsage) {
    const entries = Object.entries(toolUsage || {});
    if (!entries.length) return '<div style="font-size:0.8rem; color:var(--text-dim);">No tool execution metrics logged yet.</div>';
    const maxCount = Math.max(...entries.map(e => e[1]), 1);
    return entries.map(([tool, count]) => `
      <div class="breakdown-row">
        <div class="breakdown-header" style="display:flex; justify-content:space-between; font-size:0.8rem;">
          <span style="font-weight:500; font-family:'JetBrains Mono',monospace;">${escapeHtml(tool)}</span>
          <span style="color:var(--text-secondary);">${count} calls</span>
        </div>
        <div class="breakdown-track" style="height:6px; background:rgba(255,255,255,0.06); border-radius:3px; overflow:hidden;">
          <div style="height:100%; width:${Math.round((count / maxCount) * 100)}%; background:var(--accent-cyan); border-radius:3px;"></div>
        </div>
      </div>
    `).join('');
  }

  renderRecommendations(recs) {
    if (!recs || !recs.length) return '<div style="font-size:0.8rem; color:var(--text-dim); padding:10px;">✅ All agent executions operating smoothly within budget thresholds.</div>';
    return recs.map(r => `
      <div class="optimization-alert-item severity-${escapeHtml(r.severity)}">
        <div style="font-weight:600; font-size:0.85rem; color:var(--text-primary); display:flex; justify-content:space-between;">
          <span>${escapeHtml(r.title)}</span>
          <span style="font-size:0.7rem; text-transform:uppercase; font-weight:700;">${escapeHtml(r.severity)}</span>
        </div>
        <div style="font-size:0.78rem; color:var(--text-secondary);">${escapeHtml(r.detail)}</div>
        <div style="font-size:0.75rem; color:var(--accent-cyan); font-weight:500;">💡 Suggestion: ${escapeHtml(r.action)}</div>
      </div>
    `).join('');
  }

  renderPerfTable(sessions) {
    if (!sessions || !sessions.length) return '<div style="font-size:0.8rem; color:var(--text-dim);">No task runs recorded.</div>';
    return `
      <table class="telemetry-perf-table">
        <thead>
          <tr>
            <th>Task</th>
            <th>Status</th>
            <th>Duration</th>
            <th>Turns</th>
            <th>Tokens</th>
          </tr>
        </thead>
        <tbody>
          ${sessions.map(s => `
            <tr>
              <td><strong>${escapeHtml(s.repo)}#${s.issue_number || '?'}</strong> <span style="font-size:0.7rem; color:var(--text-dim);">${escapeHtml(s.title || '')}</span></td>
              <td><span style="font-size:0.72rem; padding:2px 6px; border-radius:4px; background:${s.status === 'COMPLETED' ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)'}; color:${s.status === 'COMPLETED' ? '#10b981' : '#f87171'}; font-weight:600;">${escapeHtml(s.status)}</span></td>
              <td>${s.duration_seconds}s</td>
              <td>${s.turn_count}</td>
              <td>${(s.total_tokens || 0).toLocaleString()}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  bindEvents() {
    this.querySelectorAll('.telemetry-tabs .tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this.activeTimescale = btn.getAttribute('data-ts') || '24h';
        this.render();
      });
    });
    const refBtn = this.querySelector('.btn-refresh-telemetry');
    if (refBtn) refBtn.addEventListener('click', () => this.loadData());
  }
}

customElements.define('telemetry-view', TelemetryView);
window.TelemetryView = TelemetryView;
})();
