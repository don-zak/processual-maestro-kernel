document.addEventListener('DOMContentLoaded', () => {
  const providers = [
    { name: 'opencode', label: 'Opencode' },
    { name: 'openai', label: 'OpenAI' },
    { name: 'anthropic', label: 'Anthropic' },
    { name: 'gemini', label: 'Gemini' },
    { name: 'deepseek', label: 'DeepSeek' },
  ];

  function showMessage(id, message, ok = true) {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = '<span class="font-data" style="font-size:11px;color:' + (ok ? 'var(--ok)' : 'var(--error)') + '">' + message + '</span>';
  }

  function setBusy(id, busyLabel, busy) {
    const btn = document.getElementById(id);
    if (!btn) return;
    if (!btn.dataset.defaultLabel) btn.dataset.defaultLabel = btn.textContent;
    btn.disabled = busy;
    btn.textContent = busy ? busyLabel : btn.dataset.defaultLabel;
  }

  function providerName(provider) {
    return provider.name || provider.provider || provider.provider_id || 'provider';
  }

  function isConfigured(provider) {
    return Boolean(provider.configured || provider.ready || provider.enabled || provider.status === 'configured');
  }

  function renderProviders(items) {
    const grid = document.getElementById('adp-grid');
    if (!grid) return;

    const rows = items && items.length ? items : providers.map((p) => ({ name: p.name, configured: false }));

    grid.innerHTML = rows.map((provider) => {
      const name = providerName(provider);
      const ok = isConfigured(provider);
      return '<div class="card flat"><div class="flex-gap"><span class="status-dot"><span class="dot ' + (ok ? 'ok' : '') + '"></span>' + name + '</span></div></div>';
    }).join('');
  }

  async function refresh() {
    try {
      const status = await ADAPTERS_ADAPTER.status();
      renderProviders(status.providers || []);
    } catch (error) {
      renderProviders([]);
      showMessage('adp-config-result', 'Failed to load adapter status: ' + (error.detail || error.message), false);
    }
  }

  async function configure() {
    const provider = document.getElementById('adp-provider')?.value;
    const apiKey = document.getElementById('adp-api-key')?.value || '';
    const model = document.getElementById('adp-model')?.value || undefined;
    const baseUrl = document.getElementById('adp-base-url')?.value || undefined;

    setBusy('adp-configure-btn', 'Configuring...', true);

    try {
      await ADAPTERS_ADAPTER.configure(provider, apiKey, model, baseUrl);
      showMessage('adp-config-result', '✓ ' + provider + ' configured', true);
      await refresh();
    } catch (error) {
      showMessage('adp-config-result', 'Error: ' + (error.detail || error.message), false);
    }

    setBusy('adp-configure-btn', '', false);
  }

  async function testConnection() {
    const provider = document.getElementById('adp-test-provider')?.value;

    setBusy('adp-test-btn', 'Testing...', true);

    try {
      const result = await ADAPTERS_ADAPTER.test(provider);
      showMessage('adp-test-result', result.ok ? '✓ Connected' : 'Disconnected', Boolean(result.ok));
    } catch (error) {
      showMessage('adp-test-result', 'Error: ' + (error.detail || error.message), false);
    }

    setBusy('adp-test-btn', '', false);
  }

  document.getElementById('adp-configure-btn')?.addEventListener('click', configure);
  document.getElementById('adp-test-btn')?.addEventListener('click', testConnection);

  refresh();
});
