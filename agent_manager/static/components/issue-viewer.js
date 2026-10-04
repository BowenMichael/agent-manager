class IssueViewer extends HTMLElement {
  constructor() {
    super();
    this._sessionId = null;
  }

  static get observedAttributes() {
    return ['session-id'];
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (name === 'session-id' && oldValue !== newValue) {
      this._sessionId = newValue;
      this.loadIssue();
    }
  }

  connectedCallback() {
    this.renderSkeleton();
    if (this.getAttribute('session-id')) {
      this._sessionId = this.getAttribute('session-id');
      this.loadIssue();
    }
  }

  renderSkeleton() {
    this.innerHTML = `
      <div class="issue-viewer-container">
        <div class="issue-viewer-header" id="issue-header">
          <div class="issue-empty-placeholder">Select an agent session to view associated issue...</div>
        </div>
        <div class="issue-conversation-stream" id="issue-stream">
          <!-- Comments stream populated dynamically -->
        </div>
      </div>
    `;
  }

  async loadIssue() {
    if (!this._sessionId) return;
    const headerEl = this.querySelector('#issue-header');
    const streamEl = this.querySelector('#issue-stream');
    if (!headerEl || !streamEl) return;

    headerEl.innerHTML = `<div class="issue-empty-placeholder">Loading GitHub issue details...</div>`;
    streamEl.innerHTML = '';

    try {
      const resp = await fetch(`/api/agents/${encodeURIComponent(this._sessionId)}/issue`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      if (!data.issue) {
        headerEl.innerHTML = `
          <div class="issue-empty-placeholder">
            No GitHub issue associated with session (${this.escapeHtml(data.repo || 'unknown repo')}).
          </div>
        `;
        return;
      }

      const issue = data.issue;
      const isOpen = issue.state === 'open';
      const stateBadge = isOpen
        ? `<span class="issue-state-badge issue-state-open">Open</span>`
        : `<span class="issue-state-badge issue-state-closed">Closed</span>`;

      headerEl.innerHTML = `
        <div class="issue-viewer-title-row">
          <h3 class="issue-viewer-title">#${issue.number} ${this.escapeHtml(issue.title)}</h3>
          ${stateBadge}
        </div>
        <div class="issue-viewer-meta">
          <span>Opened by <strong>${this.escapeHtml(issue.user?.login || 'unknown')}</strong></span>
          <span>•</span>
          <a href="${issue.html_url}" target="_blank" style="color: var(--accent-cyan); text-decoration: none;">View on GitHub ↗</a>
        </div>
      `;

      let streamHtml = '';
      if (issue.body) {
        streamHtml += `
          <div class="issue-comment-card">
            <div class="issue-comment-author-bar">
              <span class="issue-comment-author">${this.escapeHtml(issue.user?.login || 'Author')} (Description)</span>
              <span>${new Date(issue.created_at).toLocaleString()}</span>
            </div>
            <div class="issue-comment-body markdown-body">
              ${this.renderMarkdown(issue.body)}
            </div>
          </div>
        `;
      }

      if (data.comments && data.comments.length > 0) {
        data.comments.forEach(comment => {
          streamHtml += `
            <div class="issue-comment-card">
              <div class="issue-comment-author-bar">
                <span class="issue-comment-author">${this.escapeHtml(comment.user?.login || 'User')}</span>
                <span>${new Date(comment.created_at).toLocaleString()}</span>
              </div>
              <div class="issue-comment-body markdown-body">
                ${this.renderMarkdown(comment.body)}
              </div>
            </div>
          `;
        });
      }

      streamEl.innerHTML = streamHtml || `<div class="issue-empty-placeholder">No conversation comments yet.</div>`;
    } catch (err) {
      headerEl.innerHTML = `<div class="issue-empty-placeholder" style="color: var(--accent-red, #f87171);">Failed to load issue: ${this.escapeHtml(err.message)}</div>`;
    }
  }

  renderMarkdown(text) {
    if (!text) return '';
    try {
      if (window.marked && window.DOMPurify) {
        return window.DOMPurify.sanitize(window.marked.parse(text));
      }
    } catch (e) {
      console.warn("Markdown render error:", e);
    }
    return `<pre>${this.escapeHtml(text)}</pre>`;
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

customElements.define('issue-viewer', IssueViewer);
