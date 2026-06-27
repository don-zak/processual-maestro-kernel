PAGES.adapters = (() => {
  const ADAPTER_PROVIDERS = [
    { name: 'opencode', label: 'Opencode', color: '#22d3a0' },
    { name: 'openai', label: 'OpenAI', color: '#4aaef5' },
    { name: 'anthropic', label: 'Anthropic', color: '#f5a623' },
    { name: 'gemini', label: 'Gemini', color: '#a78bfa' },
    { name: 'deepseek', label: 'DeepSeek', color: '#fb923c' },
  ];

  async function refresh() {
    try {
      const st = await ADAPTERS_ADAPTER.status();
      renderProviderCards(st.providers || []);
    } catch (e) {
      APP.showToast('Failed to load adapter status: ' + e.message, 'error');
      renderProviderCards([]);
    }
  }

  function renderProviderCards(providers) {
    const grid = document.getElementById('adp-grid');
    if (!grid) return;
    grid.innerHTML = '';
    ADAPTER_PROVIDERS.forEach(p => {
      const status = providers.find(x => x.name === p.name);
      const configured = status ? status.configured : false;
      const card = document.createElement('div');
      card.className = 'card flat';
      card.style.borderLeft = '3px solid ' + (configured ? p.color : 'var(--rim)');
      card.innerHTML =
        '<div class="flex-between"><span class="font-mono" style="font-size:14px;color:var(--bright);font-weight:600">' + p.label + '</span><span class="status-dot"><span class="dot ' + (configured ? 'ok' : 'error') + '"></span>' + (configured ? 'Connected' : 'Disconnected') + '</span></div>' +
        (status && status.default_model ? '<div class="font-data text-ghost" style="font-size:10px;margin-top:4px">Model: ' + status.default_model + '</div>' : '') +
        (status && status.latency_ms ? '<div class="font-data text-muted" style="font-size:9px;margin-top:2px">Latency: ' + status.latency_ms + 'ms</div>' : '');
      grid.appendChild(card);
    });
  }

  async function configure() {
    const provider = document.getElementById('adp-provider').value;
    const apiKey = document.getElementById('adp-api-key').value;
    const model = document.getElementById('adp-model').value;
    const baseUrl = document.getElementById('adp-base-url').value;
    const resultDiv = document.getElementById('adp-config-result');

    APP.showLoading('adp-configure-btn', 'Configuring...');
    try {
      await ADAPTERS_ADAPTER.configure(provider, apiKey, model || undefined, baseUrl || undefined);
      resultDiv.innerHTML = '<span class="font-data" style="font-size:11px;color:var(--ok)">✓ ' + provider + ' configured</span>';
      APP.showToast(provider + ' configured successfully', 'success');
      await refresh();
    } catch (e) {
      resultDiv.innerHTML = '<span class="font-data" style="font-size:11px;color:var(--error)">Error: ' + (e.detail || e.message) + '</span>';
    }
    APP.hideLoading('adp-configure-btn');
    setTimeout(() => resultDiv.innerHTML = '', 3000);
  }

  async function testConnection() {
    const provider = document.getElementById('adp-test-provider').value;
    const resultDiv = document.getElementById('adp-test-result');

    APP.showLoading('adp-test-btn', 'Testing...');
    try {
      const res = await ADAPTERS_ADAPTER.test(provider);
      resultDiv.innerHTML = '<div class="card flat" style="margin-top:var(--s-2)"><div class="flex-gap"><span class="status-dot"><span class="dot ' + (res.ok ? 'ok' : 'error') + '"></span>' + (res.ok ? 'Connected' : 'Disconnected') + '</span><span class="font-data text-muted" style="font-size:10px">' + (res.latency_ms || '—') + 'ms</span></div></div>';
      APP.showToast('Test ' + provider + ': ' + (res.ok ? 'connected' : 'disconnected'), res.ok ? 'success' : 'error');
    } catch (e) {
      resultDiv.innerHTML = '<div class="card flat" style="margin-top:var(--s-2);color:var(--error)">Error: ' + (e.detail || e.message) + '</div>';
    }
    APP.hideLoading('adp-test-btn');
  }

  function init() {
    document.getElementById('adp-configure-btn')?.addEventListener('click', configure);
    document.getElementById('adp-test-btn')?.addEventListener('click', testConnection);
    refresh();
  }

  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);

  return { refresh };
})();
