class GitTreeViewer extends HTMLElement {
  constructor() {
    super();
    this._sessionId = null;
    this._loading = false;
  }

  static get observedAttributes() {
    return ['session-id'];
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (name === 'session-id' && oldValue !== newValue) {
      this._sessionId = newValue;
      this.loadGitTree();
    }
  }

  connectedCallback() {
    this.renderSkeleton();
    if (this.getAttribute('session-id')) {
      this._sessionId = this.getAttribute('session-id');
      this.loadGitTree();
    }
  }

  renderSkeleton() {
    this.innerHTML = `
      <div class="git-tree-container">
        <div class="git-tree-header">
          <h4>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="6" y1="3" x2="6" y2="15"></line>
              <circle cx="18" cy="6" r="3"></circle>
              <circle cx="6" cy="18" r="3"></circle>
              <path d="M18 9a9 9 0 0 1-9 9"></path>
            </svg>
            Git Topology Tree
            <span class="git-tree-branch-badge" id="git-tree-branch">loading...</span>
          </h4>
          <button class="git-tree-refresh-btn" id="btn-refresh-git-tree" title="Refresh Git Tree">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
            </svg>
            Refresh
          </button>
        </div>
        <div class="git-tree-body" id="git-tree-content">
          <div class="git-tree-empty">Loading Git branch topology...</div>
        </div>
      </div>
    `;

    const refreshBtn = this.querySelector('#btn-refresh-git-tree');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.loadGitTree());
    }
  }

  async loadGitTree() {
    if (!this._sessionId) return;
    const contentEl = this.querySelector('#git-tree-content');
    const branchBadge = this.querySelector('#git-tree-branch');
    if (!contentEl) return;

    contentEl.innerHTML = `<div class="git-tree-empty">Loading Git branch topology...</div>`;

    try {
      const resp = await fetch(`/api/agents/${encodeURIComponent(this._sessionId)}/git-tree`);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const data = await resp.json();

      if (branchBadge) {
        branchBadge.textContent = data.branch || 'detached';
      }

      if (!data.git_tree || data.git_tree.trim() === '') {
        contentEl.innerHTML = `<div class="git-tree-empty">No git commits found in this worktree.</div>`;
        return;
      }

      contentEl.innerHTML = `<pre class="git-tree-pre">${this.escapeHtml(data.git_tree)}</pre>`;
    } catch (err) {
      contentEl.innerHTML = `<div class="git-tree-empty" style="color: var(--accent-red, #f87171);">Failed to load git topology: ${this.escapeHtml(err.message)}</div>`;
    }
  }

  escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
}

customElements.define('git-tree-viewer', GitTreeViewer);
