import type { AgentSessionInfo } from '../types/agent'

export type WebSocketMessage =
  | { type: 'init'; data: AgentSessionInfo[] }
  | { type: 'update'; data: AgentSessionInfo }
  | { type: 'ping' }
  | { type: 'pong' }

export class AgentWebSocketClient {
  private ws: WebSocket | null = null
  private onMessageCallback: (msg: WebSocketMessage) => void
  private onStatusChangeCallback: (connected: boolean) => void
  private reconnectTimeout: number | null = null
  private pingInterval: number | null = null
  private isDestroyed = false

  constructor(
    onMessage: (msg: WebSocketMessage) => void,
    onStatusChange: (connected: boolean) => void
  ) {
    this.onMessageCallback = onMessage
    this.onStatusChangeCallback = onStatusChange
  }

  connect() {
    if (this.isDestroyed) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/agents`

    try {
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        this.onStatusChangeCallback(true)
        this.startPing()
      }

      this.ws.onmessage = (event) => {
        try {
          if (event.data === 'pong') return
          const parsed = JSON.parse(event.data)
          this.onMessageCallback(parsed)
        } catch (e) {
          console.error('Failed to parse WS message:', e)
        }
      }

      this.ws.onclose = () => {
        this.onStatusChangeCallback(false)
        this.stopPing()
        this.scheduleReconnect()
      }

      this.ws.onerror = (err) => {
        console.warn('WS error:', err)
        this.ws?.close()
      }
    } catch (err) {
      console.error('WS connection error:', err)
      this.scheduleReconnect()
    }
  }

  private startPing() {
    this.stopPing()
    this.pingInterval = window.setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send('ping')
      }
    }, 15000)
  }

  private stopPing() {
    if (this.pingInterval !== null) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }

  private scheduleReconnect() {
    if (this.isDestroyed) return
    if (this.reconnectTimeout === null) {
      this.reconnectTimeout = window.setTimeout(() => {
        this.reconnectTimeout = null
        this.connect()
      }, 3000)
    }
  }

  disconnect() {
    this.isDestroyed = true
    this.stopPing()
    if (this.reconnectTimeout !== null) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}
