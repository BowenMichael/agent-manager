/**
 * Command Output Component: Renders rich, formatted, collapsible, and scrollable
 * stdout/stderr logs for run_command and terminal executions.
 */

function createCommandOutputUI(rawContent, headerLabel = 'SHELL COMMAND LOG') {
  const card = document.createElement('div');
  card.className = 'command-output-card';

  const content = (rawContent || '').trim();
  const lineCount = content ? content.split('\n').length : 0;

  // Header Bar
  const header = document.createElement('div');
  header.className = 'command-output-header';

  const titleGroup = document.createElement('div');
  titleGroup.className = 'command-output-title';
  titleGroup.innerHTML = `
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="6 9 12 15 18 9"></polyline>
    </svg>
    <span>${escapeHtml(headerLabel)}</span>
  `;

  const metaGroup = document.createElement('div');
  metaGroup.className = 'command-output-meta';

  const badge = document.createElement('span');
  badge.className = 'command-output-badge';
  badge.textContent = `${lineCount} line${lineCount === 1 ? '' : 's'}`;
  metaGroup.appendChild(badge);

  const copyBtn = document.createElement('button');
  copyBtn.className = 'command-output-btn';
  copyBtn.title = 'Copy output to clipboard';
  copyBtn.textContent = 'Copy';
  copyBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(content).then(() => {
      copyBtn.textContent = 'Copied!';
      setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1500);
    });
  });
  metaGroup.appendChild(copyBtn);

  header.appendChild(titleGroup);
  header.appendChild(metaGroup);

  // Body Content
  const body = document.createElement('pre');
  body.className = 'command-output-body';

  // Format stdout/stderr sections if present
  if (content.includes('[STDOUT]') || content.includes('[STDERR]')) {
    const formattedHtml = content
      .split('\n')
      .map(line => {
        if (line.startsWith('[STDOUT]')) {
          return `<span style="color:#58a6ff; font-weight:bold;">${escapeHtml(line)}</span>`;
        }
        if (line.startsWith('[STDERR]')) {
          return `<span style="color:#f85149; font-weight:bold;">${escapeHtml(line)}</span>`;
        }
        if (line.startsWith('Exit Code:')) {
          const isError = !line.includes(': 0');
          const color = isError ? '#f85149' : '#3fb950';
          return `<span style="color:${color}; font-weight:bold;">${escapeHtml(line)}</span>`;
        }
        return escapeHtml(line);
      })
      .join('\n');
    body.innerHTML = formattedHtml;
  } else {
    body.textContent = content || '(No output recorded)';
  }

  // Toggle Collapse on Header Click
  header.addEventListener('click', () => {
    card.classList.toggle('collapsed');
  });

  // If output is long (> 30 lines), start collapsed by default to preserve readability
  if (lineCount > 30) {
    card.classList.add('collapsed');
  }

  card.appendChild(header);
  card.appendChild(body);
  return card;
}

// Export to global scope
window.createCommandOutputUI = createCommandOutputUI;
