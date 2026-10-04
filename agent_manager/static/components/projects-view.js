/**
 * projects-view.js
 * Multi-Project Portfolio View Web Component for Agent Manager.
 */
(function() {
  const _esc = (s) => (window.escapeHtml ? window.escapeHtml(s) : (s || ''));
  const _renderTable = (...a) => (window.renderProjectsTable ? window.renderProjectsTable(...a) : '');
  const _openModal = (...a) => (window.openNewProjectIssueModal ? window.openNewProjectIssueModal(...a) : null);

  class ProjectsView extends HTMLElement {
    constructor() {
      super();
      this.projects = [];
      this.globalCounts = {};
      this.activeTab = 'all';
      this.activeFilter = 'all';
      this.searchQuery = '';
      this.loading = false;
    }

    connectedCallback() {
      this.loadData();
    }

    async loadData(isSync = false) {
      this.loading = true;
      this.render();
      try {
        const endpoint = isSync ? '/api/projects/sync' : '/api/projects';
        const res = await fetch(endpoint, { method: isSync ? 'POST' : 'GET' });
        const data = await res.json();
        const payload = isSync ? data.data : data;
        this.projects = payload.projects || [];
        this.globalCounts = payload.global_counts || {};
      } catch (err) {
        console.error('Failed to load projects data:', err);
      } finally {
        this.loading = false;
        this.render();
      }
    }

    getCurrentItems() {
      if (this.activeTab === 'all') return this.projects.flatMap(p => p.items || []);
      const cur = this.projects.find(p => p.id === this.activeTab);
      return cur ? (cur.items || []) : [];
    }

    getCurrentProject() {
      return this.activeTab === 'all' ? null : this.projects.find(p => p.id === this.activeTab);
    }

    render() {
      const curProj = this.getCurrentProject();
      const isAll = this.activeTab === 'all';
      const items = this.getCurrentItems();

      this.innerHTML = `
        <div class="projects-view-container">
          <div class="pv-header">
            <div class="pv-title-group">
              <h2><span>📁</span> Project Portfolio & Multi-Project Tracker</h2>
              <p>Unified board tables and autonomous agent orchestration across connected repositories.</p>
            </div>
            <div class="pv-header-actions">
              <button class="btn btn-secondary" id="pv-btn-sync">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg>
                <span>Sync Boards</span>
              </button>
              <a href="https://github.com/users/BowenMichael/projects/3" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="text-decoration: none;">
                <span>GitHub Board #3 ↗</span>
              </a>
              <button class="btn btn-primary" id="pv-btn-new-issue">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                <span>New Issue</span>
              </button>
            </div>
          </div>

          <div class="pv-stats-grid">
            <div class="pv-stat-card"><span class="pv-stat-label">Active Projects</span><span class="pv-stat-value">${this.projects.length}</span></div>
            <div class="pv-stat-card"><span class="pv-stat-label">Total Tracked Tasks</span><span class="pv-stat-value cyan">${this.globalCounts.total_items || 0}</span></div>
            <div class="pv-stat-card"><span class="pv-stat-label">⚡ In Progress</span><span class="pv-stat-value amber">${this.globalCounts.in_progress || 0}</span></div>
            <div class="pv-stat-card"><span class="pv-stat-label">🔍 In Review</span><span class="pv-stat-value purple">${this.globalCounts.in_review || 0}</span></div>
            <div class="pv-stat-card"><span class="pv-stat-label">✅ Completed</span><span class="pv-stat-value green">${this.globalCounts.done || 0}</span></div>
          </div>

          <div class="pv-tabs-nav">
            <button class="pv-tab-btn ${isAll ? 'active' : ''}" data-tab="all">
              <span>🌟</span> All Projects <span class="pv-tab-badge">${this.globalCounts.total_items || 0}</span>
            </button>
            ${this.projects.map(p => `
              <button class="pv-tab-btn ${this.activeTab === p.id ? 'active' : ''}" data-tab="${p.id}">
                <span>${p.icon || '📁'}</span>
                <span>${_esc(p.name)}</span>
                ${p.active_agents_count > 0 ? `<span class="pv-tab-agent-dot" title="${p.active_agents_count} running agents"></span>` : ''}
                <span class="pv-tab-badge">${(p.items || []).length}</span>
              </button>
            `).join('')}
          </div>

          ${curProj ? `
            <div class="pv-meta-bar">
              <div class="pv-meta-left">
                <span style="font-weight: 700; font-size: 1rem;">${curProj.icon} ${_esc(curProj.name)}</span>
                <span class="pv-badge stack">${_esc(curProj.stack)}</span>
                <span class="pv-badge workspace" title="${_esc(curProj.local_path || 'Not found')}">
                  📁 ${_esc(curProj.local_path ? curProj.local_path.split('\\').pop() : 'Local workspace missing')}
                </span>
                <span class="pv-badge" style="color: #34d399;">🟢 Webhook Active</span>
              </div>
              <div class="pv-meta-right">
                <a href="${_esc(curProj.github_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="font-size: 0.75rem; padding: 4px 8px; text-decoration: none;">GitHub Repo ↗</a>
                <button class="btn btn-secondary btn-create-for-proj" data-repo="${_esc(curProj.repo)}" style="font-size: 0.75rem; padding: 4px 8px;">+ Add Task</button>
              </div>
            </div>
          ` : ''}

          <div class="pv-filter-strip">
            <div class="pv-search-box">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              <input type="text" id="pv-search-input" placeholder="Search tasks by title, number, or repo..." value="${_esc(this.searchQuery)}" />
            </div>
            <div class="pv-status-filters">
              <button class="pv-pill-filter ${this.activeFilter === 'all' ? 'active' : ''}" data-filter="all">All</button>
              <button class="pv-pill-filter ${this.activeFilter === 'ready' ? 'active' : ''}" data-filter="ready">📋 Ready</button>
              <button class="pv-pill-filter ${this.activeFilter === 'progress' ? 'active' : ''}" data-filter="progress">⚡ In Progress</button>
              <button class="pv-pill-filter ${this.activeFilter === 'review' ? 'active' : ''}" data-filter="review">🔍 In Review</button>
              <button class="pv-pill-filter ${this.activeFilter === 'done' ? 'active' : ''}" data-filter="done">✅ Done</button>
              <button class="pv-pill-filter ${this.activeFilter === 'backlog' ? 'active' : ''}" data-filter="backlog">📥 Backlog</button>
            </div>
          </div>

          ${this.loading ? `
            <div class="pv-empty-state"><div class="pulse-indicator" style="margin-bottom: 12px;"><span class="dot"></span> Loading live project data...</div></div>
          ` : _renderTable(items, isAll, this.activeFilter, this.searchQuery)}
        </div>
      `;

      this.attachEventListeners();
    }

    attachEventListeners() {
      this.querySelectorAll('.pv-tab-btn').forEach(btn => {
        btn.onclick = () => { this.activeTab = btn.getAttribute('data-tab'); this.render(); };
      });
      this.querySelectorAll('.pv-pill-filter').forEach(btn => {
        btn.onclick = () => { this.activeFilter = btn.getAttribute('data-filter'); this.render(); };
      });

      const searchInput = this.querySelector('#pv-search-input');
      if (searchInput) {
        searchInput.oninput = (e) => {
          this.searchQuery = e.target.value;
          const wrapper = this.querySelector('.pv-table-wrapper') || this.querySelector('.pv-empty-state');
          if (wrapper) {
            wrapper.outerHTML = _renderTable(this.getCurrentItems(), this.activeTab === 'all', this.activeFilter, this.searchQuery);
            this.attachRowEvents();
          }
        };
      }

      const syncBtn = this.querySelector('#pv-btn-sync');
      if (syncBtn) syncBtn.onclick = () => this.loadData(true);

      const newIssueBtn = this.querySelector('#pv-btn-new-issue');
      if (newIssueBtn) {
        newIssueBtn.onclick = () => {
          const defaultRepo = this.getCurrentProject()?.repo || 'BowenMichael/fit-elo';
          _openModal(defaultRepo, () => this.loadData());
        };
      }

      const createProjBtn = this.querySelector('.btn-create-for-proj');
      if (createProjBtn) {
        createProjBtn.onclick = () => {
          const repo = createProjBtn.getAttribute('data-repo');
          _openModal(repo, () => this.loadData());
        };
      }

      const emptyCreateBtn = this.querySelector('.btn-empty-create-task');
      if (emptyCreateBtn) {
        emptyCreateBtn.onclick = () => {
          const defaultRepo = this.getCurrentProject()?.repo || 'BowenMichael/fit-elo';
          _openModal(defaultRepo, () => this.loadData());
        };
      }

      this.attachRowEvents();
    }

    attachRowEvents() {
      this.querySelectorAll('.btn-jump-session').forEach(btn => {
        btn.onclick = () => {
          const sid = btn.getAttribute('data-session-id');
          if (sid && typeof window.selectSession === 'function') window.selectSession(sid);
        };
      });

      this.querySelectorAll('.btn-launch-issue-agent').forEach(btn => {
        btn.onclick = () => {
          const repo = btn.getAttribute('data-repo');
          const num = btn.getAttribute('data-number');
          const title = btn.getAttribute('data-title');
          if (typeof window.openLaunchModalWithIssue === 'function') {
            window.openLaunchModalWithIssue(repo, num, title);
          } else {
            const simBtn = document.getElementById('btn-simulate-modal');
            if (simBtn) simBtn.click();
          }
        };
      });
    }
  }

  if (!customElements.get('projects-view')) {
    customElements.define('projects-view', ProjectsView);
  }
})();
