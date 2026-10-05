import React from 'react'
import type { ProjectInfo, GlobalCounts } from '../../types/issue'

interface CommandCenterControlsProps {
  selectedProject: string
  setSelectedProject: (proj: string) => void
  searchQuery: string
  setSearchQuery: (query: string) => void
  statusTab: string
  setStatusTab: (tab: string) => void
  projects?: ProjectInfo[]
  counts: GlobalCounts
}

export const CommandCenterControls: React.FC<CommandCenterControlsProps> = ({
  selectedProject,
  setSelectedProject,
  searchQuery,
  setSearchQuery,
  statusTab,
  setStatusTab,
  projects,
  counts,
}) => {
  return (
    <>
      {/* Control Bar: Project Selector, Search, Stats */}
      <div className="cc-control-bar">
        <div className="cc-filters-left">
          {/* Project Selector */}
          <div className="select-wrapper">
            <select
              className="cc-select"
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
            >
              <option value="all">All Projects ({counts.total_items})</option>
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.icon} {p.name} ({p.counts?.total || 0})
                </option>
              ))}
            </select>
          </div>

          {/* Search Input */}
          <div className="search-box">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              placeholder="Filter by issue # or title..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="search-input"
            />
            {searchQuery && (
              <button className="search-clear" onClick={() => setSearchQuery('')}>✕</button>
            )}
          </div>
        </div>

        {/* Global Stats Counter Pills */}
        <div className="cc-stats-pills">
          <span className="stat-pill pill-active">
            🟢 {counts.active_agents} Running Agents
          </span>
          <span className="stat-pill">
            📋 {counts.ready} Ready
          </span>
          <span className="stat-pill">
            🔍 {counts.in_review} In Review
          </span>
          <span className="stat-pill">
            ✅ {counts.done} Done
          </span>
        </div>
      </div>

      {/* Status Tabs Navigation */}
      <div className="cc-tabs-bar">
        <button
          className={`tab-btn ${statusTab === 'active' ? 'active' : ''}`}
          onClick={() => setStatusTab('active')}
        >
          ⚡ Active Queue ({counts.ready + counts.in_progress + counts.in_review})
        </button>
        <button
          className={`tab-btn ${statusTab === 'in_progress' ? 'active' : ''}`}
          onClick={() => setStatusTab('in_progress')}
        >
          🔥 In Progress ({counts.in_progress})
        </button>
        <button
          className={`tab-btn ${statusTab === 'ready' ? 'active' : ''}`}
          onClick={() => setStatusTab('ready')}
        >
          📋 Ready for Agent ({counts.ready})
        </button>
        <button
          className={`tab-btn ${statusTab === 'in_review' ? 'active' : ''}`}
          onClick={() => setStatusTab('in_review')}
        >
          🔍 In Review ({counts.in_review})
        </button>
        <button
          className={`tab-btn ${statusTab === 'done' ? 'active' : ''}`}
          onClick={() => setStatusTab('done')}
        >
          ✅ Done ({counts.done})
        </button>
      </div>
    </>
  )
}
