import React from 'react'
import { useAuth } from '../../context/AuthContext'

export const LoginPage: React.FC = () => {
  const { login } = useAuth()

  return (
    <div className="login-container">
      <div className="login-backdrop-glow"></div>
      <div className="login-card glass-panel">
        <div className="login-header">
          <div className="login-logo-badge">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <h1 className="login-title">Agent Manager</h1>
          <p className="login-subtitle">Google Antigravity SDK • Live Autonomous Control Plane</p>
        </div>

        <div className="login-body">
          <div className="login-info-box">
            <div className="info-icon">🔒</div>
            <div className="info-text">
              <strong>Secured Access Gateway</strong>
              <p>Authentication is enforced. Please sign in with an authorized GitHub account to manage autonomous agents.</p>
            </div>
          </div>

          <button className="btn btn-github-login" onClick={login}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
            <span>Sign in with GitHub</span>
          </button>
        </div>

        <div className="login-footer">
          <div className="auth-policy-tag">
            <span className="policy-dot"></span>
            <span>Policy: Authorized Collaborators Only</span>
          </div>
        </div>
      </div>
    </div>
  )
}
