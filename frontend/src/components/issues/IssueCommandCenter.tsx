import React, { useState, useEffect, useMemo } from 'react'
import type { IssueItem, IssuesResponse } from '../../types/issue'
import { fetchIssues, syncProjectBoards } from '../../services/apiClient'
import { CommandCenterHeader } from './CommandCenterHeader'
import { CommandCenterControls } from './CommandCenterControls'
import { IssueCard } from './IssueCard'
import { IssueDetailDrawer } from './IssueDetailDrawer'
import { VoiceIssueModal } from './VoiceIssueModal'
import './issues.css'

export const IssueCommandCenter: React.FC = () => {
  const [data, setData] = useState<IssuesResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isVoiceOpen, setIsVoiceOpen] = useState(false)

  // Filters
  const [selectedProject, setSelectedProject] = useState<string>('all')
  const [statusTab, setStatusTab] = useState<string>('active')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [selectedIssue, setSelectedIssue] = useState<IssueItem | null>(null)

  const loadData = async () => {
    try {
      setError(null)
      const res = await fetchIssues()
      setData(res)
    } catch (err: any) {
      setError(err.message || 'Failed to fetch issues')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 6000)
    return () => clearInterval(interval)
  }, [])

  const handleSync = async () => {
    setSyncing(true)
    try {
      await syncProjectBoards()
      await loadData()
    } catch (err: any) {
      setError(err.message || 'Sync failed')
    } finally {
      setSyncing(false)
    }
  }

  // Filter issues based on active tab, project, and search query
  const filteredIssues = useMemo(() => {
    if (!data?.issues) return []
    return data.issues.filter((issue) => {
      if (selectedProject !== 'all' && issue.project_id !== selectedProject && issue.repo !== selectedProject) {
        return false
      }

      const s = (issue.status || '').toLowerCase()
      const isRunning = issue.active_session && issue.active_session.status === 'RUNNING'

      if (statusTab === 'active') {
        if (s.includes('done')) return false
      } else if (statusTab === 'in_progress') {
        if (!s.includes('progress') && !isRunning) return false
      } else if (statusTab === 'ready') {
        if (!s.includes('ready')) return false
      } else if (statusTab === 'in_review') {
        if (!s.includes('review')) return false
      } else if (statusTab === 'done') {
        if (!s.includes('done')) return false
      }

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchesTitle = (issue.title || '').toLowerCase().includes(q)
        const matchesNum = String(issue.number).includes(q)
        const matchesRepo = (issue.repo || '').toLowerCase().includes(q)
        if (!matchesTitle && !matchesNum && !matchesRepo) return false
      }

      return true
    })
  }, [data, selectedProject, statusTab, searchQuery])

  const counts = data?.counts || {
    total_projects: 0,
    total_items: 0,
    ready: 0,
    in_progress: 0,
    in_review: 0,
    done: 0,
    active_agents: 0,
  }

  return (
    <div className="command-center-container">
      <CommandCenterHeader
        syncing={syncing}
        onSync={handleSync}
        onOpenVoice={() => setIsVoiceOpen(true)}
      />

      <CommandCenterControls
        selectedProject={selectedProject}
        setSelectedProject={setSelectedProject}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        statusTab={statusTab}
        setStatusTab={setStatusTab}
        projects={data?.projects}
        counts={counts}
      />

      {/* Main Grid Content */}
      <main className="cc-grid-content">
        {loading && !data ? (
          <div className="cc-loading-state">
            <div className="spinner"></div>
            <p>Loading project boards & agent statuses...</p>
          </div>
        ) : error ? (
          <div className="alert-box alert-error">
            <p>⚠️ {error}</p>
            <button className="btn btn-sm btn-outline" onClick={loadData}>Retry</button>
          </div>
        ) : filteredIssues.length === 0 ? (
          <div className="cc-empty-state">
            <div className="empty-emoji">📋</div>
            <h3>No issues found</h3>
            <p>
              {searchQuery
                ? `No issues match query "${searchQuery}"`
                : 'There are currently no issues in this view tab.'}
            </p>
          </div>
        ) : (
          <div className="issues-grid">
            {filteredIssues.map((issue) => (
              <IssueCard
                key={`${issue.repo}-${issue.number}`}
                issue={issue}
                onSelect={(selected) => setSelectedIssue(selected)}
                onRefresh={loadData}
              />
            ))}
          </div>
        )}
      </main>

      <IssueDetailDrawer
        issue={selectedIssue}
        onClose={() => setSelectedIssue(null)}
        onRefresh={loadData}
      />

      <VoiceIssueModal
        isOpen={isVoiceOpen}
        projects={data?.projects}
        onClose={() => setIsVoiceOpen(false)}
        onCreated={() => {
          setIsVoiceOpen(false)
          loadData()
        }}
      />
    </div>
  )
}
