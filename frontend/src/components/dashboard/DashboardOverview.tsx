import React from 'react'
import type { AgentSessionInfo } from '../../types/agent'

export const DashboardOverview: React.FC<{ agent: AgentSessionInfo }> = ({ agent }) => {
  const percent = Math.min(100, Math.round(((agent.total_tokens || 0) / (agent.max_tokens || 150000)) * 100))

  return (
    <div className="agent-overview-pane">
      <div className="overview-box">
        <div className="overview-box-header">
          <span className="overview-label">CURRENT ACTIVITY</span>
          <span className="badge-activity-running">{agent.current_activity || agent.status}</span>
        </div>
        <div className="activity-summary-text">{agent.title}</div>
        <div className="activity-sub-detail">
          {agent.worktree_path || 'Main worktree'} • {agent.git_branch || 'no branch'}
        </div>
      </div>

      <div className="overview-box usage-metrics-box">
        <div className="overview-box-header">
          <span className="overview-label">TOKEN METRICS</span>
          <span className="usage-badge-free">{agent.model || 'Default'}</span>
        </div>

        <div className="usage-primary-stat">
          <div className="usage-total-number">{(agent.total_tokens || 0).toLocaleString()}</div>
          <div className="usage-total-label">Total Tokens Processed</div>
        </div>

        <div className="quota-progress-container">
          <div className="quota-header">
            <span className="quota-label">SESSION BUDGET</span>
            <span className="quota-percentage">{percent}%</span>
          </div>
          <div className="quota-bar-track">
            <div className="quota-bar-fill" style={{ width: `${percent}%` }}></div>
          </div>
          <div className="quota-subtext">
            <span>
              {(agent.total_tokens || 0).toLocaleString()} / {(agent.max_tokens || 150000).toLocaleString()}
            </span>
          </div>
        </div>

        <div className="usage-breakdown-grid">
          <div className="usage-sub-stat">
            <span className="sub-stat-lbl">Input</span>
            <span className="sub-stat-val">{(agent.input_tokens || 0).toLocaleString()}</span>
          </div>
          <div className="usage-sub-stat">
            <span className="sub-stat-lbl">Output</span>
            <span className="sub-stat-val">{(agent.output_tokens || 0).toLocaleString()}</span>
          </div>
          <div className="usage-sub-stat">
            <span className="sub-stat-lbl">Reasoning</span>
            <span className="sub-stat-val">{(agent.thinking_tokens || 0).toLocaleString()}</span>
          </div>
          <div className="usage-sub-stat">
            <span className="sub-stat-lbl">Turns</span>
            <span className="sub-stat-val">{agent.turn_count || 0}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
