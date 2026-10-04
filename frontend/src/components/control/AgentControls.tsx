import React from 'react'
import type { AgentSessionInfo } from '../../types/agent'
import { stopAgent, restartAgent, completeAgent, archiveAgent, unarchiveAgent } from '../../services/apiClient'
import { useAgents } from '../../context/AgentContext'

interface AgentControlsProps {
  agent: AgentSessionInfo
}

export const AgentControls: React.FC<AgentControlsProps> = ({ agent }) => {
  const { refreshAgents } = useAgents()

  const handleStop = async () => {
    try {
      await stopAgent(agent.session_id)
      await refreshAgents()
    } catch (e) {
      alert(`Error stopping agent: ${e}`)
    }
  }

  const handleRestart = async () => {
    try {
      await restartAgent(agent.session_id)
      await refreshAgents()
    } catch (e) {
      alert(`Error restarting agent: ${e}`)
    }
  }

  const handleComplete = async () => {
    try {
      await completeAgent(agent.session_id)
      await refreshAgents()
    } catch (e) {
      alert(`Error completing agent: ${e}`)
    }
  }

  const handleArchiveToggle = async () => {
    try {
      if (agent.is_archived) {
        await unarchiveAgent(agent.session_id)
      } else {
        await archiveAgent(agent.session_id)
      }
      await refreshAgents()
    } catch (e) {
      alert(`Error archiving agent: ${e}`)
    }
  }

  return (
    <div className="session-controls">
      <button className="btn btn-secondary" onClick={handleRestart} title="Restart Agent">
        Restart
      </button>
      <button className="btn btn-secondary" onClick={handleArchiveToggle} title="Archive/Unarchive">
        {agent.is_archived ? 'Unarchive' : 'Archive'}
      </button>
      {agent.status !== 'COMPLETED' && (
        <button className="btn btn-success" onClick={handleComplete} title="Mark as Done">
          Mark Done
        </button>
      )}
      {agent.status === 'RUNNING' && (
        <button className="btn btn-danger" onClick={handleStop} title="Stop Agent">
          Stop
        </button>
      )}
    </div>
  )
}
