(() => {
  'use strict';

  const state = {
    mounted: false,
    loading: false,
    integration: null,
    sandboxKeys: null,
    provider: null,
    secretOnce: '',
    message: '',
    error: '',
  };

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[char]);
  }

  function rootPage() { return document.getElementById('page-settings'); }
  function operationsRoot() { return document.getElementById('settings-operations-root'); }

  function profileOptions() {
    const profiles = Array.isArray(state.integration?.operational_profiles)
      ? state.integration.operational_profiles
      : [];
    return profiles
      .filter((profile) => profile?.client_visible === true)
      .map((profile) => {
        const selfService = profile.read_only === true
          && profile.write_allowed === false
          && profile.restricted_allowed === false
          && profile.environment === 'sandbox';
        const suffix = selfService ? 'Self-service sandbox' : 'Approval required';
        return `<option value="${esc(profile.profile_id)}" ${selfService ? '' : 'disabled'}>${esc(profile.display_name)} · ${suffix}</option>`;
      }).join('');
  }

  function activeKeys() {
    return Array.isArray(state.sandboxKeys?.keys) ? state.sandboxKeys.keys : [];
  }

  function keyRows() {
    if (state.integration?.enabled !== true) {
      return '<div class="sops-note">Sandbox API self-service is unavailable for the current plan. Upgrade or activate Enterprise Integration before issuing client-managed keys.</div>';
    }
    const keys = activeKeys();
    if (!keys.length) {
      return '<div class="sops-note">No self-service sandbox keys exist yet. Choose a read-only operational profile and create one.</div>';
    }
    return `<div class="sops-key-list">${keys.map((key) => `
      <div class="sops-key">
        <div class="sops-key-head"><strong>${esc(key.label || key.profile_id || 'Sandbox key')}</strong><span class="sops-badge good">${esc(key.status || 'enabled')}</span></div>
        <div class="sops-key-meta">key_id=${esc(key.key_id)} · prefix=${esc(key.prefix)}<br>profile=${esc(key.profile_id)} · expires=${esc(key.expires_at || '-')}<br>scopes=${esc((key.scopes || []).join(', '))}</div>
        <div class="sops-actions">
          <button class="sops-btn ghost" data-sops-rotate="${esc(key.key_id)}">Rotate</button>
          <button class="sops-btn danger" data-sops-revoke="${esc(key.key_id)}">Revoke</button>
        </div>
      </div>`).join('')}</div>`;
  }

  function render() {
    const root = operationsRoot();
    if (!root) return;
    const integrationEnabled = state.integration?.enabled === true;
    const providerConfigured = state.provider?.configured === true;
    const keyCount = activeKeys().length;

    root.innerHTML = `<div class="sops-shell">
      <section class="sops-hero">
        <div class="sops-eyebrow">Client operations center</div>
        <h1>Configure, validate, and operate safely</h1>
        <p>Routine client-scoped actions run directly here. Supervisor escalation is reserved for production access, write scopes, security exceptions, and commercial decisions.</p>
        <div class="sops-badges">
          <span class="sops-badge ${integrationEnabled ? 'good' : 'warn'}">Integration ${integrationEnabled ? 'eligible' : 'plan review required'}</span>
          <span class="sops-badge ${providerConfigured ? 'good' : 'warn'}">Provider ${providerConfigured ? 'connected' : 'not configured'}</span>
          <span class="sops-badge good">Sandbox only</span>
          <span class="sops-badge warn">Production approval required</span>
        </div>
      </section>

      <div class="sops-grid">
        <section class="sops-card">
          <h2>Provider connection</h2>
          <small>Test and save your BYOK provider directly. Routine setup does not require a supervisor message.</small>
          <div class="sops-status"><strong>${providerConfigured ? 'Connected' : 'Action required'}</strong><span>${esc(state.provider?.provider || 'Choose a provider below')}</span></div>
          <div class="sops-actions"><button class="sops-btn" data-sops-open="provider">Open provider setup</button></div>
        </section>

        <section class="sops-card">
          <h2>Institution integration</h2>
          <small>Manage CAMARA, TM Forum, and operator-specific cases in the dedicated institution workspace.</small>
          <div class="sops-status"><strong>Case workflow</strong><span>Technical intake · sandbox qualification · approval gates</span></div>
          <div class="sops-actions"><button class="sops-btn" data-sops-open="institution">Open institution workspace</button></div>
        </section>

        <section class="sops-card" style="grid-column:1/-1">
          <h2>Sandbox API access</h2>
          <small>Create, rotate, and revoke read-only client sandbox keys. Raw key material is shown once and never returned again.</small>
          <div class="sops-status"><strong>${integrationEnabled ? 'Self-service available' : 'Locked by current plan'}</strong><span>${integrationEnabled ? `${keyCount} / ${esc(state.sandboxKeys?.max_active_keys || 3)} active keys` : esc(state.integration?.plan_id || 'Enterprise Integration required')}</span></div>
          <div class="sops-form">
            <select id="sops-profile" class="sops-select" ${integrationEnabled ? '' : 'disabled'}>
              <option value="">Choose a read-only operational profile</option>
              ${profileOptions()}
            </select>
            <input id="sops-label" class="sops-input" value="Institution sandbox" maxlength="120" placeholder="Key label" ${integrationEnabled ? '' : 'disabled'}>
            <select id="sops-expiry" class="sops-select" ${integrationEnabled ? '' : 'disabled'}><option value="30">30 days</option><option value="60">60 days</option><option value="90">90 days</option></select>
          </div>
          <div class="sops-actions"><button class="sops-btn" data-sops-create ${integrationEnabled ? '' : 'disabled'}>Create sandbox key</button><button class="sops-btn ghost" data-sops-refresh>Refresh</button></div>
          ${state.secretOnce ? `<div class="sops-secret"><strong>Copy this key now — it will not be shown again.</strong><code>${esc(state.secretOnce)}</code><div class="sops-actions"><button class="sops-btn" data-sops-copy>Copy key</button><button class="sops-btn ghost" data-sops-hide-secret>Hide</button></div></div>` : ''}
          ${state.message ? `<div class="sops-note sops-success">${esc(state.message)}</div>` : ''}
          ${state.error ? `<div class="sops-note sops-error">${esc(state.error)}</div>` : ''}
          ${keyRows()}
          <div class="sops-note">Write scopes, restricted operations, runtime connectors, and production keys remain supervisor-controlled.</div>
        </section>
      </div>
    </div>`;

    bind();
  }

  async function load() {
    if (state.loading) return;
    state.loading = true;
    state.error = '';
    try {
      const primaryResults = await Promise.allSettled([
        CLIENT.get('/settings/api-key-integration'),
        CLIENT.get('/settings/client/provider-connection'),
      ]);
      state.integration = primaryResults[0].status === 'fulfilled' ? primaryResults[0].value : null;
      state.provider = primaryResults[1].status === 'fulfilled' ? primaryResults[1].value : null;

      const primaryFailures = primaryResults.filter((item) => item.status === 'rejected');
      if (primaryFailures.length) {
        state.error = primaryFailures.map((item) => item.reason?.detail || item.reason?.message || 'Unavailable').join(' · ');
      }

      if (state.integration?.enabled === true) {
        try {
          state.sandboxKeys = await CLIENT.get('/settings/client/api-keys');
        } catch (error) {
          state.sandboxKeys = { keys: [], max_active_keys: 3 };
          state.error = error?.detail || error?.message || 'Sandbox API key status unavailable.';
        }
      } else {
        state.sandboxKeys = {
          status: 'locked',
          keys: [],
          key_count: 0,
          max_active_keys: 3,
          production_allowed: false,
          runtime_connector_approved: false,
          raw_secret_visible: false,
        };
      }
    } finally {
      state.loading = false;
      render();
    }
  }

  async function createKey() {
    const profileId = document.getElementById('sops-profile')?.value || '';
    const label = document.getElementById('sops-label')?.value.trim() || 'Institution sandbox';
    const expires = Number(document.getElementById('sops-expiry')?.value || 30);
    if (!profileId) {
      state.error = 'Choose a self-service read-only operational profile.';
      render();
      return;
    }
    state.error = '';
    state.message = 'Creating sandbox key…';
    render();
    try {
      const result = await CLIENT.post('/settings/client/api-keys', {
        profile_id: profileId,
        label,
        purpose: 'Client-managed institution sandbox integration',
        expires_in_days: expires,
      });
      state.secretOnce = result.api_key || '';
      state.message = 'Sandbox key created successfully.';
      await load();
    } catch (error) {
      state.message = '';
      state.error = error?.detail || error?.message || 'Key creation failed.';
      render();
    }
  }

  async function rotateKey(keyId) {
    state.error = '';
    state.message = 'Rotating sandbox key…';
    render();
    try {
      const result = await CLIENT.post(`/settings/client/api-keys/${encodeURIComponent(keyId)}/rotate`, { expires_in_days: 30 });
      state.secretOnce = result.api_key || '';
      state.message = 'Key rotated. The previous key is revoked.';
      await load();
    } catch (error) {
      state.message = '';
      state.error = error?.detail || error?.message || 'Key rotation failed.';
      render();
    }
  }

  async function revokeKey(keyId) {
    if (!window.confirm('Revoke this sandbox key? This action cannot be undone.')) return;
    state.error = '';
    state.message = 'Revoking sandbox key…';
    render();
    try {
      await CLIENT.del(`/settings/client/api-keys/${encodeURIComponent(keyId)}`);
      state.message = 'Sandbox key revoked.';
      await load();
    } catch (error) {
      state.message = '';
      state.error = error?.detail || error?.message || 'Key revocation failed.';
      render();
    }
  }

  function openSection(target) {
    if (target === 'institution') {
      document.querySelector('.nav-btn[data-page="institution"]')?.click();
      return;
    }
    const map = {
      provider: '#set-provider-connection-card',
      api: '#set-api-key-integration-card',
      usage: '#set-usage-summary-card',
      support: '#set-client-support-card',
    };
    const element = document.querySelector(map[target] || target);
    element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function bind() {
    const root = operationsRoot();
    if (!root) return;
    root.querySelector('[data-sops-create]')?.addEventListener('click', createKey);
    root.querySelector('[data-sops-refresh]')?.addEventListener('click', load);
    root.querySelector('[data-sops-copy]')?.addEventListener('click', async () => {
      await navigator.clipboard.writeText(state.secretOnce);
      APP.showToast('API key copied', 'success');
    });
    root.querySelector('[data-sops-hide-secret]')?.addEventListener('click', () => { state.secretOnce = ''; render(); });
    root.querySelectorAll('[data-sops-rotate]').forEach((button) => button.addEventListener('click', () => rotateKey(button.dataset.sopsRotate)));
    root.querySelectorAll('[data-sops-revoke]').forEach((button) => button.addEventListener('click', () => revokeKey(button.dataset.sopsRevoke)));
    root.querySelectorAll('[data-sops-open]').forEach((button) => button.addEventListener('click', () => openSection(button.dataset.sopsOpen)));
  }

  function mount() {
    const page = rootPage();
    if (!page || operationsRoot()) return;
    const container = page.firstElementChild || page;
    const root = document.createElement('div');
    root.id = 'settings-operations-root';
    container.insertBefore(root, container.firstChild);

    ['set-client-requests-card', 'set-client-support-card'].forEach((id) => {
      document.getElementById(id)?.classList.add('sops-secondary');
    });
    state.mounted = true;
    load();
  }

  function init() {
    mount();
    load();
  }

  window.PMK_SETTINGS_OPERATIONS_18 = { init, refresh: load };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
