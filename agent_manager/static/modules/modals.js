// Modals & Action Dialogs Module

function initModals() {
  const modalSimulate = document.getElementById('modal-simulate');
  const btnSimulateModal = document.getElementById('btn-simulate-modal');
  const btnCloseSimulate = document.getElementById('btn-close-simulate');
  const btnCancelSimulate = document.getElementById('btn-cancel-simulate');
  const btnSubmitSimulate = document.getElementById('btn-submit-simulate');
  const simEventType = document.getElementById('sim-event-type');

  if (simEventType) {
    simEventType.addEventListener('change', () => {
      const simGroupTitle = document.getElementById('sim-group-title');
      const simGroupBody = document.getElementById('sim-group-body');
      const simGroupComment = document.getElementById('sim-group-comment');
      if (simEventType.value === 'issue_comment') {
        if (simGroupTitle) simGroupTitle.classList.add('hidden');
        if (simGroupBody) simGroupBody.classList.add('hidden');
        if (simGroupComment) simGroupComment.classList.remove('hidden');
      } else {
        if (simGroupTitle) simGroupTitle.classList.remove('hidden');
        if (simGroupBody) simGroupBody.classList.remove('hidden');
        if (simGroupComment) simGroupComment.classList.add('hidden');
      }
    });
  }

  if (btnSimulateModal && modalSimulate) btnSimulateModal.addEventListener('click', () => modalSimulate.classList.remove('hidden'));
  if (btnCloseSimulate && modalSimulate) btnCloseSimulate.addEventListener('click', () => modalSimulate.classList.add('hidden'));
  if (btnCancelSimulate && modalSimulate) btnCancelSimulate.addEventListener('click', () => modalSimulate.classList.add('hidden'));

  if (btnSubmitSimulate && modalSimulate) {
    btnSubmitSimulate.addEventListener('click', async () => {
      const eventType = simEventType ? simEventType.value : 'issues';
      const issueNum = parseInt(document.getElementById('sim-issue-num')?.value) || 6;
      const issueTitle = document.getElementById('sim-issue-title')?.value || '';
      const issueBody = document.getElementById('sim-issue-body')?.value || '';
      const commentBody = document.getElementById('sim-comment-body')?.value || '';

      btnSubmitSimulate.disabled = true;
      btnSubmitSimulate.textContent = 'Simulating...';

      try {
        const payload = eventType === 'issue_comment' ? {
          event_type: 'issue_comment',
          action: 'created',
          issue_number: issueNum,
          comment_body: commentBody,
          commenter: 'reviewer',
          repo: 'BowenMichael/f1-frontend'
        } : {
          event_type: 'issues',
          action: 'labeled',
          label: 'agent:ready',
          issue_number: issueNum,
          issue_title: issueTitle,
          issue_body: issueBody,
          repo: 'BowenMichael/f1-frontend'
        };

        const data = await safeFetchJson('/api/webhooks/simulate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        modalSimulate.classList.add('hidden');
        if (data.session) selectSession(data.session.session_id);
        else if (data.result && data.result.session_id) selectSession(data.result.session_id);
      } catch (err) {
        alert('Failed to simulate webhook: ' + extractErrorMessage(err));
      } finally {
        btnSubmitSimulate.disabled = false;
        btnSubmitSimulate.textContent = 'Simulate Webhook';
      }
    });
  }

  // Modal: Launch Agent
  const modalLaunch = document.getElementById('modal-launch');
  const btnNewAgentModal = document.getElementById('btn-new-agent-modal');
  const btnCloseLaunch = document.getElementById('btn-close-launch');
  const btnCancelLaunch = document.getElementById('btn-cancel-launch');
  const btnSubmitLaunch = document.getElementById('btn-submit-launch');

  if (btnNewAgentModal && modalLaunch) btnNewAgentModal.addEventListener('click', () => modalLaunch.classList.remove('hidden'));
  if (btnCloseLaunch && modalLaunch) btnCloseLaunch.addEventListener('click', () => modalLaunch.classList.add('hidden'));
  if (btnCancelLaunch && modalLaunch) btnCancelLaunch.addEventListener('click', () => modalLaunch.classList.add('hidden'));

  if (btnSubmitLaunch && modalLaunch) {
    btnSubmitLaunch.addEventListener('click', async () => {
      const repo = document.getElementById('launch-repo')?.value || '';
      const issueNumVal = document.getElementById('launch-issue-num')?.value;
      const prompt = document.getElementById('launch-prompt')?.value.trim() || '';

      if (!prompt) {
        alert('Please enter task instructions or prompt');
        return;
      }

      btnSubmitLaunch.disabled = true;
      btnSubmitLaunch.textContent = 'Spawning...';

      try {
        const session = await safeFetchJson('/api/agents/spawn', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            repo: repo,
            issue_number: issueNumVal ? parseInt(issueNumVal) : null,
            prompt: prompt
          })
        });
        modalLaunch.classList.add('hidden');
        selectSession(session.session_id);
      } catch (err) {
        alert('Failed to launch agent: ' + extractErrorMessage(err));
      } finally {
        btnSubmitLaunch.disabled = false;
        btnSubmitLaunch.textContent = 'Spawn Agent';
      }
    });
  }
}

window.initModals = initModals;
