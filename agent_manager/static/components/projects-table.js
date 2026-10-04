/**
 * projects-table.js
 * Modular table row and column renderer for the Projects View.
 */
(function() {
function getStatusClass(statusStr) {
  const s = String(statusStr || '').toLowerCase();
  if (s.includes('ready')) return 'pv-tag-ready';
  if (s.includes('progress')) return 'pv-tag-progress';
  if (s.includes('review')) return 'pv-tag-review';
  if (s.includes('done')) return 'pv-tag-done';
  return 'pv-tag-backlog';
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function renderAgentCell(item) {
  const sess = item.active_session;
  if (!sess) {
    return `<span style="color: var(--text-muted); font-size: 0.78rem;">Idle</span>`;
  }

  const isRunning = sess.status === 'RUNNING';
  const tagColor = isRunning ? '#10b981' : '#94a3b8';
  const dotHtml = isRunning ? `<span class="pv-tab-agent-dot"></span>` : '';
  const quotaPct = Math.round(sess.quota_percent || 0);

  return `
    <div style="display: flex; flex-direction: column; gap: 4px;">
      <div style="display: flex; align-items: center; gap: 6px;">
        ${dotHtml}
        <span style="font-weight: 600; font-size: 0.78rem; color: ${tagColor};">${escapeHtml(sess.status)}</span>
        <button class="btn btn-secondary btn-jump-session" data-session-id="${escapeHtml(sess.session_id)}" style="padding: 2px 6px; font-size: 0.7rem; height: auto;">Console ↗</button>
      </div>
      <div style="font-size: 0.72rem; color: var(--text-muted); font-family: monospace;">
        ${escapeHtml(sess.model || 'gemini-3.8-flash')} • Turn ${sess.turn_count || 0}/15
      </div>
    </div>
  `;
}

function renderWorktreeCell(item) {
  const sess = item.active_session;
  const branch = sess?.branch || `feat/issue-${item.number}`;
  const hasWt = item.has_local_worktree;

  return `
    <div style="display: flex; flex-direction: column; gap: 3px; font-family: monospace; font-size: 0.75rem;">
      <span style="color: var(--accent-cyan);">${escapeHtml(branch)}</span>
      <span style="color: ${hasWt ? '#34d399' : 'var(--text-muted)'}; font-size: 0.7rem;">
        ${hasWt ? '📁 .worktrees/issue-' + item.number : '—'}
      </span>
    </div>
  `;
}

function renderPrCell(item) {
  const sess = item.active_session;
  const prUrl = sess?.pr_url;
  const prNum = sess?.pr_number;

  if (prUrl) {
    return `
      <a href="${escapeHtml(prUrl)}" target="_blank" rel="noopener noreferrer" style="color: #c084fc; text-decoration: none; font-weight: 600; font-size: 0.78rem; display: flex; align-items: center; gap: 4px;">
        PR #${prNum || 'Link'} ↗
      </a>
    `;
  }
  return `<span style="color: var(--text-muted); font-size: 0.78rem;">—</span>`;
}

function renderTableRow(item, isAllProjectsView) {
  const statusCls = getStatusClass(item.status);
  const repoName = item.repo.split('/')[1] || item.repo;

  return `
    <tr data-repo="${escapeHtml(item.repo)}" data-number="${item.number}">
      ${isAllProjectsView ? `
        <td>
          <span class="pv-badge" style="font-weight: 600; font-size: 0.75rem;">
            ${escapeHtml(repoName)}
          </span>
        </td>
      ` : ''}
      <td>
        <div style="display: flex; flex-direction: column; gap: 3px;">
          <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" style="color: var(--text-primary); text-decoration: none; font-weight: 600; font-size: 0.85rem;">
            #${item.number}: ${escapeHtml(item.title)}
          </a>
        </div>
      </td>
      <td>
        <span class="pv-tag ${statusCls}">${escapeHtml(item.status)}</span>
      </td>
      <td>
        ${renderAgentCell(item)}
      </td>
      <td>
        ${renderWorktreeCell(item)}
      </td>
      <td>
        ${renderPrCell(item)}
      </td>
      <td>
        <div style="display: flex; gap: 6px; align-items: center;">
          <button class="btn btn-secondary btn-launch-issue-agent" data-repo="${escapeHtml(item.repo)}" data-number="${item.number}" data-title="${escapeHtml(item.title)}" title="Launch or Resume Agent" style="padding: 3px 8px; font-size: 0.75rem;">
            ⚡ Launch
          </button>
          <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" title="Open on GitHub" style="padding: 3px 6px; font-size: 0.75rem; text-decoration: none;">
            ↗
          </a>
        </div>
      </td>
    </tr>
  `;
}

function renderProjectsTable(items, isAllProjectsView, activeFilter, searchQuery) {
  let filtered = [...items];

  if (activeFilter && activeFilter !== 'all') {
    filtered = filtered.filter(i => {
      const s = String(i.status || '').toLowerCase();
      if (activeFilter === 'ready') return s.includes('ready');
      if (activeFilter === 'progress') return s.includes('progress');
      if (activeFilter === 'review') return s.includes('review');
      if (activeFilter === 'done') return s.includes('done');
      if (activeFilter === 'backlog') return s.includes('backlog');
      return true;
    });
  }

  if (searchQuery && searchQuery.trim()) {
    const q = searchQuery.toLowerCase().trim();
    filtered = filtered.filter(i => 
      String(i.number).includes(q) ||
      (i.title && i.title.toLowerCase().includes(q)) ||
      (i.repo && i.repo.toLowerCase().includes(q))
    );
  }

  if (filtered.length === 0) {
    return `
      <div class="pv-empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity: 0.5; margin-bottom: 12px;">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <p style="margin: 0 0 6px 0; font-weight: 600;">No tasks found matching criteria.</p>
        <small style="color: var(--text-muted); display: block; margin-bottom: 12px;">Create a new issue to dispatch an agent or add a task to this project backlog.</small>
        <button class="btn btn-primary btn-empty-create-task" style="font-size: 0.8rem; padding: 6px 14px; margin: 0 auto; display: inline-flex; align-items: center; gap: 6px;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          <span>+ Create Issue in Project</span>
        </button>
      </div>
    `;
  }

  return `
    <div class="pv-table-wrapper">
      <table class="pv-table">
        <thead>
          <tr>
            ${isAllProjectsView ? '<th style="width: 140px;">Project</th>' : ''}
            <th>Issue / Task</th>
            <th style="width: 150px;">Status</th>
            <th style="width: 180px;">Agent Execution</th>
            <th style="width: 160px;">Worktree / Branch</th>
            <th style="width: 100px;">PR</th>
            <th style="width: 110px;">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${filtered.map(item => renderTableRow(item, isAllProjectsView)).join('')}
        </tbody>
      </table>
    </div>
  `;
}

window.getStatusClass = getStatusClass;
window.escapeHtml = escapeHtml;
window.renderProjectsTable = renderProjectsTable;
window.renderTableRow = renderTableRow;
window.renderAgentCell = renderAgentCell;
window.renderWorktreeCell = renderWorktreeCell;
window.renderPrCell = renderPrCell;
})();
