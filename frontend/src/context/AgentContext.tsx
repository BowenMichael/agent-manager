import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import type { AgentSessionInfo } from '../types/agent'
import { fetchAgents } from '../services/apiClient'
import { AgentWebSocketClient, type WebSocketMessage } from '../services/wsClient'

interface AgentContextType {
  agents: AgentSessionInfo[]
  selectedSessionId: string | null
  selectedAgent: AgentSessionInfo | null
  isConnected: boolean
  selectSession: (id: string | null) => void
  refreshAgents: () => Promise<void>
}

const AgentContext = createContext<AgentContextType | undefined>(undefined)

export const AgentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [agents, setAgents] = useState<AgentSessionInfo[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState<boolean>(false)

  const refreshAgents = useCallback(async () => {
    try {
      const data = await fetchAgents(true)
      setAgents(data)
    } catch (err) {
      console.error('Failed to load agents:', err)
    }
  }, [])

  useEffect(() => {
    refreshAgents()

    const handleMessage = (msg: WebSocketMessage) => {
      if (msg.type === 'init' && Array.isArray(msg.data)) {
        setAgents(msg.data)
      } else if (msg.type === 'update' && msg.data) {
        setAgents((prev) => {
          const index = prev.findIndex((a) => a.session_id === msg.data.session_id)
          if (index >= 0) {
            const updated = [...prev]
            updated[index] = msg.data
            return updated
          }
          return [msg.data, ...prev]
        })
      }
    }

    const wsClient = new AgentWebSocketClient(handleMessage, setIsConnected)
    wsClient.connect()

    return () => {
      wsClient.disconnect()
    }
  }, [refreshAgents])

  const selectedAgent = agents.find((a) => a.session_id === selectedSessionId) || null

  return (
    <AgentContext.Provider
      value={{
        agents,
        selectedSessionId,
        selectedAgent,
        isConnected,
        selectSession: setSelectedSessionId,
        refreshAgents,
      }}
    >
      {children}
    </AgentContext.Provider>
  )
}

export const useAgents = (): AgentContextType => {
  const context = useContext(AgentContext)
  if (!context) {
    throw new Error('useAgents must be used within an AgentProvider')
  }
  return context
}
