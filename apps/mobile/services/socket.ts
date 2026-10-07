/**
 * Real-Time WebSocket Client for Expo Mobile App.
 * Connects to /ws/agents with exponential backoff auto-reconnection.
 * Adheres strictly to Anti-Monolith guidelines (< 250 lines, < 40 lines per function).
 */

import { WS_BASE_URL } from '../constants/Config';

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';
export type SocketEventHandler = (payload: any) => void;

export class AgentSocketClient {
  private ws: WebSocket | null = null;
  private reconnectAttempt = 0;
  private maxReconnectDelay = 30000;
  private baseDelay = 1000;
  private listeners: Map<string, Set<SocketEventHandler>> = new Map();
  private statusListeners: Set<(status: ConnectionStatus) => void> = new Set();
  private status: ConnectionStatus = 'disconnected';
  private shouldReconnect = true;

  constructor(private url: string = WS_BASE_URL) {}

  public getStatus(): ConnectionStatus {
    return this.status;
  }

  public connect(authToken?: string) {
    this.shouldReconnect = true;
    this.updateStatus('connecting');
    const wsUrl = authToken ? `${this.url}?token=${encodeURIComponent(authToken)}` : this.url;
    
    try {
      this.ws = new WebSocket(wsUrl);
      this.bindSocketEvents();
    } catch (err) {
      this.handleSocketClose();
    }
  }

  private bindSocketEvents() {
    if (!this.ws) return;

    this.ws.onopen = () => {
      this.reconnectAttempt = 0;
      this.updateStatus('connected');
    };

    this.ws.onmessage = (event) => {
      this.handleMessage(event.data);
    };

    this.ws.onclose = () => {
      this.handleSocketClose();
    };

    this.ws.onerror = () => {
      if (this.ws) this.ws.close();
    };
  }

  private handleMessage(rawData: any) {
    try {
      const parsed = typeof rawData === 'string' ? JSON.parse(rawData) : rawData;
      const eventType = parsed.type || 'message';
      const callbacks = this.listeners.get(eventType);
      if (callbacks) {
        callbacks.forEach((cb) => cb(parsed.data ?? parsed));
      }
    } catch (e) {
      // Ignored non-json messages
    }
  }

  private handleSocketClose() {
    this.ws = null;
    if (!this.shouldReconnect) {
      this.updateStatus('disconnected');
      return;
    }
    this.updateStatus('reconnecting');
    const delay = Math.min(
      this.baseDelay * Math.pow(2, this.reconnectAttempt),
      this.maxReconnectDelay
    );
    this.reconnectAttempt++;
    setTimeout(() => {
      if (this.shouldReconnect) this.connect();
    }, delay);
  }

  private updateStatus(newStatus: ConnectionStatus) {
    this.status = newStatus;
    this.statusListeners.forEach((cb) => cb(newStatus));
  }

  public on(event: string, handler: SocketEventHandler): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(handler);
    return () => this.listeners.get(event)?.delete(handler);
  }

  public onStatusChange(handler: (status: ConnectionStatus) => void): () => void {
    this.statusListeners.add(handler);
    return () => this.statusListeners.delete(handler);
  }

  public disconnect() {
    this.shouldReconnect = false;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.updateStatus('disconnected');
  }
}

export const agentSocket = new AgentSocketClient();
