// UI Formatting Utilities

function formatTokens(num) {
  if (!num || num === 0) return '0';
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
  return num.toLocaleString();
}

function formatDuration(sec) {
  if (!sec || sec <= 0) return '0s';
  const s = Math.round(sec);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m > 0) return `${m}m ${rem}s`;
  return `${s}s`;
}

function formatTime(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function getStatusBadgeClass(status) {
  switch (status) {
    case 'RUNNING': return 'status-running';
    case 'COMPLETED': return 'status-completed';
    case 'IN_REVIEW': return 'status-review';
    case 'STOPPED': return 'status-stopped';
    case 'PAUSED': return 'status-paused';
    case 'FAILED': return 'status-failed';
    default: return 'status-idle';
  }
}

function showToast(msg, type = 'info') {
  const stack = document.getElementById('toast-stack');
  if (!stack) return;
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  stack.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

window.formatTokens = formatTokens;
window.formatDuration = formatDuration;
window.formatTime = formatTime;
window.escapeHtml = escapeHtml;
window.getStatusBadgeClass = getStatusBadgeClass;
window.showToast = showToast;
