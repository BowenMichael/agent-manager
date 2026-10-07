/**
 * Unit Tests for Mobile SessionStore and AgentSocketClient.
 * Tests initial state, filtering, optimistic updates, and subscription notifications.
 * Adheres strictly to Anti-Monolith guidelines (< 250 LOC, functions <= 40 LOC).
 */

import { SessionStore, MobileAgentSession } from '../store/sessionStore';
import { AgentSocketClient } from '../services/socket';

describe('AgentSocketClient', () => {
  it('initializes with disconnected state', () => {
    const client = new AgentSocketClient('wss://test.local');
    expect(client.getStatus()).toBe('disconnected');
  });

  it('registers and unregisters event listeners cleanly', () => {
    const client = new AgentSocketClient('wss://test.local');
    const callback = jest.fn();
    const unsubscribe = client.on('test_event', callback);
    expect(typeof unsubscribe).toBe('function');
    unsubscribe();
  });
});

describe('SessionStore', () => {
  let store: SessionStore;

  beforeEach(() => {
    store = new SessionStore();
  });

  it('filters sessions by active, in_review, and completed', () => {
    const mockSessions: MobileAgentSession[] = [
      { session_id: 's-1', repo: 'test/repo1', status: 'running', created_at: new Date().toISOString() },
      { session_id: 's-2', repo: 'test/repo2', status: 'in_review', created_at: new Date().toISOString() },
      { session_id: 's-3', repo: 'test/repo3', status: 'completed', created_at: new Date().toISOString() },
      { session_id: 's-4', repo: 'test/repo4', status: 'failed', created_at: new Date().toISOString() },
    ];

    // Simulate init payload
    (store as any).sessions.clear();
    mockSessions.forEach((s) => (store as any).sessions.set(s.session_id, s));

    store.setFilter('active');
    expect(store.getSessions().length).toBe(1);
    expect(store.getSessions()[0].session_id).toBe('s-1');

    store.setFilter('in_review');
    expect(store.getSessions().length).toBe(1);
    expect(store.getSessions()[0].session_id).toBe('s-2');

    store.setFilter('completed');
    expect(store.getSessions().length).toBe(1);
    expect(store.getSessions()[0].session_id).toBe('s-3');

    store.setFilter('all');
    expect(store.getSessions().length).toBe(4);
  });

  it('applies optimistic updates and notifies subscribers', () => {
    const listener = jest.fn();
    store.subscribe(listener);

    (store as any).sessions.set('s-optimistic', {
      session_id: 's-optimistic',
      repo: 'test/repo',
      status: 'running',
      created_at: new Date().toISOString(),
    });

    store.optimisticUpdateStatus('s-optimistic', 'in_review');
    expect(store.getSession('s-optimistic')?.status).toBe('in_review');
    expect(listener).toHaveBeenCalled();
  });
});
