/**
 * Environment configuration for Agent Manager Mobile / Web Client.
 * Reads Expo public variables with safe defaults for local development.
 */

export const Config = {
  apiUrl: process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000',
  wsUrl: process.env.EXPO_PUBLIC_WS_URL || 'ws://localhost:8000/ws/agents',
  appVersion: '1.0.0',
  appName: 'Agent Manager',
};

export default Config;
