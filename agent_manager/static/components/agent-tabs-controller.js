/**
 * Controller for Agent Overview Navigation Tabs (Overview, Git Tree, Issue).
 */
(function() {
  function initAgentTabs() {
    const tabButtons = document.querySelectorAll('.agent-tab-btn');
    const tabPanes = document.querySelectorAll('.agent-tab-pane');

    tabButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-target');
        if (!targetId) return;

        // Update button active state
        tabButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Update pane visibility
        tabPanes.forEach(pane => {
          if (pane.id === targetId) {
            pane.classList.remove('hidden');
          } else {
            pane.classList.add('hidden');
          }
        });
      });
    });
  }

  function updateAgentTabsContext(sessionId) {
    if (!sessionId) return;
    
    const gitTreeViewer = document.getElementById('active-git-tree-viewer');
    if (gitTreeViewer) {
      gitTreeViewer.setAttribute('session-id', sessionId);
    }

    const issueViewer = document.getElementById('active-issue-viewer');
    if (issueViewer) {
      issueViewer.setAttribute('session-id', sessionId);
    }
  }

  window.initAgentTabs = initAgentTabs;
  window.updateAgentTabsContext = updateAgentTabsContext;

  document.addEventListener('DOMContentLoaded', () => {
    initAgentTabs();
  });
})();
