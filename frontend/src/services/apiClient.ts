import type { AgentSessionInfo, SpawnRequest } from '../types/agent'

export async function fetchAgents(includeArchived: boolean = true): Promise<AgentSessionInfo[]> {
  const res = await fetch(`/api/agents?include_archived=${includeArchived}`)
  if (!res.ok) {
    throw new Error(`Failed to fetch agents: ${res.statusText}`)
  }
  return res.json()
}

export async function fetchAgent(sessionId: string): Promise<AgentSessionInfo> {
  const res = await fetch(`/api/agents/${sessionId}`)
  if (!res.ok) {
    throw new Error(`Failed to fetch agent ${sessionId}: ${res.statusText}`)
  }
  return res.json()
}

export async function spawnAgent(req: SpawnRequest): Promise<AgentSessionInfo> {
  const res = await fetch('/api/agents/spawn', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to spawn agent: ${res.statusText}`)
  }
  return res.json()
}

export async function stopAgent(sessionId: string, reason?: string): Promise<void> {
  const res = await fetch(`/api/agents/${sessionId}/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: reason || 'Stopped via React UI' }),
  })
  if (!res.ok) {
    throw new Error(`Failed to stop agent: ${res.statusText}`)
  }
}

export async function restartAgent(sessionId: string): Promise<AgentSessionInfo> {
  const res = await fetch(`/api/agents/${sessionId}/restart`, {
    method: 'POST',
  })
  if (!res.ok) {
    throw new Error(`Failed to restart agent: ${res.statusText}`)
  }
  return res.json()
}

export async function archiveAgent(sessionId: string): Promise<void> {
  const res = await fetch(`/api/agents/${sessionId}/archive`, {
    method: 'POST',
  })
  if (!res.ok) {
    throw new Error(`Failed to archive agent: ${res.statusText}`)
  }
}

export async function unarchiveAgent(sessionId: string): Promise<void> {
  const res = await fetch(`/api/agents/${sessionId}/unarchive`, {
    method: 'POST',
  })
  if (!res.ok) {
    throw new Error(`Failed to unarchive agent: ${res.statusText}`)
  }
}

export async function completeAgent(sessionId: string): Promise<void> {
  const res = await fetch(`/api/agents/${sessionId}/complete`, {
    method: 'POST',
  })
  if (!res.ok) {
    throw new Error(`Failed to complete agent: ${res.statusText}`)
  }
}

export async function addContext(sessionId: string, context: string): Promise<void> {
  const res = await fetch(`/api/agents/${sessionId}/context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ context }),
  })
  if (!res.ok) {
    throw new Error(`Failed to send context: ${res.statusText}`)
  }
}

export async function fetchIssues(): Promise<any> {
  const res = await fetch('/api/issues')
  if (!res.ok) {
    throw new Error(`Failed to fetch issues: ${res.statusText}`)
  }
  return res.json()
}

export async function startIssueAgent(repo: string, issueNumber: number, title?: string, body?: string): Promise<any> {
  const res = await fetch('/api/issues/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo, issue_number: issueNumber, title, body }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to start agent: ${res.statusText}`)
  }
  return res.json()
}

export async function pauseIssueAgent(repo: string, issueNumber: number): Promise<any> {
  const res = await fetch('/api/issues/pause', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo, issue_number: issueNumber }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to pause agent: ${res.statusText}`)
  }
  return res.json()
}

export async function stopIssueAgent(repo: string, issueNumber: number): Promise<any> {
  const res = await fetch('/api/issues/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo, issue_number: issueNumber }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to stop agent: ${res.statusText}`)
  }
  return res.json()
}

export async function syncProjectBoards(): Promise<any> {
  const res = await fetch('/api/issues/sync', {
    method: 'POST',
  })
  if (!res.ok) {
    throw new Error(`Failed to sync boards: ${res.statusText}`)
  }
  return res.json()
}

export async function createVoiceIssue(transcript: string, targetRepo?: string, autoAssign: boolean = true): Promise<any> {
  const res = await fetch('/api/issues/voice-create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ transcript, target_repo: targetRepo || undefined, auto_assign: autoAssign }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to create voice issue: ${res.statusText}`)
  }
  return res.json()
}

export async function restartIssueAgent(repo: string, issueNumber: number): Promise<any> {
  const res = await fetch('/api/issues/restart', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo, issue_number: issueNumber }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to restart agent: ${res.statusText}`)
  }
  return res.json()
}


