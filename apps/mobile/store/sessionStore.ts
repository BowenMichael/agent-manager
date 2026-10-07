/**
 * Mobile Session State Store.
 * Manages active and historical agent sessions, live WebSocket state, and optimistic updates.
 * Adheres strictly to Anti-Monolith guidelines (< 250 lines, < 40 lines per function).
 */

import { API_BASE_URL } from '../constants/Config';
import { agentSocket, ConnectionStatus } from '../services/socket';

export interface MobileAgentSession {
  session_id: string;
  repo: string;
  issue_number?: number;
  status: 'running' | 'paused' | 'in_review' | 'completed' | 'stopped' | 'failed';
  current_activity?: string;
  total_tokens?: number;
  total_cost_usd?: number;
  created_at: string;
  last_activity_at?: string;
}

export type StatusFilter = 'all' | 'active' | 'in_review' | 'completed' | 'failed';

export class SessionStore {
  private sessions: Map<string, MobileAgentSession> = new Map();
  private listeners: Set<() => void> = new Set();
  private connectionStatus: ConnectionStatus = 'disconnected';
  private statusFilter: StatusFilter = 'all';

  constructor() {
    this.bindSocketEvents();
  }

  private bindSocketEvents() {
    agentSocket.onStatusChange((status) => {
      this.connectionStatus = status;
      this.notify();
    });

    agentSocket.on('init', (data: MobileAgentSession[]) => {
      if (Array.isArray(data)) {
        this.sessions.clear();
        data.forEach((s) => this.sessions.set(s.session_id, s));
        this.notify();
      }
    });

    agentSocket.on('session_updated', (session: MobileAgentSession) => {
      if (session && session.session_id) {
        this.sessions.set(session.session_id, session);
        this.notify();
      }
    });
  }

  public getSessions(): MobileAgentSession[] {
    const list = Array.from(this.sessions.values()).sort((a, b) =>
      new Date(b.last_activity_at || b.created_at).getTime() -
      new Date(a.last_activity_at || a.created_at).getTime()
    );

    if (this.statusFilter === 'active') {
      return list.filter((s) => s.status === 'running' || s.status === 'paused');
    }
    if (this.statusFilter === 'in_review') {
      return list.filter((s) => s.status === 'in_review');
    }
    if (this.statusFilter === 'completed') {
      return list.filter((s) => s.status === 'completed');
    }
    if (this.statusFilter === 'failed') {
      return list.filter((s) => s.status === 'failed' || s.status === 'stopped');
    }
    return list;
  }

  public getSession(id: string): MobileAgentSession | undefined {
    return this.sessions.get(id);
  }

  public getConnectionStatus(): ConnectionStatus {
    return this.connectionStatus;
  }

  public setFilter(filter: StatusFilter) {
    this.statusFilter = filter;
    this.notify();
  }

  public getFilter(): StatusFilter {
    return this.statusFilter;
  }

  public async fetchSessions(authToken?: string): Promise<boolean> {
    try {
      const headers: Record<string, string> = {};
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
      const res = await fetch(`${API_BASE_URL}/api/agents`, { headers });
      if (!res.ok) return false;
      const data = await res.json();
      if (Array.isArray(data)) {
        data.forEach((s: MobileAgentSession) => this.sessions.set(s.session_id, s));
        this.notify();
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }

  public optimisticUpdateStatus(sessionId: string, status: MobileAgentSession['status']) {
    const session = this.sessions.get(sessionId);
    if (session) {
      this.sessions.set(sessionId, { ...session, status });
      this.notify();
    }
  }

  public subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify() {
    this.listeners.forEach((l) => l());
  }
}

export const sessionStore = new SessionStore();
