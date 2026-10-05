import React from 'react'

interface CommandCenterHeaderProps {
  syncing: boolean
  onSync: () => void
  onOpenVoice: () => void
}

export const CommandCenterHeader: React.FC<CommandCenterHeaderProps> = ({
  syncing,
  onSync,
  onOpenVoice,
}) => {
  return (
    <header className="cc-header">
      <div className="cc-title-area">
        <div className="cc-logo-badge">🎯</div>
        <div>
          <h1 className="cc-title">Issue Command Center</h1>
          <p className="cc-subtitle">Direct autonomous agent control, milestone tracking & board synchronization</p>
        </div>
      </div>

      <div className="cc-header-actions">
        <button className="btn btn-success" onClick={onOpenVoice}>
          🎙️ Voice Issue
        </button>
        <button className="btn btn-primary" onClick={onSync} disabled={syncing}>
          {syncing ? '🔄 Syncing Boards...' : '🔄 Sync GitHub Boards'}
        </button>
      </div>
    </header>
  )
}
