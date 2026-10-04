/**
 * Interactive File Viewer Modal: Fetches and displays file contents scoped to
 * the agent's worktree with line numbering and highlighted ranges.
 */
(function() {
let fileModalInstance = null;

function ensureFileModal() {
  if (fileModalInstance) return fileModalInstance;

  const backdrop = document.createElement('div');
  backdrop.id = 'file-modal-backdrop';
  backdrop.className = 'file-modal-backdrop';
  backdrop.innerHTML = `
    <div class="file-modal-container" role="dialog" aria-modal="true">
      <div class="file-modal-header">
        <div class="file-modal-title-group">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#58a6ff" stroke-width="2">
            <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
            <polyline points="13 2 13 9 20 9"></polyline>
          </svg>
          <div>
            <div id="file-modal-filename" class="file-modal-filename">File Viewer</div>
            <div id="file-modal-path" class="file-modal-path"></div>
          </div>
        </div>
        <div class="file-modal-actions">
          <button id="file-modal-copy-btn" class="command-output-btn" title="Copy file content">Copy</button>
          <button id="file-modal-close-btn" class="file-modal-close-btn" title="Close (Esc)">&times;</button>
        </div>
      </div>
      <div id="file-modal-body" class="file-modal-body">
        <div style="padding: 20px; color: #8b949e; text-align: center;">Loading file contents...</div>
      </div>
    </div>
  `;

  document.body.appendChild(backdrop);

  // Close event handlers
  const closeBtn = backdrop.querySelector('#file-modal-close-btn');
  closeBtn.addEventListener('click', closeFileModal);

  backdrop.addEventListener('click', (e) => {
    if (e.target === backdrop) {
      closeFileModal();
    }
  });

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && backdrop.classList.contains('open')) {
      closeFileModal();
    }
  });

  fileModalInstance = backdrop;
  return backdrop;
}

function closeFileModal() {
  if (fileModalInstance) {
    fileModalInstance.classList.remove('open');
  }
}

async function openFileViewer(sessionId, filePath, options = {}) {
  if (!sessionId || !filePath) return;

  const modal = ensureFileModal();
  const filenameEl = modal.querySelector('#file-modal-filename');
  const pathEl = modal.querySelector('#file-modal-path');
  const bodyEl = modal.querySelector('#file-modal-body');
  const copyBtn = modal.querySelector('#file-modal-copy-btn');

  const baseName = filePath.replace(/\\/g, '/').split('/').pop() || filePath;
  filenameEl.textContent = baseName;
  pathEl.textContent = filePath;
  bodyEl.innerHTML = `<div style="padding: 40px; color: #8b949e; text-align: center;">Fetching file contents...</div>`;
  modal.classList.add('open');

  try {
    const url = `/api/agents/${encodeURIComponent(sessionId)}/files/content?path=${encodeURIComponent(filePath)}`;
    const res = await fetch(url);

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const msg = errData.detail || `HTTP Error ${res.status}`;
      bodyEl.innerHTML = `
        <div style="padding: 30px; color: #f85149; text-align: center;">
          <div style="font-weight: 600; margin-bottom: 8px;">Failed to load file</div>
          <div style="font-size: 12px; color: #8b949e;">${escapeHtml(msg)}</div>
        </div>
      `;
      return;
    }

    const data = await res.json();
    const content = data.content || '';
    const lines = content.split('\n');

    // Wire Copy Button
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(content).then(() => {
        copyBtn.textContent = 'Copied!';
        setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1500);
      });
    };

    // Render lines with numbering
    const startLine = options.startLine ? parseInt(options.startLine, 10) : null;
    const endLine = options.endLine ? parseInt(options.endLine, 10) : null;

    const table = document.createElement('div');
    table.className = 'file-code-table';

    let firstHighlightedEl = null;

    lines.forEach((lineText, idx) => {
      const lineNum = idx + 1;
      const isHighlighted = startLine && endLine && lineNum >= startLine && lineNum <= endLine;

      const row = document.createElement('div');
      row.className = `file-code-line${isHighlighted ? ' highlighted' : ''}`;
      if (isHighlighted && !firstHighlightedEl) {
        firstHighlightedEl = row;
      }

      const numCol = document.createElement('div');
      numCol.className = 'file-line-num';
      numCol.textContent = lineNum;

      const contentCol = document.createElement('div');
      contentCol.className = 'file-line-content';
      contentCol.textContent = lineText;

      row.appendChild(numCol);
      row.appendChild(contentCol);
      table.appendChild(row);
    });

    bodyEl.innerHTML = '';
    bodyEl.appendChild(table);

    // Scroll to first highlighted line if available
    if (firstHighlightedEl) {
      setTimeout(() => {
        firstHighlightedEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 50);
    }
  } catch (err) {
    bodyEl.innerHTML = `
      <div style="padding: 30px; color: #f85149; text-align: center;">
        <div style="font-weight: 600; margin-bottom: 8px;">Network Error</div>
        <div style="font-size: 12px; color: #8b949e;">${escapeHtml(err.message)}</div>
      </div>
    `;
  }
}

// Export to global scope
window.openFileViewer = openFileViewer;
window.closeFileModal = closeFileModal;
})();
