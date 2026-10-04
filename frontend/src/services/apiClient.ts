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
