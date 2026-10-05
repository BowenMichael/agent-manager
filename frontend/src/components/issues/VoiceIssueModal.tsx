import React, { useState, useEffect } from 'react'
import { createVoiceIssue } from '../../services/apiClient'
import type { ProjectSummary } from '../../types/issue'
import { useSpeechRecognition } from './useSpeechRecognition'

interface VoiceIssueModalProps {
  isOpen: boolean
  projects?: ProjectSummary[]
  onClose: () => void
  onCreated: () => void
}

export const VoiceIssueModal: React.FC<VoiceIssueModalProps> = ({
  isOpen,
  projects = [],
  onClose,
  onCreated,
}) => {
  const [transcript, setTranscript] = useState('')
  const [selectedRepo, setSelectedRepo] = useState<string>('')
  const [autoAssign, setAutoAssign] = useState<boolean>(true)
  const [processing, setProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successInfo, setSuccessInfo] = useState<any | null>(null)

  const { isListening, stopListening, toggleListening } = useSpeechRecognition()

  useEffect(() => {
    if (!isOpen) {
      stopListening()
      setTranscript('')
      setError(null)
      setSuccessInfo(null)
      setProcessing(false)
    }
  }, [isOpen, stopListening])

  const handleToggleListening = () => {
    setError(null)
    toggleListening(
      (newTranscript) => setTranscript(newTranscript),
      (err) => setError(err)
    )
  }

  const handleCreate = async () => {
    if (!transcript.trim()) {
      setError('Please speak or type the issue description first.')
      return
    }
    stopListening()
    setProcessing(true)
    setError(null)

    try {
      const result = await createVoiceIssue(transcript, selectedRepo || undefined, autoAssign)
      setSuccessInfo(result)
      setTimeout(() => {
        onCreated()
      }, 600)
    } catch (err: any) {
      setError(err.message || 'Failed to create voice issue.')
    } finally {
      setProcessing(false)
    }
  }

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="voice-modal-overlay" onClick={onClose}>
      <div className="voice-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="voice-modal-header">
          <div className="voice-header-title">
            <span className="voice-header-icon">🎙️</span>
            <div>
              <h2>Voice Issue Listener</h2>
              <p>Speak your feature request or bug report — AI will detail it and assign an agent.</p>
            </div>
          </div>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <div className="voice-modal-body">
          {error && <div className="alert-box alert-error">{error}</div>}

          {/* Success Banner */}
          {successInfo && (
            <div className="alert-box alert-success">
              <h4>✅ Issue #{successInfo.number} Created Successfully!</h4>
              <p><strong>Title:</strong> {successInfo.title}</p>
              <p><strong>Repo:</strong> {successInfo.repo}</p>
              {successInfo.auto_assigned && (
                <p>⚡ <strong>Agent Assigned:</strong> Operating in isolated worktree <code>{successInfo.worktree || 'active'}</code></p>
              )}
              {successInfo.url && (
                <a href={successInfo.url} target="_blank" rel="noreferrer" className="btn btn-sm btn-outline mt-2">
                  View on GitHub ↗
                </a>
              )}
            </div>
          )}

          {/* Microphone Visualizer / Action Box */}
          <div className={`voice-listener-box ${isListening ? 'listening-active' : ''}`}>
            <button
              className={`mic-record-btn ${isListening ? 'mic-recording' : ''}`}
              onClick={handleToggleListening}
              type="button"
            >
              <span className="mic-icon">{isListening ? '🛑' : '🎙️'}</span>
              <span className="mic-status-text">
                {isListening ? 'Listening... (Click to stop)' : 'Click to Start Speaking'}
              </span>
            </button>
            {isListening && <div className="audio-wave-anim"><span></span><span></span><span></span><span></span><span></span></div>}
          </div>

          {/* Live Transcript / Manual Input Area */}
          <div className="transcript-section">
            <label className="input-label">
              <span>Spoken Transcript / Issue Details</span>
              <span className="input-hint">(Live transcribed — you can edit anytime)</span>
            </label>
            <textarea
              className="transcript-textarea"
              placeholder="e.g. In FitElo, add a workout rest timer with an audio beep after each completed set..."
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              rows={4}
            />
          </div>

          {/* Target Project & Auto-assign options */}
          <div className="voice-options-row">
            <div className="option-field">
              <label className="input-label">Target Repository</label>
              <select
                className="cc-select"
                value={selectedRepo}
                onChange={(e) => setSelectedRepo(e.target.value)}
              >
                <option value="">✨ Auto-detect from voice</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.repo}>
                    {p.icon} {p.name} ({p.repo})
                  </option>
                ))}
              </select>
            </div>

            <div className="option-field checkbox-field">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={autoAssign}
                  onChange={(e) => setAutoAssign(e.target.checked)}
                />
                <span>⚡ Auto-assign agent immediately</span>
              </label>
            </div>
          </div>
        </div>

        <div className="voice-modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={processing}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleCreate}
            disabled={processing || !transcript.trim()}
          >
            {processing ? '⏳ Structuring & Assigning Issue...' : '🚀 Create & Assign Issue'}
          </button>
        </div>
      </div>
    </div>
  )
}
