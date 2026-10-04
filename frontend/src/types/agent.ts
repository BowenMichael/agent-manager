export type AgentStatus =
  | 'IDLE'
  | 'INITIALIZING'
  | 'RUNNING'
  | 'PAUSED'
  | 'STOPPED'
  | 'IN_REVIEW'
  | 'COMPLETED'
  | 'FAILED'

export type MessageRole =
  | 'USER'
  | 'AGENT'
  | 'THOUGHT'
  | 'TOOL_CALL'
  | 'TOOL_RESULT'
  | 'SYSTEM'

export interface ConversationMessage {
  id: string
  role: MessageRole
  content: string
  timestamp: string
  tool_name?: string
  tool_args?: Record<string, unknown>
  tool_output?: string
}

export type WorkflowStage =
  | 'DIRECT'
  | 'SUMMARIZING'
  | 'PLANNING'
  | 'IMPLEMENTING'
  | 'COMPLETED'

export interface AgentSessionInfo {
  session_id: string
  repo: string
  issue_number?: number
  pr_url?: string
  pr_number?: number
  title: string
  status: AgentStatus
  worktree_path?: string
  git_branch?: string
  started_at: string
  updated_at: string
  turn_count: number
  max_turns: number
  token_count: number
  input_tokens: number
  output_tokens: number
  thinking_tokens: number
  total_tokens: number
  duration_seconds: number
  max_tokens: number
  quota_percent: number
  messages: ConversationMessage[]
  error_message?: string
  model?: string
  effort?: string
  current_activity?: string
  last_activity_at?: string
  is_stalled?: boolean
  quota_exceeded?: boolean
  quota_message?: string
  is_archived: boolean
  archived_at?: string
  workflow_stage?: WorkflowStage
}

export interface SpawnRequest {
  repo?: string
  issue_number?: number
  title?: string
  prompt: string
  worktree_branch?: string
  model?: string
  effort?: string
  workflow_pipeline_enabled?: boolean
}
