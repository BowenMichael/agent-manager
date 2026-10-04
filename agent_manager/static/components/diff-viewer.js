/**
 * Diff Viewer Component: Renders visual before/after diffs and patch comparisons
 * for replace_file_content and write_to_file agent tool calls.
 */

function createDiffViewerUI(targetContent, replacementContent, options = {}) {
  const wrapper = document.createElement('div');
  wrapper.className = 'diff-viewer-wrapper';

  const beforeText = typeof targetContent === 'string' ? targetContent : '';
  const afterText = typeof replacementContent === 'string' ? replacementContent : '';
  const isCreate = !beforeText && !!afterText;

  const beforeLines = beforeText ? beforeText.split('\n') : [];
  const afterLines = afterText ? afterText.split('\n') : [];

  // Header Bar
  const header = document.createElement('div');
  header.className = 'diff-viewer-header';

  const title = document.createElement('span');
  title.style.fontWeight = '600';
  if (isCreate) {
    title.innerHTML = `<span style="color:#3fb950;">+ ${afterLines.length} lines written</span>`;
  } else {
    title.innerHTML = `<span>File Changes: </span><span style="color:#f85149;">-${beforeLines.length}</span> / <span style="color:#3fb950;">+${afterLines.length}</span>`;
  }

  const toggleBtn = document.createElement('button');
  toggleBtn.className = 'diff-viewer-toggle-btn';
  toggleBtn.innerHTML = `
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="6 9 12 15 18 9"></polyline>
    </svg>
    <span>Inspect Diff</span>
  `;

  header.appendChild(title);
  header.appendChild(toggleBtn);

  // Container
  const container = document.createElement('div');
  container.className = 'diff-viewer-container collapsed'; // Collapsed by default

  if (!isCreate) {
    // Before Pane (Removals)
    const beforePane = document.createElement('div');
    beforePane.className = 'diff-pane diff-pane-before';

    const beforeTitle = document.createElement('div');
    beforeTitle.className = 'diff-pane-title';
    beforeTitle.textContent = `Original (${beforeLines.length} lines)`;

    const beforePre = document.createElement('pre');
    beforePre.className = 'diff-content';
    beforePre.innerHTML = beforeLines
      .map(line => `<div class="diff-line-removed">- ${escapeHtml(line)}</div>`)
      .join('');

    beforePane.appendChild(beforeTitle);
    beforePane.appendChild(beforePre);
    container.appendChild(beforePane);
  }

  // After Pane (Additions)
  const afterPane = document.createElement('div');
  afterPane.className = 'diff-pane diff-pane-after';

  const afterTitle = document.createElement('div');
  afterTitle.className = 'diff-pane-title';
  afterTitle.textContent = isCreate ? `New File Content (${afterLines.length} lines)` : `Replacement (${afterLines.length} lines)`;

  const afterPre = document.createElement('pre');
  afterPre.className = 'diff-content';
  afterPre.innerHTML = afterLines
    .map(line => `<div class="diff-line-added">+ ${escapeHtml(line)}</div>`)
    .join('');

  afterPane.appendChild(afterTitle);
  afterPane.appendChild(afterPre);
  container.appendChild(afterPane);

  // Toggle button event
  toggleBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    const isNowCollapsed = container.classList.toggle('collapsed');
    toggleBtn.querySelector('span').textContent = isNowCollapsed ? 'Inspect Diff' : 'Hide Diff';
    const svg = toggleBtn.querySelector('svg');
    if (svg) {
      svg.style.transform = isNowCollapsed ? 'none' : 'rotate(180deg)';
    }
  });

  wrapper.appendChild(header);
  wrapper.appendChild(container);
  return wrapper;
}

// Export to global scope
window.createDiffViewerUI = createDiffViewerUI;
