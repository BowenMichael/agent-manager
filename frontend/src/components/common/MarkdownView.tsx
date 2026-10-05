import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './markdown.css'

interface MarkdownViewProps {
  content: string
  className?: string
}

export const MarkdownView: React.FC<MarkdownViewProps> = ({ content, className = '' }) => {
  return (
    <div className={`markdown-view ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '')
            const codeString = String(children).replace(/\n$/, '')

            if (!inline && (match || codeString.includes('\n'))) {
              return <CodeBlock language={match ? match[1] : 'code'} code={codeString} />
            }

            return (
              <code className={className} {...props}>
                {children}
              </code>
            )
          },
          a({ node, children, href, ...props }: any) {
            return (
              <a href={href} target="_blank" rel="noreferrer" {...props}>
                {children}
              </a>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

interface CodeBlockProps {
  language: string
  code: string
}

const CodeBlock: React.FC<CodeBlockProps> = ({ language, code }) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        <span className="code-lang">{language}</span>
        <button className="code-copy-btn" onClick={handleCopy} type="button">
          {copied ? '✓ Copied' : 'Copy'}
        </button>
      </div>
      <pre>
        <code>{code}</code>
      </pre>
    </div>
  )
}
