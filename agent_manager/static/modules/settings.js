// Settings Data Loader & Population Module

async function loadSettings() {
  const apiKeyBanner = document.getElementById('api-key-banner');
  const keyStatusDisplay = document.getElementById('key-status-display');

  try {
    const data = await safeFetchJson('/api/settings');
    if (!data) return;

    if (data.has_gemini_api_key) {
      if (apiKeyBanner) apiKeyBanner.classList.add('hidden');
      if (keyStatusDisplay) {
        keyStatusDisplay.textContent = 'Active: ' + data.masked_gemini_api_key;
        keyStatusDisplay.style.color = 'var(--accent-green)';
      }
    } else {
      if (apiKeyBanner) apiKeyBanner.classList.remove('hidden');
      if (keyStatusDisplay) {
        keyStatusDisplay.textContent = 'Not configured';
        keyStatusDisplay.style.color = 'var(--accent-amber)';
      }
    }

    const selectModel = document.getElementById('select-default-model');
    const selectEffort = document.getElementById('select-default-effort');
    const badgeModel = document.getElementById('current-model-badge');
    const badgeEffort = document.getElementById('current-effort-badge');
    const checkOverage = document.getElementById('check-allow-overage');
    const inputMaxTokens = document.getElementById('input-max-tokens');

    if (selectModel && data.default_model) {
      let matched = false;
      for (const opt of selectModel.options) {
        if (opt.value === data.default_model) {
          selectModel.value = data.default_model;
          matched = true;
          break;
        }
      }
      if (!matched) {
        const base = data.default_model.replace(/-(low|medium|high|xhigh|max)$/, '');
        for (const opt of selectModel.options) {
          if (opt.value === base) {
            selectModel.value = base;
            matched = true;
            break;
          }
        }
      }
    }

    if (selectEffort && data.default_effort) selectEffort.value = data.default_effort;
    if (badgeModel && data.default_model) badgeModel.textContent = data.default_model;
    if (badgeEffort && data.default_effort) badgeEffort.textContent = data.default_effort;

    if (checkOverage && typeof data.allow_overage_credits === 'boolean') {
      checkOverage.checked = data.allow_overage_credits;
    }

    if (inputMaxTokens && data.max_session_tokens) {
      inputMaxTokens.value = data.max_session_tokens;
    }

    const checkAutoCompact = document.getElementById('check-auto-compact');
    if (checkAutoCompact && typeof data.compact_completed_chat === 'boolean') {
      checkAutoCompact.checked = data.compact_completed_chat;
    }

    const checkGuardrails = document.getElementById('check-guardrails-enabled');
    const guardrailsStatus = document.getElementById('guardrails-toggle-status');
    const guardrailsWarning = document.getElementById('guardrails-warning-note');
    const topbarGuardrailsBadge = document.getElementById('badge-guardrails-status');

    function updateGuardrailsUI(enabled) {
      if (guardrailsStatus) {
        guardrailsStatus.textContent = enabled ? 'Active' : 'Disabled';
        guardrailsStatus.style.background = enabled ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.2)';
        guardrailsStatus.style.color = enabled ? '#34d399' : '#f87171';
        guardrailsStatus.style.borderColor = enabled ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.4)';
      }
      if (guardrailsWarning) {
        if (enabled) guardrailsWarning.classList.add('hidden');
        else guardrailsWarning.classList.remove('hidden');
      }
      if (topbarGuardrailsBadge) {
        if (enabled) topbarGuardrailsBadge.classList.add('hidden');
        else topbarGuardrailsBadge.classList.remove('hidden');
      }
    }

    if (checkGuardrails) {
      const isEnabled = typeof data.guardrails_enabled === 'boolean' ? data.guardrails_enabled : true;
      checkGuardrails.checked = isEnabled;
      updateGuardrailsUI(isEnabled);

      if (!checkGuardrails.dataset.listenerBound) {
        checkGuardrails.dataset.listenerBound = 'true';
        checkGuardrails.addEventListener('change', () => {
          updateGuardrailsUI(checkGuardrails.checked);
        });
      }
    }

    const checkAutoMerge = document.getElementById('check-auto-merge');
    if (checkAutoMerge && typeof data.auto_merge_enabled === 'boolean') {
      checkAutoMerge.checked = data.auto_merge_enabled;
    }

    if (topbarGuardrailsBadge && !topbarGuardrailsBadge.dataset.listenerBound) {
      topbarGuardrailsBadge.dataset.listenerBound = 'true';
      topbarGuardrailsBadge.addEventListener('click', () => {
        const modalSettings = document.getElementById('modal-settings');
        if (modalSettings) modalSettings.classList.remove('hidden');
        loadSettings();
      });
    }

    const checkWorkflowPipeline = document.getElementById('check-workflow-pipeline');
    if (checkWorkflowPipeline && typeof data.workflow_pipeline_enabled === 'boolean') {
      checkWorkflowPipeline.checked = data.workflow_pipeline_enabled;
    }

    const selSumModel = document.getElementById('select-pipeline-sum-model');
    if (selSumModel && data.pipeline_summary_model) selSumModel.value = data.pipeline_summary_model;

    const selSumEffort = document.getElementById('select-pipeline-sum-effort');
    if (selSumEffort && data.pipeline_summary_effort) selSumEffort.value = data.pipeline_summary_effort;

    const selPlanModel = document.getElementById('select-pipeline-plan-model');
    if (selPlanModel && data.pipeline_planning_model) selPlanModel.value = data.pipeline_planning_model;

    const selPlanEffort = document.getElementById('select-pipeline-plan-effort');
    if (selPlanEffort && data.pipeline_planning_effort) selPlanEffort.value = data.pipeline_planning_effort;

    const selImplModel = document.getElementById('select-pipeline-impl-model');
    if (selImplModel && data.pipeline_implementation_model) selImplModel.value = data.pipeline_implementation_model;

    const selImplEffort = document.getElementById('select-pipeline-impl-effort');
    if (selImplEffort && data.pipeline_implementation_effort) selImplEffort.value = data.pipeline_implementation_effort;

    if (data.agy_mode === 'terminal') {
      const modeTerm = document.getElementById('mode-terminal');
      if (modeTerm) modeTerm.checked = true;
    } else {
      const modeWeb = document.getElementById('mode-webstream');
      if (modeWeb) modeWeb.checked = true;
    }

    if (data.quota_status) {
      const quotaTitle = document.getElementById('settings-quota-title');
      const quotaTag = document.getElementById('settings-quota-tag');
      const quotaDesc = document.getElementById('settings-quota-desc');
      if (data.quota_status.subscription_quota_reached) {
        if (quotaTitle) quotaTitle.innerHTML = '<span>⚠️</span> Antigravity Quota Reached';
        if (quotaTag) {
          quotaTag.textContent = 'QUOTA LIMITED';
          quotaTag.style.background = 'rgba(239, 68, 68, 0.2)';
          quotaTag.style.color = '#f87171';
          quotaTag.style.border = '1px solid #ef4444';
        }
        if (quotaDesc) {
          quotaDesc.innerHTML = `Baseline quota reached. ${data.allow_overage_credits ? '<strong>AI Credit Overages active</strong>.' : 'Enable <strong>AI Credit Overages</strong> or switch models below.'}`;
        }
      } else {
        if (quotaTitle) quotaTitle.innerHTML = '<span>✅</span> Antigravity Subscription Active';
        if (quotaTag) {
          quotaTag.textContent = 'FRESH QUOTA';
          quotaTag.style.background = 'rgba(16, 185, 129, 0.2)';
          quotaTag.style.color = '#34d399';
          quotaTag.style.border = '1px solid #10b981';
        }
        if (quotaDesc) {
          quotaDesc.innerHTML = `<strong>Google Antigravity Subscription</strong> active.<br>${data.allow_overage_credits ? 'AI Credit Overages enabled.' : 'Zero API key needed.'}`;
        }
      }
    }

    const inputRepo = document.getElementById('setting-default-repo');
    const launchRepo = document.getElementById('launch-repo');
    if (data.default_repo) {
      if (inputRepo) inputRepo.value = data.default_repo;
      if (launchRepo) launchRepo.value = data.default_repo;
    }
  } catch (e) {
    console.error('Failed to load settings:', e);
  }
}

window.loadSettings = loadSettings;
