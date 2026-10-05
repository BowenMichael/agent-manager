import React, { useState } from 'react'
import './feedback.css'

interface AgentFeedbackWidgetProps {
  appName?: string
  targetRepo?: string
  apiBase?: string
}

export const AgentFeedbackWidget: React.FC<AgentFeedbackWidgetProps> = ({
  appName = 'agent-manager',
  targetRepo,
  apiBase = '',
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const [feedbackType, setFeedbackType] = useState<'bug' | 'feature' | 'ux_polish'>('bug')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [userEmail, setUserEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [successInfo, setSuccessInfo] = useState<{ number: number; url?: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !description.trim()) {
      setError('Please provide both a title and description.')
      return
    }

    setSubmitting(true)
    setError(null)

    const payload = {
      app_name: appName,
      target_repo: targetRepo,
      feedback_type: feedbackType,
      title,
      description,
      route: typeof window !== 'undefined' ? window.location.pathname : undefined,
      user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : undefined,
      viewport: typeof window !== 'undefined' ? { width: window.innerWidth, height: window.innerHeight } : undefined,
      user_email: userEmail.trim() || undefined,
      auto_assign: true,
    }

    try {
      const res = await fetch(`${apiBase}/api/feedback/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to submit feedback')
      }
      setSuccessInfo({ number: data.issue_number, url: data.url })
      setTitle('')
      setDescription('')
    } catch (err: any) {
      setError(err.message || 'Error submitting feedback')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <button
        className="feedback-floating-btn"
        onClick={() => {
          setIsOpen(true)
          setSuccessInfo(null)
          setError(null)
        }}
        aria-label="Send Feedback or Report Bug"
      >
        <span>💬 Feedback</span>
      </button>

      {isOpen && (
        <div className="feedback-modal-overlay" onClick={() => setIsOpen(false)}>
          <div className="feedback-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="feedback-modal-header">
              <h3>⚡ Quick Feedback & Bug Report</h3>
              <button className="btn-close" onClick={() => setIsOpen(false)}>✕</button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="feedback-modal-body">
                {error && <div className="alert-box alert-error">{error}</div>}
                {successInfo && (
                  <div className="alert-box alert-success">
                    ✅ Issue #{successInfo.number} created and queued in Ready for Agent!
                    {successInfo.url && (
                      <a href={successInfo.url} target="_blank" rel="noreferrer" className="block text-xs underline mt-1">
                        View on GitHub ↗
                      </a>
                    )}
                  </div>
                )}

                <div className="feedback-type-tabs">
                  <button
                    type="button"
                    className={`feedback-type-btn ${feedbackType === 'bug' ? 'active' : ''}`}
                    onClick={() => setFeedbackType('bug')}
                  >
                    🐞 Bug
                  </button>
                  <button
                    type="button"
                    className={`feedback-type-btn ${feedbackType === 'feature' ? 'active' : ''}`}
                    onClick={() => setFeedbackType('feature')}
                  >
                    ✨ Feature
                  </button>
                  <button
                    type="button"
                    className={`feedback-type-btn ${feedbackType === 'ux_polish' ? 'active' : ''}`}
                    onClick={() => setFeedbackType('ux_polish')}
                  >
                    🎨 UX Polish
                  </button>
                </div>

                <input
                  type="text"
                  className="feedback-input"
                  placeholder="Short issue title..."
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                />

                <textarea
                  className="feedback-textarea"
                  placeholder="Describe what happened, expected behavior, or your idea..."
                  rows={4}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  required
                />

                <input
                  type="email"
                  className="feedback-input"
                  placeholder="Your email (optional, for notifications)..."
                  value={userEmail}
                  onChange={(e) => setUserEmail(e.target.value)}
                />

                <div className="feedback-telemetry-badge">
                  📍 Auto-capturing route `{typeof window !== 'undefined' ? window.location.pathname : '/'}` & diagnostics
                </div>
              </div>

              <div className="feedback-modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setIsOpen(false)}>
                  Close
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Submitting...' : 'Send to Agent Swarm'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
