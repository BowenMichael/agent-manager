import React, { useState } from 'react'
import { useAgents } from './context/AgentContext'
import { Header } from './components/layout/Header'
import { Sidebar } from './components/layout/Sidebar'
import { StreamViewer } from './components/stream/StreamViewer'
import { DashboardOverview } from './components/dashboard/DashboardOverview'
import { AgentControls } from './components/control/AgentControls'
import { LaunchAgentModal } from './components/control/LaunchAgentModal'
import { IssueCommandCenter } from './components/issues/IssueCommandCenter'

export const App: React.FC = () => {
  const { selectedAgent } = useAgents()
  const [isLaunchOpen, setIsLaunchOpen] = useState(false)
  const [activeView, setActiveView] = useState<'issues' | 'sessions'>('issues')

  return (
    <div className="app-layout">
      <Header
        onOpenLaunchModal={() => setIsLaunchOpen(true)}
        activeView={activeView}
        onToggleView={(view) => setActiveView(view)}
      />

      {activeView === 'issues' ? (
        <IssueCommandCenter />
      ) : (
        <main className="main-workspace">
          <Sidebar />

          <section className="console-panel">
            {selectedAgent ? (
              <div className="console-active">
                <div className="session-header">
                  <div className="session-meta">
                    <div className="session-title-row">
                      <span className="status-tag tag-running">{selectedAgent.status}</span>
                      <h2>
                        {selectedAgent.issue_number ? `Issue #${selectedAgent.issue_number}: ` : ''}
                        {selectedAgent.title}
                      </h2>
                    </div>
                    <div className="session-submeta">
                      <span>{selectedAgent.repo}</span>
                      <span>•</span>
                      <span>{selectedAgent.git_branch || 'no-branch'}</span>
                      <span>•</span>
                      <span>{selectedAgent.model || 'gemini-3.8-flash'}</span>
                    </div>
                  </div>

                  <AgentControls agent={selectedAgent} />
                </div>

                <div className="console-body-split">
                  <StreamViewer agent={selectedAgent} />
                  <DashboardOverview agent={selectedAgent} />
                </div>
              </div>
            ) : (
              <div className="console-empty">
                <div className="console-empty-card">
                  <div className="empty-icon">⚡</div>
                  <h3>Select an Agent Session</h3>
                  <p>
                    Click on an active or past agent from the left sidebar to view its real-time thought
                    stream, tool calls, and conversation history.
                  </p>
                  <button className="btn btn-primary" onClick={() => setIsLaunchOpen(true)}>
                    Launch New Agent
                  </button>
                </div>
              </div>
            )}
          </section>
        </main>
      )}

      <LaunchAgentModal isOpen={isLaunchOpen} onClose={() => setIsLaunchOpen(false)} />
    </div>
  )
}

export default App
