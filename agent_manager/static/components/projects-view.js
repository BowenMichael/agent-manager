/**
 * projects-view.js
 * Multi-Project Portfolio View Web Component for Agent Manager.
 */

import { renderProjectsTable, escapeHtml } from './projects-table.js';
import { openNewProjectIssueModal } from './project-new-modal.js';

class ProjectsView extends HTMLElement {
  constructor() {
    super();
    this.projects = [];
    this.globalCounts = {};
    this.activeTab = 'all'; // 'all' or project.id
    this.activeFilter = 'all'; // 'all', 'ready', 'progress', 'review', 'done', 'backlog'
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
      const method = isSync ? 'POST' : 'GET';
      const res = await fetch(endpoint, { method });
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
    if (this.activeTab === 'all') {
      return this.projects.flatMap(p => p.items || []);
    }
    const currentProj = this.projects.find(p => p.id === this.activeTab);
    return currentProj ? (currentProj.items || []) : [];
  }

  getCurrentProject() {
    if (this.activeTab === 'all') return null;
    return this.projects.find(p => p.id === this.activeTab);
  }

  render() {
    const currentProj = this.getCurrentProject();
    const isAll = this.activeTab === 'all';
    const items = this.getCurrentItems();

    this.innerHTML = `
      <div class="projects-view-container">
        <!-- Header -->
        <div class="pv-header">
          <div class="pv-title-group">
            <h2>
              <span>📁</span> Project Portfolio & Multi-Project Tracker
            </h2>
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

        <!-- Global Stat Cards -->
        <div class="pv-stats-grid">
          <div class="pv-stat-card">
            <span class="pv-stat-label">Active Projects</span>
            <span class="pv-stat-value">${this.projects.length}</span>
          </div>
          <div class="pv-stat-card">
            <span class="pv-stat-label">Total Tracked Tasks</span>
            <span class="pv-stat-value cyan">${this.globalCounts.total_items || 0}</span>
          </div>
          <div class="pv-stat-card">
            <span class="pv-stat-label">⚡ In Progress</span>
            <span class="pv-stat-value amber">${this.globalCounts.in_progress || 0}</span>
          </div>
          <div class="pv-stat-card">
            <span class="pv-stat-label">🔍 In Review</span>
            <span class="pv-stat-value purple">${this.globalCounts.in_review || 0}</span>
          </div>
          <div class="pv-stat-card">
            <span class="pv-stat-label">✅ Completed</span>
            <span class="pv-stat-value green">${this.globalCounts.done || 0}</span>
          </div>
        </div>

        <!-- Project Selector Tabs -->
        <div class="pv-tabs-nav">
          <button class="pv-tab-btn ${isAll ? 'active' : ''}" data-tab="all">
            <span>🌟</span> All Projects
            <span class="pv-tab-badge">${this.globalCounts.total_items || 0}</span>
          </button>
          ${this.projects.map(p => `
            <button class="pv-tab-btn ${this.activeTab === p.id ? 'active' : ''}" data-tab="${p.id}">
              <span>${p.icon || '📁'}</span>
              <span>${escapeHtml(p.name)}</span>
              ${p.active_agents_count > 0 ? `<span class="pv-tab-agent-dot" title="${p.active_agents_count} running agents"></span>` : ''}
              <span class="pv-tab-badge">${(p.items || []).length}</span>
            </button>
          `).join('')}
        </div>

        <!-- Current Project Meta Bar (if single project selected) -->
        ${currentProj ? `
          <div class="pv-meta-bar">
            <div class="pv-meta-left">
              <span style="font-weight: 700; font-size: 1rem;">${currentProj.icon} ${escapeHtml(currentProj.name)}</span>
              <span class="pv-badge stack">${escapeHtml(currentProj.stack)}</span>
              <span class="pv-badge workspace" title="${escapeHtml(currentProj.local_path || 'Not found')}">
                📁 ${escapeHtml(currentProj.local_path ? currentProj.local_path.split('\\').pop() : 'Local workspace missing')}
              </span>
              <span class="pv-badge" style="color: #34d399;">🟢 Webhook Active</span>
            </div>
            <div class="pv-meta-right">
              <a href="${escapeHtml(currentProj.github_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="font-size: 0.75rem; padding: 4px 8px; text-decoration: none;">
                GitHub Repo ↗
              </a>
              <button class="btn btn-secondary btn-create-for-proj" data-repo="${escapeHtml(currentProj.repo)}" style="font-size: 0.75rem; padding: 4px 8px;">
                + Add Task
              </button>
            </div>
          </div>
        ` : ''}

        <!-- Filter & Search Strip -->
        <div class="pv-filter-strip">
          <div class="pv-search-box">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            <input type="text" id="pv-search-input" placeholder="Search tasks by title, number, or repo..." value="${escapeHtml(this.searchQuery)}" />
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

        <!-- Interactive Table -->
        ${this.loading ? `
          <div class="pv-empty-state">
            <div class="pulse-indicator" style="margin-bottom: 12px;"><span class="dot"></span> Loading live project data...</div>
          </div>
        ` : renderProjectsTable(items, isAll, this.activeFilter, this.searchQuery)}
      </div>
    `;

    this.attachEventListeners();
  }

