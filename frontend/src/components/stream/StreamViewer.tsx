import React, { useEffect, useRef, useState } from 'react'
import type { AgentSessionInfo } from '../../types/agent'
import { LogMessage } from './LogMessage'
import { addContext } from '../../services/apiClient'

interface StreamViewerProps {
  agent: AgentSessionInfo
}

export const StreamViewer: React.FC<StreamViewerProps> = ({ agent }) => {
  const [contextText, setContextText] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const streamBottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    streamBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [agent.messages])

  const handleSendContext = async () => {
    if (!contextText.trim() || isSubmitting) return
    setIsSubmitting(true)
    try {
      await addContext(agent.session_id, contextText)
      setContextText('')
    } catch (err) {
      alert(`Failed to send context: ${err}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      handleSendContext()
    }
  }

  return (
    <div className="stream-main-pane">
      <div className="stream-header-strip">
        <div className="strip-left">
          <span>Live Tool & Execution Stream</span>
        </div>
        <div className="strip-right">
          <span className="pulse-indicator">
            <span className="dot"></span>
            {agent.status === 'RUNNING' ? 'LIVE' : agent.status}
          </span>
        </div>
      </div>

      <div className="transcript-viewport">
        <div className="transcript-stream">
          {(!agent.messages || agent.messages.length === 0) ? (
            <div className="empty-stream">
              <p>No messages or activity logged yet.</p>
            </div>
          ) : (
            agent.messages.map((m) => <LogMessage key={m.id} message={m} />)
          )}
          <div ref={streamBottomRef} />
        </div>
      </div>

      <div className="context-bar">
        <div className="context-input-wrapper">
          <textarea
            value={contextText}
            onChange={(e) => setContextText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Inject feedback or instructions... (Ctrl+Enter to send)"
            rows={2}
          />
          <button
            className="btn btn-primary btn-send-context"
            onClick={handleSendContext}
            disabled={isSubmitting || !contextText.trim()}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
