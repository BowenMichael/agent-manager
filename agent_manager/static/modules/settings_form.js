// Settings Form & Event Listeners Module

function initSettingsEvents() {
  const modalSettings = document.getElementById('modal-settings');
  const btnSettingsModal = document.getElementById('btn-settings-modal');
  const btnCloseSettings = document.getElementById('btn-close-settings');
  const btnCancelSettings = document.getElementById('btn-cancel-settings');
  const btnSaveSettings = document.getElementById('btn-save-settings');
  const inputGeminiKey = document.getElementById('setting-gemini-key');

  if (btnSettingsModal) {
    btnSettingsModal.addEventListener('click', () => {
      if (modalSettings) modalSettings.classList.remove('hidden');
      loadSettings();
    });
  }

  if (btnCloseSettings) btnCloseSettings.addEventListener('click', () => modalSettings.classList.add('hidden'));
  if (btnCancelSettings) btnCancelSettings.addEventListener('click', () => modalSettings.classList.add('hidden'));

  const selectDefaultModelEl = document.getElementById('select-default-model');
  if (selectDefaultModelEl) {
    selectDefaultModelEl.addEventListener('change', () => {
      const badgeModel = document.getElementById('current-model-badge');
      if (badgeModel) badgeModel.textContent = selectDefaultModelEl.value;
    });
  }

  const selectDefaultEffortEl = document.getElementById('select-default-effort');
  if (selectDefaultEffortEl) {
    selectDefaultEffortEl.addEventListener('change', () => {
      const badgeEffort = document.getElementById('current-effort-badge');
      if (badgeEffort) badgeEffort.textContent = selectDefaultEffortEl.value;
    });
  }

  if (btnSaveSettings) {
    btnSaveSettings.addEventListener('click', async () => {
      const selectedMode = document.querySelector('input[name="agy_execution_mode"]:checked')?.value || 'web_stream';
      const selectedModel = document.getElementById('select-default-model')?.value || 'gemini-3.8-flash';
      const selectedEffort = document.getElementById('select-default-effort')?.value || 'high';
      const allowOverage = document.getElementById('check-allow-overage')?.checked ?? true;
      const maxTokens = parseInt(document.getElementById('input-max-tokens')?.value || '150000', 10);
      const autoCompact = document.getElementById('check-auto-compact')?.checked ?? true;
      const guardrailsEnabled = document.getElementById('check-guardrails-enabled')?.checked ?? true;
      const autoMergeEnabled = document.getElementById('check-auto-merge')?.checked ?? false;
      const workflowPipeline = document.getElementById('check-workflow-pipeline')?.checked ?? false;
      const sumModel = document.getElementById('select-pipeline-sum-model')?.value || 'gemini-3.8-flash';
      const sumEffort = document.getElementById('select-pipeline-sum-effort')?.value || 'low';
      const planModel = document.getElementById('select-pipeline-plan-model')?.value || 'gemini-3.1-pro';
      const planEffort = document.getElementById('select-pipeline-plan-effort')?.value || 'high';
      const implModel = document.getElementById('select-pipeline-impl-model')?.value || 'gemini-3.8-flash';
      const implEffort = document.getElementById('select-pipeline-impl-effort')?.value || 'low';
      const repoVal = document.getElementById('setting-default-repo')?.value?.trim();
      const key = inputGeminiKey?.value.trim();

      btnSaveSettings.disabled = true;
      btnSaveSettings.textContent = 'Saving...';
      try {
        const payload = {
          agy_mode: selectedMode,
          default_model: selectedModel,
          default_effort: selectedEffort,
          effort_level: selectedEffort,
          allow_overage_credits: allowOverage,
          max_session_tokens: maxTokens,
          compact_completed_chat: autoCompact,
          guardrails_enabled: guardrailsEnabled,
          auto_merge_enabled: autoMergeEnabled,
          workflow_pipeline_enabled: workflowPipeline,
          pipeline_summary_model: sumModel,
          pipeline_summary_effort: sumEffort,
          pipeline_planning_model: planModel,
          pipeline_planning_effort: planEffort,
          pipeline_implementation_model: implModel,
          pipeline_implementation_effort: implEffort
        };
        if (repoVal) payload.default_repo = repoVal;
        if (key) payload.gemini_api_key = key;

        const data = await safeFetchJson('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (modalSettings) modalSettings.classList.add('hidden');
        if (inputGeminiKey) inputGeminiKey.value = '';

        const badgeModel = document.getElementById('current-model-badge');
        const badgeEffort = document.getElementById('current-effort-badge');
        if (badgeModel && data.default_model) badgeModel.textContent = data.default_model;
        if (badgeEffort && data.default_effort) badgeEffort.textContent = data.default_effort;

        showToast(`Settings saved! Model: ${data.default_model} (${data.default_effort} effort). Will apply on next prompt.`);
        await loadSettings();
      } catch (err) {
        showToast('Failed to save settings: ' + extractErrorMessage(err), 'error');
      } finally {
        btnSaveSettings.disabled = false;
        btnSaveSettings.textContent = 'Save Settings';
      }
    });
  }
}

window.initSettingsEvents = initSettingsEvents;
