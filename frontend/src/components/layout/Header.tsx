import React from 'react'
import { useAgents } from '../../context/AgentContext'

interface HeaderProps {
  onOpenLaunchModal: () => void
}

export const Header: React.FC<HeaderProps> = ({ onOpenLaunchModal }) => {
  const { agents, isConnected } = useAgents()

  const activeCount = agents.filter((a) => !a.is_archived && a.status !== 'COMPLETED' && a.status !== 'STOPPED').length
  const completedCount = agents.filter((a) => a.status === 'COMPLETED' || a.is_archived).length
  const totalTokens = agents.reduce((sum, a) => sum + (a.total_tokens || 0), 0)

  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-logo">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
        </div>
        <div>
          <h1 className="brand-title">Agent Manager</h1>
          <span className="brand-subtitle">Google Antigravity SDK • Control Plane (React)</span>
        </div>
      </div>

      <div className="header-stats">
        <div className="stat-pill">
          <span className="stat-label">Active</span>
          <span className="stat-value active-val">{activeCount}</span>
        </div>
        <div className="stat-pill">
          <span className="stat-label">Completed</span>
          <span className="stat-value comp-val">{completedCount}</span>
        </div>
        <div className="stat-pill">
          <span className="stat-label">Tokens</span>
          <span className="stat-value token-val">{totalTokens.toLocaleString()}</span>
        </div>
      </div>

      <div className="header-actions">
        <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
          <span className="pulse-dot"></span>
          <span className="status-text">{isConnected ? 'Live Connected' : 'Disconnected'}</span>
        </div>
        <button className="btn btn-primary" onClick={onOpenLaunchModal}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          Launch Agent
        </button>
      </div>
    </header>
  )
}
