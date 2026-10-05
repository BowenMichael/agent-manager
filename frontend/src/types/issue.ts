export interface ActiveSessionSummary {
  session_id: string
  status: string
  model?: string
  turn_count: number
  quota_percent: number
  is_stalled?: boolean
  branch?: string
  worktree?: string
  pr_url?: string
  pr_number?: number
  updated_at?: string
}

export interface IssueItem {
  id: string
  repo: string
  number: number
  title: string
  body?: string
  state?: string
  url?: string
  status: string
  board_title?: string
  board_url?: string
  active_session?: ActiveSessionSummary | null
  has_local_worktree?: boolean
  worktree_path?: string
  project_id?: string
  project_name?: string
  project_icon?: string
}

export interface ProjectSummary {
  id: string
  name: string
  repo: string
  icon: string
  counts: {
    ready: number
    in_progress: number
    in_review: number
    done: number
    backlog: number
    total: number
  }
  active_agents_count: number
}

export interface IssuesResponse {
  issues: IssueItem[]
  counts: {
    total_projects: number
    total_items: number
    ready: number
    in_progress: number
    in_review: number
    done: number
    active_agents: number
  }
  projects: ProjectSummary[]
}
