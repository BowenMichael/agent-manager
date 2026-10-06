import React from 'react'
import { useAgents } from '../../context/AgentContext'
import { useAuth } from '../../context/AuthContext'

interface HeaderProps {
  onOpenLaunchModal: () => void
  activeView: 'issues' | 'sessions'
  onToggleView: (view: 'issues' | 'sessions') => void
}

export const Header: React.FC<HeaderProps> = ({ onOpenLaunchModal, activeView, onToggleView }) => {
  const { agents, isConnected } = useAgents()
  const { user, authEnabled, logout } = useAuth()

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
          <span className="brand-subtitle">Google Antigravity SDK • Control Plane</span>
        </div>
      </div>

      <div className="header-nav-tabs">
        <button
          className={`nav-tab-btn ${activeView === 'issues' ? 'active' : ''}`}
          onClick={() => onToggleView('issues')}
        >
          🎯 Issue Command Center
        </button>
        <button
          className={`nav-tab-btn ${activeView === 'sessions' ? 'active' : ''}`}
          onClick={() => onToggleView('sessions')}
        >
          ⚡ Agent Sessions & Console
        </button>
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

        {authEnabled && user ? (
          <div className="user-profile-pill">
            {user.avatar_url ? (
              <img src={user.avatar_url} alt={user.username} className="user-avatar-img" />
            ) : (
              <div className="user-avatar-placeholder">👤</div>
            )}
            <span className="user-name-tag">@{user.username}</span>
            <button className="btn-logout" onClick={logout} title="Sign Out">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
            </button>
          </div>
        ) : !authEnabled ? (
          <div className="local-mode-pill" title="Authentication disabled / Local development mode">
            <span className="local-dot"></span>
            <span>Local Mode</span>
          </div>
        ) : null}

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
