/**
 * Agent REST API Client for Mobile Remote Control.
 * Dispatches context injection, status mutations, and parameter updates.
 */

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'https://agent-manager-api.onrender.com';

export interface ActionResponse {
  success: boolean;
  status?: string;
  message?: string;
}

export interface ParameterPayload {
  model?: string;
  effort?: 'low' | 'medium' | 'high';
}

export async function injectContext(sessionId: string, prompt: string): Promise<ActionResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/agents/${sessionId}/context`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    });
    return { success: res.ok, status: res.ok ? 'injected' : 'error' };
  } catch (err: any) {
    return { success: false, message: err?.message || 'Network error' };
  }
}

export async function executeControlAction(sessionId: string, action: 'stop' | 'resume' | 'restart' | 'complete'): Promise<ActionResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/agents/${sessionId}/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    return { success: res.ok, status: action };
  } catch (err: any) {
    return { success: false, message: err?.message || 'Network error' };
  }
}

export async function updateParameters(sessionId: string, params: ParameterPayload): Promise<ActionResponse> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/agents/${sessionId}/parameters`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    return { success: res.ok };
  } catch (err: any) {
    return { success: false, message: err?.message || 'Network error' };
  }
}
