// Chat Transcript & Message Rendering Module

function formatContent(str) {
  if (!str) return '';
  if (typeof window.renderMarkdownContent === 'function') {
    return window.renderMarkdownContent(str);
  }
  return escapeHtml(str).replace(/\n/g, '<br>');
}

function renderMessageItem(msg) {
  const transcriptStream = document.getElementById('transcript-stream');
  if (!transcriptStream) return;

  const bubble = document.createElement('div');
  
  if (msg.role === 'USER') {
    bubble.className = 'msg-bubble msg-user';
    bubble.innerHTML = `<span class="msg-role-tag">USER CONTEXT</span>${formatContent(msg.content)}`;
  } else if (msg.role === 'AGENT') {
    bubble.className = 'msg-bubble msg-agent';
    bubble.innerHTML = `<span class="msg-role-tag">AGENT RESPONSE</span>${formatContent(msg.content)}`;
  } else if (msg.role === 'THOUGHT') {
    bubble.className = 'msg-bubble msg-thought';
    bubble.innerHTML = `<span class="msg-role-tag">THINKING TRACE</span>${formatContent(msg.content)}`;
  } else if (msg.role === 'TOOL_RESULT' || msg.tool_name === 'agy_terminal') {
    bubble.className = 'msg-terminal';
    const tName = msg.tool_name || 'Terminal';
    const isGenericDone = !msg.content || msg.content.trim() === 'Done';
    const headerLabel = isGenericDone ? `AGY TERMINAL: ${escapeHtml(tName).toUpperCase()}` : `AGY TERMINAL LOG: ${escapeHtml(tName).toUpperCase()}`;
    if (typeof window.createCommandOutputUI === 'function') {
      const outputCard = window.createCommandOutputUI(msg.content, headerLabel);
      bubble.appendChild(outputCard);
    } else {
      bubble.innerHTML = `
        <div class="terminal-header">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
          <span>${headerLabel}</span>
        </div>
        <div class="terminal-body">${escapeHtml(msg.content)}</div>
      `;
    }
  } else if (msg.role === 'TOOL_CALL') {
    bubble.className = 'msg-tool';
    const tName = msg.tool_name || 'tool';
    const args = msg.tool_args || {};

    let targetBadge = '';
    let actionDesc = '';

    if (tName === 'view_file') {
      const p = args.AbsolutePath || args.path || '';
      const base = p.split(/[\\/]/).pop() || '';
      const startLine = args.StartLine || '';
      const endLine = args.EndLine || '';
      targetBadge = base ? `<span class="tool-tag-file file-clickable-badge" data-filepath="${escapeHtml(p)}" data-startline="${escapeHtml(String(startLine))}" data-endline="${escapeHtml(String(endLine))}" title="Click to view file in interactive viewer">📄 ${escapeHtml(base)}</span>` : '';
      const lineRange = (startLine && endLine) ? ` (lines ${startLine}-${endLine})` : '';
      const action = args.toolAction || args.toolSummary || '';
      actionDesc = action ? `${action}: ${p}${lineRange}` : `${p}${lineRange}`;
    } else if (tName === 'replace_file_content' || tName === 'write_to_file' || tName === 'multi_replace_file_content') {
      const p = args.TargetFile || args.path || '';
      const base = p.split(/[\\/]/).pop() || '';
      const icon = tName === 'write_to_file' ? '📝 Create' : '✏️ Edit';
      targetBadge = base ? `<span class="tool-tag-file file-clickable-badge" data-filepath="${escapeHtml(p)}" title="Click to view file in interactive viewer">${icon}: ${escapeHtml(base)}</span>` : '';
      const instr = args.Instruction || args.Description || args.toolAction || args.toolSummary || '';
      actionDesc = instr ? `${p} - ${instr}` : p;
    } else if (tName === 'run_command') {
      const cmd = args.CommandLine || args.command || '';
      targetBadge = `<span class="tool-tag-cmd">💻 Shell</span>`;
      const summary = args.toolSummary || args.toolAction || '';
      actionDesc = summary ? `${summary}: ${cmd}` : cmd;
    } else if (tName === 'call_mcp_tool') {
      const sub = args.ToolName || 'tool';
      const server = args.ServerName ? `[${args.ServerName}] ` : '';
      targetBadge = `<span class="tool-tag-mcp">🔌 MCP ${escapeHtml(server + sub)}</span>`;
      const subArgs = args.Arguments ? JSON.stringify(args.Arguments) : '';
      actionDesc = subArgs ? `${sub}(${subArgs})` : sub;
    }

    const headerTitle = targetBadge || `<span>TOOL EXECUTION: ${escapeHtml(tName)}</span>`;
    const bodyContent = actionDesc ? escapeHtml(actionDesc) : escapeHtml(msg.content);

    bubble.innerHTML = `
      <div class="tool-header">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
        <span>TOOL EXECUTION: ${escapeHtml(tName)}</span>
        ${targetBadge}
      </div>
      <div class="tool-args">${bodyContent}</div>
    `;

    if (typeof window.createDiffViewerUI === 'function') {
      if (tName === 'replace_file_content' && (args.TargetContent || args.ReplacementContent)) {
        const diffBlock = window.createDiffViewerUI(args.TargetContent || '', args.ReplacementContent || '');
        bubble.appendChild(diffBlock);
      } else if (tName === 'write_to_file' && args.CodeContent) {
        const diffBlock = window.createDiffViewerUI('', args.CodeContent || '');
        bubble.appendChild(diffBlock);
      }
    }
  } else if (msg.role === 'SYSTEM') {
    if (msg.content && msg.content.includes('Chat Compacted & Compressed')) {
      bubble.className = 'msg-bubble msg-compacted';
      bubble.innerHTML = `
        <div class="msg-compacted-header">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 14 10 14 10 20"></polyline><polyline points="20 10 14 10 14 4"></polyline><line x1="14" y1="10" x2="21" y2="3"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg>
          <span>CHAT COMPACTED & COMPRESSED (TOKEN OPTIMIZATION)</span>
        </div>
        <div class="msg-compacted-body">${formatContent(msg.content.replace('📦 **Chat Compacted & Compressed (Token Optimization)**\n', ''))}</div>
      `;
    } else {
      bubble.className = 'msg-bubble msg-system';
      bubble.innerHTML = `<strong>SYSTEM:</strong> ${escapeHtml(msg.content)}`;
    }
  }

  transcriptStream.appendChild(bubble);
}

function renderTranscript(session) {
  const transcriptStream = document.getElementById('transcript-stream');
  if (!transcriptStream) return;
  transcriptStream.innerHTML = '';
  (session.messages || []).forEach(msg => {
    renderMessageItem(msg);
  });
  if (typeof window.scrollToBottom === 'function') {
    window.scrollToBottom();
  }
}

window.formatContent = formatContent;
window.renderMessageItem = renderMessageItem;
window.renderTranscript = renderTranscript;