  attachEventListeners() {
    // Project Tab switching
    this.querySelectorAll('.pv-tab-btn').forEach(btn => {
      btn.onclick = () => {
        this.activeTab = btn.getAttribute('data-tab');
        this.render();
      };
    });

    // Status filter pill switching
    this.querySelectorAll('.pv-pill-filter').forEach(btn => {
      btn.onclick = () => {
        this.activeFilter = btn.getAttribute('data-filter');
        this.render();
      };
    });

    // Search input
    const searchInput = this.querySelector('#pv-search-input');
    if (searchInput) {
      searchInput.oninput = (e) => {
        this.searchQuery = e.target.value;
        const currentProj = this.getCurrentProject();
        const items = this.getCurrentItems();
        const wrapper = this.querySelector('.pv-table-wrapper') || this.querySelector('.pv-empty-state');
        if (wrapper) {
          wrapper.outerHTML = renderProjectsTable(items, this.activeTab === 'all', this.activeFilter, this.searchQuery);
          this.attachRowEvents();
        }
      };
    }

    // Sync button
    const syncBtn = this.querySelector('#pv-btn-sync');
    if (syncBtn) {
      syncBtn.onclick = () => this.loadData(true);
    }

    // New issue button
    const newIssueBtn = this.querySelector('#pv-btn-new-issue');
    if (newIssueBtn) {
      newIssueBtn.onclick = () => {
        const defaultRepo = this.getCurrentProject()?.repo || 'BowenMichael/fit-elo';
        openNewProjectIssueModal(defaultRepo, () => this.loadData());
      };
    }

    const createProjBtn = this.querySelector('.btn-create-for-proj');
    if (createProjBtn) {
      createProjBtn.onclick = () => {
        const repo = createProjBtn.getAttribute('data-repo');
        openNewProjectIssueModal(repo, () => this.loadData());
      };
    }

    this.attachRowEvents();
  }

  attachRowEvents() {
    // Jump to session button
    this.querySelectorAll('.btn-jump-session').forEach(btn => {
      btn.onclick = () => {
        const sessionId = btn.getAttribute('data-session-id');
        if (sessionId && typeof window.selectSession === 'function') {
          window.selectSession(sessionId);
        }
      };
    });

    // Launch agent button
    this.querySelectorAll('.btn-launch-issue-agent').forEach(btn => {
      btn.onclick = () => {
        const repo = btn.getAttribute('data-repo');
        const num = btn.getAttribute('data-number');
        const title = btn.getAttribute('data-title');
        if (typeof window.openLaunchModalWithIssue === 'function') {
          window.openLaunchModalWithIssue(repo, num, title);
        } else {
          // Trigger Simulate Webhook or Launch
          const simBtn = document.getElementById('btn-simulate-modal');
          if (simBtn) simBtn.click();
        }
      };
    });
  }
}

customElements.define('projects-view', ProjectsView);
