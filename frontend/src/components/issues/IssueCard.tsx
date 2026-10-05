import React, { useState } from 'react'
import type { IssueItem } from '../../types/issue'
import { startIssueAgent, pauseIssueAgent, stopIssueAgent, restartIssueAgent } from '../../services/apiClient'

interface IssueCardProps {
  issue: IssueItem
  onSelect: (issue: IssueItem) => void
  onRefresh: () => void
}

export const IssueCard: React.FC<IssueCardProps> = ({ issue, onSelect, onRefresh }) => {
  const [loading, setLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const active = issue.active_session
  const isRunning = active && active.status === 'RUNNING'
  const isPaused = active && active.status === 'PAUSED'
  const statusStr = issue.status || '📋 Ready for Agent'

  const handleStart = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setLoading(true)
    setActionError(null)
    try {
      await startIssueAgent(issue.repo, issue.number, issue.title, issue.body)
      setTimeout(onRefresh, 1000)
    } catch (err: any) {
      setActionError(err.message || 'Failed to start agent')
    } finally {
      setLoading(false)
    }
  }

  const handlePause = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setLoading(true)
    setActionError(null)
    try {
      await pauseIssueAgent(issue.repo, issue.number)
      setTimeout(onRefresh, 800)
    } catch (err: any) {
      setActionError(err.message || 'Failed to pause agent')
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setLoading(true)
    setActionError(null)
    try {
      await stopIssueAgent(issue.repo, issue.number)
      setTimeout(onRefresh, 800)
    } catch (err: any) {
      setActionError(err.message || 'Failed to stop agent')
    } finally {
      setLoading(false)
    }
  }

  const handleRestart = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setLoading(true)
    setActionError(null)
    try {
      await restartIssueAgent(issue.repo, issue.number)
      setTimeout(onRefresh, 1000)
    } catch (err: any) {
      setActionError(err.message || 'Failed to restart agent')
    } finally {
      setLoading(false)
    }
  }

  // Derive status badge styling
  let badgeClass = 'badge-ready'
  let displayStatus = 'Ready for Agent'
  if (statusStr.includes('Progress') || isRunning) {
    badgeClass = 'badge-progress'
    displayStatus = 'In Progress'
  } else if (statusStr.includes('Review')) {
    badgeClass = 'badge-review'
    displayStatus = 'In Review'
  } else if (statusStr.includes('Done')) {
    badgeClass = 'badge-done'
    displayStatus = 'Done'
  } else if (statusStr.includes('Backlog')) {
    badgeClass = 'badge-backlog'
    displayStatus = 'Backlog'
  }

  const repoShort = issue.repo.includes('/') ? issue.repo.split('/')[1] : issue.repo

  return (
    <div className={`issue-card ${isRunning ? 'issue-card-running' : ''}`} onClick={() => onSelect(issue)}>
      <div className="issue-card-header">
        <div className="issue-repo-meta">
          <span className="project-icon">{issue.project_icon || '📦'}</span>
          <span className="repo-pill">{repoShort}</span>
          <span className="issue-number">#{issue.number}</span>
        </div>
        <span className={`status-pill ${badgeClass}`}>
          {isRunning && <span className="pulse-dot"></span>}
          {displayStatus}
        </span>
      </div>

      <h3 className="issue-card-title">{issue.title}</h3>

      {/* High-Level Milestones */}
      <div className="milestone-track">
        <div className={`milestone-step ${issue.has_local_worktree ? 'completed' : isRunning ? 'active' : ''}`}>
          <span className="step-dot"></span>
          <span className="step-label">Worktree</span>
        </div>
        <div className="step-connector"></div>
        <div className={`milestone-step ${isRunning ? 'active' : active ? 'completed' : ''}`}>
          <span className="step-dot"></span>
          <span className="step-label">Code</span>
        </div>
        <div className="step-connector"></div>
        <div className={`milestone-step ${displayStatus === 'In Review' || displayStatus === 'Done' ? 'completed' : ''}`}>
          <span className="step-dot"></span>
          <span className="step-label">Tests</span>
        </div>
        <div className="step-connector"></div>
        <div className={`milestone-step ${displayStatus === 'In Review' || displayStatus === 'Done' ? 'completed' : ''}`}>
          <span className="step-dot"></span>
          <span className="step-label">Changelog</span>
        </div>
        <div className="step-connector"></div>
        <div className={`milestone-step ${displayStatus === 'Done' ? 'completed' : displayStatus === 'In Review' ? 'active' : ''}`}>
          <span className="step-dot"></span>
          <span className="step-label">PR</span>
        </div>
      </div>

      {/* Active Agent Info Banner */}
      {active && (
        <div className="issue-agent-banner">
          <div className="agent-indicator">
            <span className={`agent-dot ${isRunning ? 'dot-running' : 'dot-idle'}`}></span>
            <span className="agent-name">Agent: {active.model || 'Autonomous'}</span>
            <span className="agent-turns">Turns: {active.turn_count || 0}/15</span>
          </div>
          {active.branch && <span className="branch-tag">{active.branch}</span>}
        </div>
      )}

      {actionError && <div className="card-error-text">{actionError}</div>}

      {/* Direct Controls */}
      <div className="issue-card-actions">
        {isRunning ? (
          <>
            <button className="btn btn-warning btn-sm" onClick={handlePause} disabled={loading}>
              ⏸️ Pause
            </button>
            <button className="btn btn-outline btn-sm" onClick={handleRestart} disabled={loading} title="Wipe clean and restart fresh">
              🔄 Restart
            </button>
            <button className="btn btn-danger btn-sm" onClick={handleStop} disabled={loading}>
              ⏹️ Stop
            </button>
          </>
        ) : isPaused ? (
          <>
            <button className="btn btn-primary btn-sm" onClick={handleStart} disabled={loading}>
              ▶️ Resume
            </button>
            <button className="btn btn-outline btn-sm" onClick={handleRestart} disabled={loading} title="Wipe clean and restart fresh">
              🔄 Restart
            </button>
            <button className="btn btn-secondary btn-sm" onClick={handleStop} disabled={loading}>
              ⏹️ Stop
            </button>
          </>
        ) : (
          <>
            <button
              className={`btn ${displayStatus === 'Done' ? 'btn-secondary' : 'btn-primary'} btn-sm`}
              onClick={handleStart}
              disabled={loading}
            >
              {loading ? 'Starting...' : displayStatus === 'Done' ? '🔄 Re-run' : '🚀 Run Agent'}
            </button>
            {active && (
              <button className="btn btn-outline btn-sm" onClick={handleRestart} disabled={loading} title="Wipe clean and restart fresh">
                🔄 Restart
              </button>
            )}
          </>
        )}

        {issue.active_session?.pr_url && (
          <a
            href={issue.active_session.pr_url}
            target="_blank"
            rel="noreferrer"
            className="btn btn-outline btn-sm"
            onClick={(e) => e.stopPropagation()}
          >
            🔗 PR #{issue.active_session.pr_number || ''}
          </a>
        )}

        <button className="btn btn-ghost btn-sm card-details-btn" onClick={() => onSelect(issue)}>
          Details &rarr;
        </button>
      </div>
    </div>
  )
}
