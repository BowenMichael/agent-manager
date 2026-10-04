import React from 'react'
import type { ConversationMessage } from '../../types/agent'

export const LogMessage: React.FC<{ message: ConversationMessage }> = ({ message }) => {
  const isTool = message.role === 'TOOL_CALL' || message.role === 'TOOL_RESULT'
  const isAgent = message.role === 'AGENT'
  const isUser = message.role === 'USER'
  const isThought = message.role === 'THOUGHT'

  let roleClass = 'role-system'
  if (isAgent) roleClass = 'role-agent'
  if (isUser) roleClass = 'role-user'
  if (isTool) roleClass = 'role-tool'
  if (isThought) roleClass = 'role-thought'

  return (
    <div className={`message-item ${roleClass}`}>
      <div className="message-header">
        <span className="message-role-tag">{message.role}</span>
        {message.tool_name && <span className="message-tool-tag">{message.tool_name}</span>}
        <span className="message-time">
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      </div>

      {message.content && <div className="message-content">{message.content}</div>}

      {message.tool_args && (
        <details className="tool-details">
          <summary>Arguments</summary>
          <pre>{JSON.stringify(message.tool_args, null, 2)}</pre>
        </details>
      )}

      {message.tool_output && (
        <details className="tool-details">
          <summary>Output</summary>
          <pre>{message.tool_output}</pre>
        </details>
      )}
    </div>
  )
}
