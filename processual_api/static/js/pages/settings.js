PAGES.settings = (() => {
  function refresh() {
    loadSettings();
    loadApiKeys();
  }

  async function loadSettings() {
    try {
      const res = await CLIENT.get('/settings');
      if (res.general) {
        document.getElementById('set-lang').value = res.general.language || 'en';
        document.getElementById('set-refresh').value = String(res.general.refresh_interval || '30');
        document.getElementById('set-tz').value = res.general.timezone || 'UTC';
      }
      if (res.llm_provider) {
        const llm = res.llm_provider;
        const statusEl = document.getElementById('set-llm-status');
        if (llm.configured) {
          statusEl.textContent = '✓ Connected — ' + llm.provider + (llm.model ? ' (' + llm.model + ')' : '');
          statusEl.className = 'status-badge ok';
          document.getElementById('set-llm-provider').value = llm.provider;
          document.getElementById('set-llm-model').value = llm.model || '';
        } else {
          statusEl.textContent = '○ Not configured';
          statusEl.className = 'status-badge';
        }
      }
      if (res.notifications) {
        document.getElementById('set-webhook').value = res.notifications.discord_webhook || '';
        document.getElementById('set-alert-level').value = res.notifications.alert_level || 'warning';
      }
      if (res.subscription) {
        const sub = res.subscription;
        document.getElementById('set-sub-plan').textContent = sub.plan || '—';
        const statusEl = document.getElementById('set-sub-status');
        statusEl.textContent = sub.status || '—';
        const stageColors = { active: 'var(--ok)', grace: 'var(--warn)', suspended: 'var(--error)', expired: 'var(--error)' };
        statusEl.style.color = stageColors[sub.stage] || 'var(--warn)';
        if (sub.stage === 'grace' || sub.stage === 'suspended') {
          statusEl.textContent += ' (' + sub.stage + ')';
        }
        if (sub.stage === 'grace') {
          statusEl.textContent += ' — read-only';
        }
        document.getElementById('set-sub-renews').textContent = sub.renews_at ? new Date(sub.renews_at).toLocaleDateString() : '—';
        document.getElementById('set-sub-seats').textContent = (sub.seats || 0) + ' / ' + (sub.max_seats || 0);
      }
    } catch (e) {
      APP.showToast('Failed to load settings: ' + (e.detail || e.message), 'error');
    }
  }

  async function loadApiKeys() {
    try {
      const keys = await CLIENT.get('/settings/api-keys');
      const list = document.getElementById('set-apikeys-list');
      if (!keys || keys.length === 0) {
        list.innerHTML = '<span class="text-muted">No API keys configured</span>';
      } else {
        list.innerHTML = keys.map(k =>
          '<div class="flex-between" style="margin-bottom:4px"><span class="font-mono" style="font-size:11px;color:var(--amber)">' + k.prefix + '</span><span class="font-data text-muted" style="font-size:9px">' + (k.created_at ? new Date(k.created_at).toLocaleDateString() : '') + '</span></div>'
        ).join('');
      }
    } catch (e) {
      /* not critical */
    }
  }

  function init() {
    refresh();

    document.getElementById('set-general-save').addEventListener('click', async () => {
      const body = {
        language: document.getElementById('set-lang').value,
        refresh_interval: parseInt(document.getElementById('set-refresh').value) || 30,
        timezone: document.getElementById('set-tz').value,
      };
      try {
        await CLIENT.put('/settings/general', body);
        document.getElementById('set-general-status').textContent = '✓ Saved';
        APP.showToast('General settings saved', 'success');
      } catch (e) {
        document.getElementById('set-general-status').textContent = '✗ Error: ' + (e.detail || e.message);
      }
    });

    document.getElementById('set-llm-save').addEventListener('click', async () => {
      const body = {
        provider: document.getElementById('set-llm-provider').value,
        api_key: document.getElementById('set-llm-key').value,
        model: document.getElementById('set-llm-model').value,
      };
      const resultEl = document.getElementById('set-llm-result');
      APP.showLoading('set-llm-save', 'Saving & Testing...');
      try {
        await CLIENT.put('/settings/llm-provider', body);
        const test = await CLIENT.post('/settings/llm-provider/test', body);
        if (test.success) {
          resultEl.innerHTML = '<span style="color:var(--ok)">✓ Saved & connected (' + test.latency_ms + 'ms)</span>';
          APP.showToast('LLM provider configured', 'success');
        } else {
          resultEl.innerHTML = '<span style="color:var(--warn)">✓ Saved but test failed: ' + (test.error || '') + '</span>';
        }
        document.getElementById('set-llm-key').value = '';
        loadSettings();
      } catch (e) {
        resultEl.innerHTML = '<span style="color:var(--error)">✗ Error: ' + (e.detail || e.message) + '</span>';
      } finally {
        APP.hideLoading('set-llm-save');
      }
    });

    document.getElementById('set-llm-test').addEventListener('click', async () => {
      const body = {
        provider: document.getElementById('set-llm-provider').value,
        api_key: document.getElementById('set-llm-key').value || 'saved',
        model: document.getElementById('set-llm-model').value,
      };
      const resultEl = document.getElementById('set-llm-result');
      APP.showLoading('set-llm-test', 'Testing...');
      try {
        const test = await CLIENT.post('/settings/llm-provider/test', body);
        if (test.success) {
          resultEl.innerHTML = '<span style="color:var(--ok)">✓ Connected (' + test.latency_ms + 'ms)</span>';
        } else {
          resultEl.innerHTML = '<span style="color:var(--error)">✗ Failed: ' + (test.error || '') + '</span>';
        }
      } catch (e) {
        resultEl.innerHTML = '<span style="color:var(--error)">✗ Error: ' + (e.detail || e.message) + '</span>';
      } finally {
        APP.hideLoading('set-llm-test');
      }
    });

    document.getElementById('set-llm-clear').addEventListener('click', async () => {
      const resultEl = document.getElementById('set-llm-result');
      try {
        await CLIENT.del('/settings/llm-provider');
        resultEl.innerHTML = '<span style="color:var(--ok)">✓ API key cleared</span>';
        document.getElementById('set-llm-key').value = '';
        document.getElementById('set-llm-model').value = '';
        loadSettings();
        APP.showToast('LLM provider cleared', 'info');
      } catch (e) {
        resultEl.innerHTML = '<span style="color:var(--error)">✗ Error: ' + (e.detail || e.message) + '</span>';
      }
    });

    document.getElementById('set-notif-save').addEventListener('click', async () => {
      const body = {
        discord_webhook: document.getElementById('set-webhook').value,
        alert_level: document.getElementById('set-alert-level').value,
      };
      try {
        await CLIENT.put('/settings/notifications', body);
        document.getElementById('set-notif-status').textContent = '✓ Saved';
        APP.showToast('Notification settings saved', 'success');
      } catch (e) {
        document.getElementById('set-notif-status').textContent = '✗ Error: ' + (e.detail || e.message);
      }
    });

    document.getElementById('set-notif-test').addEventListener('click', async () => {
      const body = {
        discord_webhook: document.getElementById('set-webhook').value,
        alert_level: document.getElementById('set-alert-level').value,
      };
      APP.showLoading('set-notif-test', 'Testing...');
      try {
        await CLIENT.post('/settings/notifications/test', body);
        document.getElementById('set-notif-status').textContent = '✓ Test message sent to Discord';
        APP.showToast('Discord test sent', 'success');
      } catch (e) {
        document.getElementById('set-notif-status').textContent = '✗ Error: ' + (e.detail || e.message);
      } finally {
        APP.hideLoading('set-notif-test');
      }
    });

    document.getElementById('set-sub-manage').addEventListener('click', () => {
      APP.showToast('Subscription management coming soon', 'info');
    });

    document.getElementById('set-apikey-generate').addEventListener('click', async () => {
      const resultEl = document.getElementById('set-apikey-result');
      try {
        const res = await CLIENT.post('/settings/api-keys', {});
        resultEl.innerHTML = '<div style="color:var(--ok);font-size:11px">✓ New key generated:</div>' +
          '<code style="display:block;background:var(--bg2);padding:6px 8px;border-radius:4px;margin-top:4px;word-break:break-all;font-size:11px">' + res.api_key + '</code>' +
          '<div style="font-size:9px;color:var(--warn);margin-top:4px">⚠ Copy this key now. It will not be shown again.</div>';
        loadApiKeys();
        APP.showToast('API key generated', 'success');
      } catch (e) {
        resultEl.innerHTML = '<span style="color:var(--error)">✗ Error: ' + (e.detail || e.message) + '</span>';
      }
    });
  }

  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
  return { refresh };
})();
