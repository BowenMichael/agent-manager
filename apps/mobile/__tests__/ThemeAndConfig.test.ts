import { Colors, Theme } from '../constants/Theme';
import { Config } from '../constants/Config';

describe('Design System Theme', () => {
  it('should define dark theme background and text colors matching desktop dashboard', () => {
    expect(Theme.background).toBe('#090D16');
    expect(Theme.surface).toBe('#0F172A');
    expect(Theme.text).toBe('#F8FAFC');
    expect(Theme.primary).toBe('#38BDF8');
  });

  it('should include accent and status colors', () => {
    expect(Colors.dark.success).toBe('#10B981');
    expect(Colors.dark.warning).toBe('#F59E0B');
    expect(Colors.dark.danger).toBe('#EF4444');
    expect(Colors.dark.accent).toBe('#6366F1');
  });
});

describe('Environment Configuration', () => {
  it('should provide default API and WebSocket URLs', () => {
    expect(Config.apiUrl).toBeDefined();
    expect(Config.wsUrl).toBeDefined();
    expect(Config.apiUrl).toContain('http');
    expect(Config.wsUrl).toContain('ws');
  });

  it('should have app metadata defined', () => {
    expect(Config.appName).toBe('Agent Manager');
    expect(Config.appVersion).toBe('1.0.0');
  });
});
