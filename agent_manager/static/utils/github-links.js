/**
 * github-links.js
 * Utility helpers for formatting and updating GitHub Issue and Pull Request links across the UI.
 */

function updateGitHubHeaderLinks(session) {
  const currentIssueLink = document.getElementById('current-issue-link');
  const currentIssueDivider = document.getElementById('current-issue-divider');
  if (currentIssueLink) {
    if (session && session.issue_number && session.repo) {
      currentIssueLink.href = `https://github.com/${session.repo}/issues/${session.issue_number}`;
      currentIssueLink.textContent = `Issue #${session.issue_number} ↗`;
      currentIssueLink.classList.remove('hidden');
      if (currentIssueDivider) currentIssueDivider.classList.remove('hidden');
    } else {
      currentIssueLink.classList.add('hidden');
      if (currentIssueDivider) currentIssueDivider.classList.add('hidden');
    }
  }

  const currentPrLink = document.getElementById('current-pr-link');
  const currentPrDivider = document.getElementById('current-pr-divider');
  if (currentPrLink) {
    if (session && session.pr_url) {
      currentPrLink.href = session.pr_url;
      currentPrLink.textContent = session.pr_number ? `PR #${session.pr_number} ↗` : 'PR ↗';
      currentPrLink.classList.remove('hidden');
      if (currentPrDivider) currentPrDivider.classList.remove('hidden');
    } else {
      currentPrLink.classList.add('hidden');
      if (currentPrDivider) currentPrDivider.classList.add('hidden');
    }
  }
}

if (typeof window !== 'undefined') {
  window.updateGitHubHeaderLinks = updateGitHubHeaderLinks;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { updateGitHubHeaderLinks };
}
