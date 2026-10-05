import React, { useState, useEffect } from 'react'
import type { IssueItem } from '../../types/issue'
import { startIssueAgent, pauseIssueAgent, stopIssueAgent, restartIssueAgent } from '../../services/apiClient'
import { MarkdownView } from '../common/MarkdownView'

interface IssueDetailDrawerProps {
  issue: IssueItem | null
  onClose: () => void
  onRefresh: () => void
}

export const IssueDetailDrawer: React.FC<IssueDetailDrawerProps> = ({ issue, onClose, onRefresh }) => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && issue) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [issue, onClose])

  if (!issue) return null

  const active = issue.active_session
  const isRunning = active && active.status === 'RUNNING'
  const isPaused = active && active.status === 'PAUSED'

  const handleStart = async () => {
    setLoading(true)
    setError(null)
    try {
      await startIssueAgent(issue.repo, issue.number, issue.title, issue.body)
      setTimeout(onRefresh, 1000)
    } catch (err: any) {
      setError(err.message || 'Failed to start agent')
    } finally {
      setLoading(false)
    }
  }

  const handlePause = async () => {
    setLoading(true)
    setError(null)
    try {
      await pauseIssueAgent(issue.repo, issue.number)
      setTimeout(onRefresh, 800)
    } catch (err: any) {
      setError(err.message || 'Failed to pause agent')
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    setLoading(true)
    setError(null)
    try {
      await stopIssueAgent(issue.repo, issue.number)
      setTimeout(onRefresh, 800)
    } catch (err: any) {
      setError(err.message || 'Failed to stop agent')
    } finally {
      setLoading(false)
    }
  }

  const handleRestart = async () => {
    setLoading(true)
    setError(null)
    try {
      await restartIssueAgent(issue.repo, issue.number)
      setTimeout(onRefresh, 1000)
    } catch (err: any) {
      setError(err.message || 'Failed to restart agent')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-content" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div className="drawer-title-area">
            <span className="repo-pill">{issue.repo}</span>
            <h2>Issue #{issue.number}: {issue.title}</h2>
          </div>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <div className="drawer-body">
          {error && <div className="alert-box alert-error">{error}</div>}

          {/* Quick Actions */}
          <div className="drawer-actions-bar">
            {isRunning ? (
              <>
                <button className="btn btn-warning" onClick={handlePause} disabled={loading}>
                  ⏸️ Pause Agent
                </button>
                <button className="btn btn-outline" onClick={handleRestart} disabled={loading} title="Wipe clean and restart fresh">
                  🔄 Restart Agent
                </button>
                <button className="btn btn-danger" onClick={handleStop} disabled={loading}>
                  ⏹️ Stop Agent
                </button>
              </>
            ) : isPaused ? (
              <>
                <button className="btn btn-primary" onClick={handleStart} disabled={loading}>
                  ▶️ Resume Agent
                </button>
                <button className="btn btn-outline" onClick={handleRestart} disabled={loading} title="Wipe clean and restart fresh">
                  🔄 Restart Agent
                </button>
                <button className="btn btn-danger" onClick={handleStop} disabled={loading}>
                  ⏹️ Stop Agent
                </button>
              </>
            ) : (
              <>
                <button className="btn btn-primary" onClick={handleStart} disabled={loading}>
                  {loading ? 'Starting...' : '🚀 Launch Agent'}
                </button>
                {active && (
                  <button className="btn btn-outline" onClick={handleRestart} disabled={loading} title="Wipe clean and restart fresh">
                    🔄 Restart Agent
                  </button>
                )}
              </>
            )}

            {issue.url && (
              <a href={issue.url} target="_blank" rel="noreferrer" className="btn btn-outline">
                View on GitHub ↗
              </a>
            )}
          </div>

          {/* Supervisor Governance Checklist */}
          <div className="governance-panel">
            <h3>🛡️ Supervisor Governance Status</h3>
            <div className="gov-grid">
              <div className="gov-item">
                <span className="gov-label">Worktree Sandbox:</span>
                <span className={`gov-val ${issue.has_local_worktree ? 'val-good' : 'val-warn'}`}>
                  {issue.has_local_worktree ? '✅ Isolated Worktree Created' : '⚪ Not Initialized'}
                </span>
              </div>
              <div className="gov-item">
                <span className="gov-label">Target Branch:</span>
                <span className="gov-val">{active?.branch || `feat/issue-${issue.number}`}</span>
              </div>
              <div className="gov-item">
                <span className="gov-label">Turn Budget Guardrail:</span>
                <span className="gov-val">{active?.turn_count || 0} / 15 max turns</span>
              </div>
              <div className="gov-item">
                <span className="gov-label">Board Status:</span>
                <span className="gov-val">{issue.status || '📋 Ready for Agent'}</span>
              </div>
              <div className="gov-item">
                <span className="gov-label">Local Worktree Path:</span>
                <span className="gov-val gov-path">{issue.worktree_path || 'None'}</span>
              </div>
            </div>
          </div>

          {/* Description Section with Rich Markdown Support */}
          <div className="issue-desc-section">
            <h3>📋 Requirements & Description</h3>
            <div className="desc-box">
              {issue.body ? (
                <MarkdownView content={issue.body} />
              ) : (
                <p className="text-muted">No description provided in this issue.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
