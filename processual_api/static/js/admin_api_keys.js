document.addEventListener('DOMContentLoaded', () => {
  function writeResult(id, value, ok = true) {
    const el = document.getElementById(id);
    if (!el) return;

    const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
    el.style.color = ok ? 'var(--text)' : 'var(--error)';
    el.textContent = text;
  }

  function setBusy(id, label, busy) {
    const btn = document.getElementById(id);
    if (!btn) return;
    if (!btn.dataset.defaultLabel) btn.dataset.defaultLabel = btn.textContent;
    btn.disabled = busy;
    btn.textContent = busy ? label : btn.dataset.defaultLabel;
  }

  async function refreshKeys() {
    setBusy('admin-api-key-refresh-btn', 'Refreshing...', true);

    try {
      const result = await CLIENT.get('/settings/api-keys');
      writeResult('admin-api-key-list', result);
    } catch (error) {
      writeResult('admin-api-key-list', 'Error: ' + (error.detail || error.message), false);
    }

    setBusy('admin-api-key-refresh-btn', '', false);
  }

  async function generateKey() {
    setBusy('admin-api-key-generate-btn', 'Generating...', true);

    try {
      const result = await CLIENT.post('/settings/api-keys', {});
      writeResult('admin-api-key-create-result', result);
      await refreshKeys();
    } catch (error) {
      writeResult('admin-api-key-create-result', 'Error: ' + (error.detail || error.message), false);
    }

    setBusy('admin-api-key-generate-btn', '', false);
  }

  document.getElementById('admin-api-key-refresh-btn')?.addEventListener('click', refreshKeys);
  document.getElementById('admin-api-key-generate-btn')?.addEventListener('click', generateKey);

  if (document.getElementById('page-admin-api-keys')) {
    refreshKeys();
  }
});
