// Overview Side Panel UI Module

function updateOverviewPanel(session) {
  if (!session) return;

  const msgs = session.messages || [];
  let toolCalls = 0;
  let cmdsRun = 0;
  const filesTouched = new Set();
  const toolCounts = {};
  const recentActions = [];
  let latestActivity = 'Agent initialized. Analyzing task objective and codebase...';
  let latestSub = 'Status: ' + session.status;

  for (let i = msgs.length - 1; i >= 0; i--) {
    const m = msgs[i];
    if (m.role === 'TOOL_CALL') {
      toolCalls++;
      const tName = m.tool_name || 'tool';
      toolCounts[tName] = (toolCounts[tName] || 0) + 1;

      let actionDesc = tName;
      let icon = '⚡';

      if (tName === 'run_command') {
        cmdsRun++;
        icon = '💻';
        const cmd = m.tool_args?.CommandLine || m.tool_args?.command || '';
        actionDesc = 'Ran: ' + (cmd.length > 40 ? cmd.substring(0, 37) + '...' : cmd);
      } else if (tName === 'view_file') {
        icon = '📄';
        const file = m.tool_args?.AbsolutePath || m.tool_args?.path || '';
        const baseName = file.split(/[\\/]/).pop();
        filesTouched.add(baseName);
        actionDesc = 'Viewed ' + baseName;
      } else if (tName === 'write_to_file' || tName === 'replace_file_content' || tName === 'multi_replace_file_content') {
        icon = '📝';
        const file = m.tool_args?.TargetFile || m.tool_args?.path || '';
        const baseName = file.split(/[\\/]/).pop();
        filesTouched.add(baseName);
        actionDesc = 'Edited ' + baseName;
      } else if (tName === 'call_mcp_tool') {
        icon = '🔌';
        actionDesc = 'MCP ' + (m.tool_args?.ToolName || 'tool');
      }

      if (recentActions.length < 4) {
        recentActions.push({ icon, desc: actionDesc, time: m.timestamp });
      }

      if (latestActivity === 'Agent initialized. Analyzing task objective and codebase...') {
        latestActivity = actionDesc;
        latestSub = 'Tool: ' + tName;
      }
    } else if (m.role === 'AGENT' && latestActivity === 'Agent initialized. Analyzing task objective and codebase...') {
      latestActivity = m.content.substring(0, 80) + '...';
      latestSub = 'Thinking / Synthesizing';
    }
  }

  // 1. Current Activity Highlight
  const elSummary = document.getElementById('overview-activity-summary');
  const elSub = document.getElementById('overview-activity-sub');
  const elBadge = document.getElementById('overview-badge');
  if (elSummary) elSummary.textContent = latestActivity;
  if (elSub) elSub.textContent = latestSub;
  if (elBadge) {
    elBadge.textContent = session.status === 'RUNNING' ? 'EXECUTING' : session.status;
    elBadge.style.color = session.status === 'COMPLETED' ? 'var(--accent-green)' : (session.status === 'RUNNING' ? 'var(--accent-cyan)' : 'var(--accent-amber)');
  }

  // 2. Workflow Milestones
  const msBranchText = document.getElementById('ms-branch-text');
  if (msBranchText) msBranchText.textContent = session.git_branch || 'main';

  const msToolProgress = document.getElementById('ms-tool-progress');
  if (msToolProgress) {
    msToolProgress.textContent = `${toolCalls} tool turns completed`;
  }

  const stepExec = document.getElementById('ms-step-exec');
  const stepVerify = document.getElementById('ms-step-verify');
  const stepPr = document.getElementById('ms-step-pr');

  if (session.status === 'COMPLETED') {
    if (stepExec) stepExec.className = 'milestone-step step-done';
    if (stepVerify) stepVerify.className = 'milestone-step step-done';
    if (stepPr) stepPr.className = 'milestone-step step-done';
  } else if (session.status === 'RUNNING') {
    if (stepExec) stepExec.className = 'milestone-step step-active';
    if (cmdsRun > 10 && stepVerify) stepVerify.className = 'milestone-step step-active';
  }

  // 3. Telemetry Stats Grid
  const elToolCalls = document.getElementById('stat-tool-calls');
  const elCmdsRun = document.getElementById('stat-cmds-run');
  const elFiles = document.getElementById('stat-files-touched');
  const elTurns = document.getElementById('stat-agent-turns');

  if (elToolCalls) elToolCalls.textContent = toolCalls;
  if (elCmdsRun) elCmdsRun.textContent = cmdsRun;
  if (elFiles) elFiles.textContent = filesTouched.size;
  if (elTurns) elTurns.textContent = session.turn_count || toolCalls;

  // Tool tags breakdown
  const toolContainer = document.getElementById('tools-tags-container');
  if (toolContainer) {
    toolContainer.innerHTML = '';
    const entries = Object.entries(toolCounts);
    if (entries.length === 0) {
      toolContainer.innerHTML = '<span style="font-size: 0.7rem; color: var(--text-dim); font-style: italic;">No tools invoked yet</span>';
    } else {
      entries.forEach(([name, count]) => {
        const chip = document.createElement('span');
        chip.className = 'tool-chip';
        chip.innerHTML = `${name}: <strong>${count}</strong>`;
        toolContainer.appendChild(chip);
      });
    }
  }

  // 4. Usage & Token Telemetry Box
  const totalToks = session.total_tokens || session.token_count || 0;
  const inputToks = session.input_tokens || 0;
  const outputToks = session.output_tokens || 0;
  const thinkingToks = session.thinking_tokens || 0;
  const duration = session.duration_seconds || 0;

  const elTotalToks = document.getElementById('usage-total-tokens');
  const elInputToks = document.getElementById('usage-input-tokens');
  const elOutputToks = document.getElementById('usage-output-tokens');
  const elThinkingToks = document.getElementById('usage-thinking-tokens');
  const elDuration = document.getElementById('usage-duration');

  if (elTotalToks) elTotalToks.textContent = formatTokens(totalToks);
  if (elInputToks) elInputToks.textContent = formatTokens(inputToks);
  if (elOutputToks) elOutputToks.textContent = formatTokens(outputToks);
  if (elThinkingToks) elThinkingToks.textContent = formatTokens(thinkingToks);
  if (elDuration) elDuration.textContent = formatDuration(duration);

  // Quota percentage and limit tracking
  const maxTokens = session.max_tokens || 150000;
  const pct = Math.min(100, Math.round(((totalToks / maxTokens) * 100) * 10) / 10);
  const elQuotaPct = document.getElementById('usage-quota-percent');
  const elQuotaFill = document.getElementById('usage-quota-fill');
  const elTokensRatio = document.getElementById('usage-tokens-ratio');
  const elQuotaStatus = document.getElementById('usage-quota-status');

  if (elQuotaPct) elQuotaPct.textContent = pct + '%';
  if (elTokensRatio) elTokensRatio.textContent = `${totalToks.toLocaleString()} / ${maxTokens.toLocaleString()} tokens`;

  if (elQuotaFill) {
    elQuotaFill.style.width = pct + '%';
    if (pct >= 90) {
      elQuotaFill.className = 'quota-bar-fill danger';
      if (elQuotaStatus) { elQuotaStatus.textContent = 'CRITICAL / LIMIT'; elQuotaStatus.style.color = 'var(--accent-red)'; }
    } else if (pct >= 70) {
      elQuotaFill.className = 'quota-bar-fill warning';
      if (elQuotaStatus) { elQuotaStatus.textContent = 'HIGH'; elQuotaStatus.style.color = 'var(--accent-amber)'; }
    } else {
      elQuotaFill.className = 'quota-bar-fill';
      if (elQuotaStatus) { elQuotaStatus.textContent = 'HEALTHY'; elQuotaStatus.style.color = 'var(--accent-green)'; }
    }
  }

  // Handle Resume button visibility
  const btnResume = document.getElementById('btn-resume-current');
  if (btnResume) {
    if (session.status === 'PAUSED') {
      btnResume.classList.remove('hidden');
    } else {
      btnResume.classList.add('hidden');
    }
  }

  // 5. Recent Actions Feed
  const actionsList = document.getElementById('recent-actions-list');
  if (actionsList) {
    actionsList.innerHTML = '';
    if (recentActions.length === 0) {
      actionsList.innerHTML = '<li class="action-item-empty">Listening for agent actions...</li>';
    } else {
      recentActions.forEach(act => {
        const li = document.createElement('li');
        li.className = 'action-item';
        li.innerHTML = `<span class="action-item-icon">${act.icon}</span><span title="${act.desc}">${act.desc}</span>`;
        actionsList.appendChild(li);
      });
    }
  }
}

window.updateOverviewPanel = updateOverviewPanel;
