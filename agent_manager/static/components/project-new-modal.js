/**
 * project-new-modal.js
 * Modal dialog for creating new GitHub issues across projects directly from the Project View.
 */
(function() {
function openNewProjectIssueModal(defaultRepo = 'BowenMichael/fit-elo', onCreated = null) {
  let modal = document.getElementById('modal-new-project-issue');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'modal-new-project-issue';
    modal.className = 'modal-backdrop hidden';
    modal.innerHTML = `
      <div class="modal-card" style="max-width: 580px;">
        <div class="modal-header">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 1.2rem;">✨</span>
            <h3 style="margin: 0; font-size: 1.1rem;">Create Project Issue</h3>
          </div>
          <button class="btn-icon" id="btn-close-new-issue-modal">&times;</button>
        </div>
        <div class="modal-body" style="display: flex; flex-direction: column; gap: 14px; padding: 18px 24px;">
          <div class="form-group">
            <label style="font-size: 0.8rem; font-weight: 600; color: var(--text-muted); display: block; margin-bottom: 6px;">Target Project / Repository</label>
            <select id="new-issue-repo" class="form-control" style="width: 100%; padding: 8px 12px; background: rgba(0,0,0,0.3); border: 1px solid var(--border-color); border-radius: 6px; color: #fff;">
              <option value="BowenMichael/fit-elo">🏋️ FitElo (BowenMichael/fit-elo)</option>
              <option value="BowenMichael/better_buisness_deal">💼 Better Business Deal (BowenMichael/better_buisness_deal)</option>
              <option value="BowenMichael/leanfolio">📈 Leanfolio (BowenMichael/leanfolio)</option>
              <option value="BowenMichael/agent-manager">🤖 Agent Manager (BowenMichael/agent-manager)</option>
              <option value="BowenMichael/f1-frontend">🏎️ F1 Frontend (BowenMichael/f1-frontend)</option>
            </select>
          </div>

          <div class="form-group">
            <label style="font-size: 0.8rem; font-weight: 600; color: var(--text-muted); display: block; margin-bottom: 6px;">Issue Title</label>
            <input type="text" id="new-issue-title" placeholder="[FEAT] or [TASK]: Short descriptive title" style="width: 100%; box-sizing: border-box; padding: 8px 12px; background: rgba(0,0,0,0.3); border: 1px solid var(--border-color); border-radius: 6px; color: #fff;" />
          </div>

          <div class="form-group">
            <label style="font-size: 0.8rem; font-weight: 600; color: var(--text-muted); display: block; margin-bottom: 6px;">Requirements & Context (Markdown)</label>
            <textarea id="new-issue-body" rows="6" style="width: 100%; box-sizing: border-box; padding: 8px 12px; background: rgba(0,0,0,0.3); border: 1px solid var(--border-color); border-radius: 6px; color: #fff; font-family: monospace; font-size: 0.8rem; resize: vertical;" placeholder="### 🎯 Objective\nDescribe the feature or fix...\n\n### 📋 Acceptance Criteria\n- [ ] Criterion 1\n- [ ] Criterion 2"></textarea>
          </div>

          <div id="new-issue-status-msg" style="font-size: 0.8rem; display: none;"></div>
        </div>

        <div class="modal-footer" style="display: flex; justify-content: flex-end; gap: 10px; padding: 14px 24px; border-top: 1px solid var(--border-color);">
          <button class="btn btn-secondary" id="btn-cancel-new-issue">Cancel</button>
          <button class="btn btn-primary" id="btn-submit-new-issue" style="display: flex; align-items: center; gap: 6px;">
            <span>Create & Dispatch</span>
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    modal.querySelector('#btn-close-new-issue-modal').onclick = () => modal.classList.add('hidden');
    modal.querySelector('#btn-cancel-new-issue').onclick = () => modal.classList.add('hidden');

    const submitBtn = modal.querySelector('#btn-submit-new-issue');
    submitBtn.onclick = async () => {
      const repo = modal.querySelector('#new-issue-repo').value;
      const title = modal.querySelector('#new-issue-title').value.trim();
      const body = modal.querySelector('#new-issue-body').value.trim();
      const statusEl = modal.querySelector('#new-issue-status-msg');

      if (!title) {
        statusEl.style.display = 'block';
        statusEl.style.color = '#ef4444';
        statusEl.innerText = 'Please enter an issue title.';
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerText = 'Creating on GitHub...';
      statusEl.style.display = 'none';

      try {
        const resp = await fetch('/api/projects/issues', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ repo, title, body })
        });
        const res = await resp.json();
        if (!resp.ok) {
          throw new Error(res.detail || 'Failed to create issue');
        }

        modal.classList.add('hidden');
        if (typeof onCreated === 'function') {
          onCreated(res);
        }
      } catch (err) {
        statusEl.style.display = 'block';
        statusEl.style.color = '#ef4444';
        statusEl.innerText = err.message || 'Error creating issue.';
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Create & Dispatch</span>';
      }
    };
  }

  // Pre-select repo
  const repoSelect = modal.querySelector('#new-issue-repo');
  if (repoSelect && defaultRepo) {
    repoSelect.value = defaultRepo;
  }
  const titleInput = modal.querySelector('#new-issue-title');
  if (titleInput) titleInput.value = '';
  const bodyInput = modal.querySelector('#new-issue-body');
  if (bodyInput) {
    bodyInput.value = `### 🎯 Objective\n\n### 📋 Acceptance Criteria\n- [ ] Complete implementation\n- [ ] Verification and tests`;
  }
  const statusEl = modal.querySelector('#new-issue-status-msg');
  if (statusEl) statusEl.style.display = 'none';

  modal.classList.remove('hidden');
}

window.openNewProjectIssueModal = openNewProjectIssueModal;
})();
