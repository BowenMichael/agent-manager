// Telemetry and Timescales UI Module
(function() {
let currentTelemetryData = null;
let activeTimescale = '24h';

async function fetchAndRenderTelemetry(timescale = activeTimescale) {
  try {
    currentTelemetryData = await safeFetchJson('/api/telemetry/tokens');
    renderTelemetryView(currentTelemetryData, timescale);
  } catch (err) {
    console.error('Error fetching telemetry:', extractErrorMessage(err));
  }
}

function renderTelemetryView(data, timescale) {
  if (!data || !data.summary) return;
  activeTimescale = timescale;

  const s = data.summary;
  let windowTokens = s.last_24h_tokens || 0;
  let windowLabel = 'Tokens consumed in last 24h';

  if (timescale === '1h') {
    windowTokens = s.last_1h_tokens || 0;
    windowLabel = 'Tokens consumed in last 1 hour';
  } else if (timescale === '7d') {
    windowTokens = s.last_7d_tokens || 0;
    windowLabel = 'Tokens consumed in last 7 days';
  } else if (timescale === '30d') {
    windowTokens = s.last_30d_tokens || 0;
    windowLabel = 'Tokens consumed in last 30 days';
  } else if (timescale === 'all') {
    windowTokens = s.all_time_tokens || 0;
    windowLabel = 'All-time cumulative tokens';
  }

  // Update Metric Cards
  const elWindowTokens = document.getElementById('telemetry-window-tokens');
  const elWindowLabel = document.getElementById('telemetry-window-label');
  const elAllTokens = document.getElementById('telemetry-all-tokens');
  const elCacheTokens = document.getElementById('telemetry-cache-tokens');
  const elSessionsCount = document.getElementById('telemetry-sessions-count');

  if (elWindowTokens) elWindowTokens.textContent = windowTokens.toLocaleString();
  if (elWindowLabel) elWindowLabel.textContent = windowLabel;
  if (elAllTokens) elAllTokens.textContent = (s.all_time_tokens || 0).toLocaleString();
  if (elCacheTokens) elCacheTokens.textContent = (s.all_time_cache_read_tokens || 0).toLocaleString();
  if (elSessionsCount) elSessionsCount.textContent = (s.total_sessions_tracked || 0).toLocaleString();

  // Render Trend Bars
  const barsContainer = document.getElementById('telemetry-bars-container');
  const trendTitle = document.getElementById('telemetry-trend-title');

  if (barsContainer) {
    barsContainer.innerHTML = '';
    let trendItems = [];

    if (timescale === '1h' || timescale === '24h') {
      if (trendTitle) trendTitle.textContent = '24-Hour Hourly Consumption Trend';
      trendItems = (data.hourly_trend || []).map(item => ({
        label: item.hour ? item.hour.split(' ')[1] : '',
        fullLabel: item.hour,
        tokens: item.tokens || 0
      }));
    } else {
      if (trendTitle) trendTitle.textContent = `${timescale === '7d' ? '7-Day' : '30-Day'} Daily Consumption Trend`;
      const days = timescale === '7d' ? 7 : 30;
      trendItems = (data.daily_trend || []).slice(-days).map(item => ({
        label: item.date ? item.date.slice(5) : '',
        fullLabel: item.date,
        tokens: item.tokens || 0
      }));
    }

    const maxToks = Math.max(...trendItems.map(i => i.tokens), 100);

    trendItems.forEach(item => {
      const col = document.createElement('div');
      col.className = 'telemetry-bar-col';
      col.title = `${item.fullLabel}: ${item.tokens.toLocaleString()} tokens`;

      const pct = Math.max(3, Math.round((item.tokens / maxToks) * 100));
      col.innerHTML = `
        <div class="telemetry-bar-fill" style="height: ${pct}%;"></div>
        <div style="font-size: 0.65rem; color: var(--text-dim); margin-top: 4px; text-align: center; white-space: nowrap;">${item.label}</div>
      `;
      barsContainer.appendChild(col);
    });
  }

  // Render Model Breakdown
  const modelList = document.getElementById('telemetry-model-list');
  if (modelList) {
    modelList.innerHTML = '';
    const models = data.model_breakdown || data.by_model || [];
    if (models.length === 0) {
      modelList.innerHTML = '<div style="font-size: 0.78rem; color: var(--text-dim);">No model metrics recorded yet.</div>';
    } else {
      models.forEach(m => {
        const row = document.createElement('div');
        row.className = 'breakdown-row';
        row.innerHTML = `
          <div class="breakdown-header">
            <span style="font-weight: 500; color: var(--text-primary);">${escapeHtml(m.model)}</span>
            <span style="color: var(--text-secondary);">${(m.tokens || 0).toLocaleString()} (${m.percentage}%)</span>
          </div>
          <div class="breakdown-track">
            <div class="breakdown-fill" style="width: ${m.percentage}%;"></div>
          </div>
        `;
        modelList.appendChild(row);
      });
    }
  }

  // Render Repo Breakdown
  const repoList = document.getElementById('telemetry-repo-list');
  if (repoList) {
    repoList.innerHTML = '';
    const repos = data.repo_breakdown || data.by_repo || [];
    if (repos.length === 0) {
      repoList.innerHTML = '<div style="font-size: 0.78rem; color: var(--text-dim);">No repository metrics recorded yet.</div>';
    } else {
      repos.forEach(r => {
        const row = document.createElement('div');
        row.className = 'breakdown-row';
        row.innerHTML = `
          <div class="breakdown-header">
            <span style="font-weight: 500; color: var(--text-primary);">${escapeHtml(r.repo)}</span>
            <span style="color: var(--text-secondary);">${(r.tokens || 0).toLocaleString()} (${r.percentage}%)</span>
          </div>
          <div class="breakdown-track">
            <div class="breakdown-fill" style="width: ${r.percentage}%; background: var(--accent-purple);"></div>
          </div>
        `;
        repoList.appendChild(row);
      });
    }
  }
}

function initTelemetryEvents() {
  const modalTelemetry = document.getElementById('modal-telemetry');
  const btnTelemetryModal = document.getElementById('btn-telemetry-modal');
  const btnCloseTelemetry = document.getElementById('btn-close-telemetry');
  const btnRefreshTelemetry = document.getElementById('btn-refresh-telemetry');
  const statPillTokens = document.getElementById('stat-pill-tokens');

  if (btnTelemetryModal) {
    btnTelemetryModal.addEventListener('click', () => {
      if (modalTelemetry) modalTelemetry.classList.remove('hidden');
      fetchAndRenderTelemetry(activeTimescale);
    });
  }

  if (statPillTokens) {
    statPillTokens.addEventListener('click', () => {
      if (modalTelemetry) modalTelemetry.classList.remove('hidden');
      fetchAndRenderTelemetry(activeTimescale);
    });
  }

  if (btnCloseTelemetry) {
    btnCloseTelemetry.addEventListener('click', () => {
      if (modalTelemetry) modalTelemetry.classList.add('hidden');
    });
  }

  if (btnRefreshTelemetry) {
    btnRefreshTelemetry.addEventListener('click', () => {
      fetchAndRenderTelemetry(activeTimescale);
    });
  }

  if (modalTelemetry) {
    modalTelemetry.addEventListener('click', (e) => {
      if (e.target === modalTelemetry) modalTelemetry.classList.add('hidden');
    });
  }

  document.querySelectorAll('.telemetry-tabs .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.telemetry-tabs .tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const ts = btn.getAttribute('data-timescale') || '24h';
      if (currentTelemetryData) {
        renderTelemetryView(currentTelemetryData, ts);
      } else {
        fetchAndRenderTelemetry(ts);
      }
    });
  });
}

window.fetchAndRenderTelemetry = fetchAndRenderTelemetry;
window.renderTelemetryView = renderTelemetryView;
window.initTelemetryEvents = initTelemetryEvents;
})();
