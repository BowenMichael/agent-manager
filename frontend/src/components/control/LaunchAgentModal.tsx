import React, { useState } from 'react'
import { spawnAgent } from '../../services/apiClient'
import { useAgents } from '../../context/AgentContext'

interface LaunchModalProps {
  isOpen: boolean
  onClose: () => void
}

export const LaunchAgentModal: React.FC<LaunchModalProps> = ({ isOpen, onClose }) => {
  const { selectSession, refreshAgents } = useAgents()
  const [repo, setRepo] = useState('BowenMichael/agent-manager')
  const [issueNumber, setIssueNumber] = useState<string>('')
  const [title, setTitle] = useState('')
  const [prompt, setPrompt] = useState('')
  const [model, setModel] = useState('gemini-3.8-flash')
  const [effort, setEffort] = useState('high')
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!prompt.trim() || isSubmitting) return

    setIsSubmitting(true)
    try {
      const newSession = await spawnAgent({
        repo: repo.trim(),
        issue_number: issueNumber ? parseInt(issueNumber, 10) : undefined,
        title: title.trim() || undefined,
        prompt: prompt.trim(),
        model,
        effort,
      })
      await refreshAgents()
      selectSession(newSession.session_id)
      onClose()
    } catch (err) {
      alert(`Failed to launch agent: ${err}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <div className="modal-header">
          <h3>Launch Autonomous Agent</h3>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-group">
              <label>Target Repository</label>
              <input
                type="text"
                className="form-control"
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label>Issue Number (Optional)</label>
              <input
                type="number"
                className="form-control"
                value={issueNumber}
                onChange={(e) => setIssueNumber(e.target.value)}
                placeholder="e.g. 75"
              />
            </div>
            <div className="form-group">
              <label>Session Title (Optional)</label>
              <input
                type="text"
                className="form-control"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Implement React frontend"
              />
            </div>
            <div className="form-group">
              <label>Model & Effort</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <select
                  className="form-control"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                >
                  <option value="gemini-3.8-flash">Gemini 3.8 Flash</option>
                  <option value="gemini-3.1-pro">Gemini 3.1 Pro</option>
                  <option value="claude-sonnet-5-5">Claude Sonnet 5.5</option>
                </select>
                <select
                  className="form-control"
                  value={effort}
                  onChange={(e) => setEffort(e.target.value)}
                >
                  <option value="low">Low Effort</option>
                  <option value="medium">Medium Effort</option>
                  <option value="high">High Effort</option>
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>Task Instructions / Prompt</label>
              <textarea
                className="form-control"
                rows={4}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Specify task instructions, requirements, and files..."
                required
              />
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Spawning...' : 'Spawn Agent'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
