import React, { useState } from 'react'
import { useAgents } from '../../context/AgentContext'
import type { AgentSessionInfo } from '../../types/agent'

export const Sidebar: React.FC = () => {
  const { agents, selectedSessionId, selectSession, refreshAgents } = useAgents()
  const [filter, setFilter] = useState<'active' | 'archived' | 'all'>('active')

  const filteredAgents = agents.filter((agent) => {
    if (filter === 'active') return !agent.is_archived
    if (filter === 'archived') return agent.is_archived
    return true
  })

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'RUNNING':
        return <span className="status-tag tag-running">RUNNING</span>
      case 'IN_REVIEW':
        return <span className="status-tag tag-review">IN REVIEW</span>
      case 'COMPLETED':
        return <span className="status-tag tag-completed">DONE</span>
      case 'FAILED':
        return <span className="status-tag tag-failed">FAILED</span>
      case 'PAUSED':
        return <span className="status-tag tag-paused">PAUSED</span>
      default:
        return <span className="status-tag tag-idle">{status}</span>
    }
  }

  return (
    <aside className="agents-sidebar">
      <div className="sidebar-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <h2>Agent Sessions</h2>
          <span className="badge">{filteredAgents.length}</span>
        </div>
        <button className="btn-icon" onClick={() => refreshAgents()} title="Refresh Sessions">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
          </svg>
        </button>
      </div>

      <div className="sidebar-filters">
        <button
          className={`filter-tab ${filter === 'active' ? 'active' : ''}`}
          onClick={() => setFilter('active')}
        >
          Active
        </button>
        <button
          className={`filter-tab ${filter === 'archived' ? 'active' : ''}`}
          onClick={() => setFilter('archived')}
        >
          Archived
        </button>
        <button
          className={`filter-tab ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All
        </button>
      </div>

      <div className="sessions-list">
        {filteredAgents.length === 0 ? (
          <div className="empty-state">
            <p>No agents in this view.</p>
          </div>
        ) : (
          filteredAgents.map((a: AgentSessionInfo) => (
            <div
              key={a.session_id}
              className={`session-card ${selectedSessionId === a.session_id ? 'selected' : ''}`}
              onClick={() => selectSession(a.session_id)}
            >
              <div className="card-top">
                <span className="card-title" title={a.title}>
                  {a.issue_number ? `#${a.issue_number}: ` : ''}
                  {a.title}
                </span>
                {getStatusBadge(a.status)}
              </div>
              <div className="card-meta">
                <span>{a.repo}</span>
                <span>•</span>
                <span>{a.git_branch || 'no-branch'}</span>
              </div>
              <div className="card-footer">
                <span>Turns: {a.turn_count || 0}</span>
                <span>{(a.total_tokens || 0).toLocaleString()} tok</span>
              </div>
            </div>
          ))
        )}
      </div>
    </aside>
  )
}
