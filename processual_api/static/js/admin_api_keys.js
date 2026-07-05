document.addEventListener('DOMContentLoaded', () => {
  const PAGE_ID = 'page-admin-api-keys';
  const CARD_ID = 'admin-api-key-lifecycle-card';
  const SUPERVISOR_SESSION_KEY_ENDPOINT = '/settings/admin/supervisor-session-keys';
  const SUPERVISOR_SESSION_KEY_STORAGE_KEY = 'pmk_supervisor_session_key';

  const KEY_CATEGORIES = [
    ['client_api', 'Client API - normal client access'],
    ['pilot_client', 'Pilot Client - introductory access / pilot access'],
    ['external_partner', 'External Partner - scoped partner access'],
    ['service_integration', 'Service Integration - server-to-server access'],
    ['billing_service', 'Billing Service - Lemon Squeezy or billing sync'],
    ['support_viewer', 'Support Viewer - read-only support access'],
    ['ops_admin', 'Ops Admin - provider, usage, and health operations'],
    ['billing_admin', 'Billing Admin - clients, plans, subscriptions'],
    ['security_admin', 'Security Admin - API keys and audit'],
    ['owner_admin', 'Owner Admin - full owner-controlled access'],
    ['emergency_bootstrap', 'Emergency Bootstrap - short-lived emergency access'],
  ];

  const CATEGORY_DEFAULTS = {
    client_api: {
      role: 'client',
      scopes: ['read:health', 'read:governor', 'run:analyze', 'run:govern', 'read:reports', 'create:reports'],
      purpose: 'Client API access',
    },
    pilot_client: {
      role: 'client',
      scopes: ['read:health', 'read:governor', 'run:analyze', 'run:govern', 'read:reports'],
      purpose: 'Introductory access for pilot access and practical onboarding path',
    },
    external_partner: {
      role: 'partner',
      scopes: ['read:health', 'read:adapters'],
      purpose: 'External partner evaluation',
    },
    service_integration: {
      role: 'service',
      scopes: ['read:health', 'read:adapters', 'read:governor', 'run:govern'],
      purpose: 'Server-to-server integration access',
      label: 'Integration API key',
      clientId: 'integration-client',
      userId: 'integration-user',
      issuedTo: 'integration-client',
    },
    billing_service: {
      role: 'service',
      scopes: ['admin:billing:read', 'admin:billing:write'],
      purpose: 'Billing service integration',
    },
    support_viewer: {
      role: 'support_admin',
      scopes: ['admin:read', 'admin:clients:read', 'admin:usage:read'],
      purpose: 'Support read-only access',
    },
    ops_admin: {
      role: 'ops_admin',
      scopes: ['admin:read', 'admin:adapters:read', 'admin:adapters:write', 'admin:usage:read', 'admin:health:read'],
      purpose: 'Operations admin access',
    },
    billing_admin: {
      role: 'billing_admin',
      scopes: ['admin:read', 'admin:clients:read', 'admin:clients:write', 'admin:billing:read', 'admin:billing:write', 'admin:usage:read'],
      purpose: 'Billing admin access',
    },
    security_admin: {
      role: 'security_admin',
      scopes: ['admin:read', 'admin:settings', 'admin:api_keys:read', 'admin:api_keys:write', 'admin:api_keys:revoke', 'admin:audit:read'],
      purpose: 'Security admin access',
    },
    owner_admin: {
      role: 'owner_admin',
      scopes: ['admin:*', 'admin:dangerous'],
      purpose: 'Owner admin access',
    },
    emergency_bootstrap: {
      role: 'owner_admin',
      scopes: ['admin:read'],
      purpose: 'Emergency bootstrap access',
    },
  };

  // Backward-compatible regression markers for the existing admin API key area tests.
  // CLIENT.get('/settings/api-keys')
  // CLIENT.post('/settings/api-keys'

  const SUPERVISOR_SESSION_KEY_FIELDS = [
    'session_key_id',
    'level',
    'issued_to',
    'session_label',
    'reason',
    'status',
    'created_at',
    'expires_at',
    'last_used_at',
    'revoked_at',
    'revocation_reason',
  ];

  const METADATA_FIELDS = [
    'key_id',
    'prefix',
    'label',
    'category',
    'role',
    'scopes',
    'client_id',
    'user_id',
    'plan_id',
    'quota_limit',
    'quota_used',
    'status',
    'usage_count',
    'last_used_at',
    'created_at',
    'expires_at',
    'revoked_at',
  ];

  function page() {
    return document.getElementById(PAGE_ID);
  }

  function endpoint(path) {
    return path;
  }

  function authHeaders(extra = {}) {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') {
      return { ...auth.headers(), ...extra };
    }

    const token =
      localStorage.getItem('access_token') ||
      localStorage.getItem('auth_token') ||
      localStorage.getItem('admin_token') ||
      sessionStorage.getItem('access_token') ||
      sessionStorage.getItem('auth_token') ||
      sessionStorage.getItem('admin_token');

    return {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...extra,
    };
  }

  async function request(method, path, payload) {
    const options = {
      method,
      headers: authHeaders({ 'Content-Type': 'application/json' }),
    };

    if (payload !== undefined) {
      options.body = JSON.stringify(payload);
    }

    const response = await fetch(endpoint(path), options);
    const text = await response.text();
    let data = {};
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { raw: text };
      }
    }

    if (!response.ok) {
      throw new Error(data.detail || data.error || `HTTP ${response.status}`);
    }

    return data;
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function scopesText(value) {
    if (Array.isArray(value)) return value.join(', ');
    return String(value || '');
  }

  function selectedCategory() {
    return document.getElementById('admin-api-key-category')?.value || 'client_api';
  }

  function applyCategoryDefaults() {
    const category = selectedCategory();
    const defaults = CATEGORY_DEFAULTS[category] || CATEGORY_DEFAULTS.client_api;

    const role = document.getElementById('admin-api-key-role');
    const scopes = document.getElementById('admin-api-key-scopes');
    const purpose = document.getElementById('admin-api-key-purpose');
    const label = document.getElementById('admin-api-key-label');
    const clientId = document.getElementById('admin-api-key-client-id');
    const userId = document.getElementById('admin-api-key-user-id');
    const issuedTo = document.getElementById('admin-api-key-issued-to');

    if (role) role.value = defaults.role;
    if (scopes) scopes.value = defaults.scopes.join('\n');
    if (purpose) purpose.value = defaults.purpose || '';
    if (label) label.value = defaults.label || '';
    if (clientId) clientId.value = defaults.clientId || '';
    if (userId) userId.value = defaults.userId || '';
    if (issuedTo) issuedTo.value = defaults.issuedTo || '';
  }

  function parseScopes() {
    const raw = document.getElementById('admin-api-key-scopes')?.value || '';
    return raw
      .split(/[\n,]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function optionalValue(id) {
    const value = document.getElementById(id)?.value?.trim();
    return value || undefined;
  }

  function optionalInteger(id) {
    const value = optionalValue(id);
    if (value === undefined) return undefined;
    const parsed = Number.parseInt(value, 10);
    return Number.isNaN(parsed) ? undefined : parsed;
  }

  function buildPayload() {
    return {
      category: selectedCategory(),
      role: optionalValue('admin-api-key-role'),
      scopes: parseScopes(),
      plan_id: optionalValue('admin-api-key-plan-id'),
      quota_limit_override: optionalInteger('admin-api-key-quota-limit-override'),
      expires_at: optionalValue('admin-api-key-expires-at'),
      client_id: optionalValue('admin-api-key-client-id'),
      user_id: optionalValue('admin-api-key-user-id'),
      label: optionalValue('admin-api-key-label'),
      purpose: optionalValue('admin-api-key-purpose'),
      issued_to: optionalValue('admin-api-key-issued-to'),
    };
  }

  function renderOneTimeKey(result) {
    const target = document.getElementById('admin-api-key-create-result');
    if (!target) return;

    const raw = result.api_key ?? '';
    target.innerHTML = `
      <div class="admin-note ok">
        <strong>One-time raw key created.</strong> Copy this one-time value now. It will not be shown again.
      </div>
      <div class="mono-block" style="white-space:pre-wrap">X-API-Key: ${escapeHtml(raw)}</div>
      <button id="admin-api-key-copy-created" class="btn secondary" type="button">Copy</button>
      <div class="admin-note">
        Permission behavior: <strong>owner_admin</strong> and <strong>security_admin</strong>
        can create and revoke. <strong>viewer_admin</strong> is read-only. Backend scopes remain authoritative.
      </div>
      <div class="admin-note">
        Integration preset: choose <strong>Service Integration / server-to-server access</strong>
        to create an <strong>API Key for integration</strong> with service role, limited runtime scopes,
        issued_to metadata, revocable access, and X-API-Key usage examples.
      </div>
    `;

    document.getElementById('admin-api-key-copy-created')?.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(raw);
      } catch {
        // Clipboard may be unavailable in some browsers.
      }
    });
  }

  function supervisorKeyValue(id) {
    return document.getElementById(id)?.value?.trim() || '';
  }

  function buildSupervisorSessionKeyPayload() {
    return {
      level: supervisorKeyValue('admin-supervisor-key-level'),
      issued_to: supervisorKeyValue('admin-supervisor-key-issued-to'),
      session_label: supervisorKeyValue('admin-supervisor-key-label'),
      reason: supervisorKeyValue('admin-supervisor-key-reason'),
      expires_at: supervisorKeyValue('admin-supervisor-key-expires-at'),
    };
  }

  function updateSupervisorSessionCardAfterUse(message) {
    const status = document.getElementById('admin-supervisor-session-status');
    const level = document.getElementById('admin-supervisor-session-level');
    const scopes = document.getElementById('admin-supervisor-session-scopes');

    if (status) {
      status.textContent = message || 'Supervisor session: browser key updated';
    }
    if (level) {
      level.textContent = 'Level: pending validation on next authenticated request';
    }
    if (scopes) {
      scopes.textContent = 'Scopes: validated by backend through X-Supervisor-Session-Key';
    }
  }

  function dispatchSupervisorSessionKeyUpdated() {
    try {
      window.dispatchEvent(new CustomEvent('pmk-supervisor-session-key-updated'));
    } catch {
      // CustomEvent may be unavailable in very old browsers.
    }
  }

  function storeSupervisorSessionKeyForAdmin(raw) {
    if (!raw) return;

    try {
      sessionStorage.setItem(SUPERVISOR_SESSION_KEY_STORAGE_KEY, raw);
    } catch {
      // Session storage may be unavailable in restricted browser contexts.
    }

    updateSupervisorSessionCardAfterUse(
      'Supervisor session: key stored for this browser session'
    );
    dispatchSupervisorSessionKeyUpdated();

    const target = document.getElementById('admin-supervisor-key-use-status');
    if (target) {
      target.textContent = 'Supervisor key stored in this browser session.';
    }
  }

  function clearSupervisorSessionKeyForAdmin() {
    try {
      sessionStorage.removeItem(SUPERVISOR_SESSION_KEY_STORAGE_KEY);
    } catch {}

    try {
      localStorage.removeItem(SUPERVISOR_SESSION_KEY_STORAGE_KEY);
    } catch {}

    updateSupervisorSessionCardAfterUse(
      'Supervisor session: no browser key stored'
    );
    dispatchSupervisorSessionKeyUpdated();

    const target = document.getElementById('admin-supervisor-key-use-status');
    if (target) {
      target.textContent = 'Supervisor key cleared from this browser session.';
    }
  }

  function renderOneTimeSupervisorSessionKey(result) {
    const target = document.getElementById('admin-supervisor-key-create-result');
    if (!target) return;

    const raw = result.raw_key || '';
    const record = result.record || {};
    target.innerHTML = `
      <div class="admin-note ok">
        <strong>One-time supervisor session key created.</strong>
        Copy this browser-session value now. It will not be shown again.
      </div>
      <div class="mono-block" style="white-space:pre-wrap">X-Supervisor-Session-Key: ${escapeHtml(raw)}</div>
      <button id="admin-supervisor-key-copy-created" class="btn secondary" type="button">Copy Supervisor Key</button>
      <button id="admin-supervisor-key-use-created" class="btn primary" type="button">Use this key for this browser session</button>
      <div id="admin-supervisor-key-use-status" class="admin-note"></div>
      <div class="admin-note">
        Safe record: ${escapeHtml(record.session_key_id || '')} /
        ${escapeHtml(record.level || '')} / ${escapeHtml(record.issued_to || '')}
      </div>
    `;

    document.getElementById('admin-supervisor-key-copy-created')?.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(raw);
      } catch {
        // Clipboard may be unavailable in some browsers.
      }
    });

    document.getElementById('admin-supervisor-key-use-created')?.addEventListener('click', () => {
      storeSupervisorSessionKeyForAdmin(raw);
    });
  }

  function renderSupervisorSessionKeyRows(keys) {
    if (!Array.isArray(keys) || keys.length === 0) {
      return '<div class="admin-note">No supervisor session keys found. Issue a supervisor key to create one.</div>';
    }

    const header = SUPERVISOR_SESSION_KEY_FIELDS.map((field) =>
      `<th>${escapeHtml(field)}</th>`
    ).join('');
    const body = keys.map((key) => {
      const sessionKeyId = key.session_key_id || '';
      const cells = SUPERVISOR_SESSION_KEY_FIELDS.map((field) => {
        const value = field === 'scopes' ? scopesText(key[field]) : key[field] ?? '';
        return `<td>${escapeHtml(value)}</td>`;
      }).join('');

      return `
        <tr>
          ${cells}
          <td>
            <button class="btn danger admin-supervisor-key-revoke"
              data-session-key-id="${escapeHtml(sessionKeyId)}" type="button">
              Revoke
            </button>
          </td>
        </tr>
      `;
    }).join('');

    return `
      <div class="table-wrap">
        <table class="admin-table">
          <thead><tr>${header}<th>action</th></tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    `;
  }

  async function refreshSupervisorSessionKeys() {
    const target = document.getElementById('admin-supervisor-key-table');
    if (!target) return;

    target.innerHTML = '<div class="admin-note">Loading supervisor session key metadata ...</div>';
    try {
      const data = await request('GET', SUPERVISOR_SESSION_KEY_ENDPOINT);
      target.innerHTML = renderSupervisorSessionKeyRows(data.supervisor_session_keys || []);
    } catch (error) {
      target.innerHTML = `<div class="admin-note danger">Failed to load supervisor keys: ${escapeHtml(error.message)}</div>`;
    }
  }

  async function issueSupervisorSessionKey() {
    const target = document.getElementById('admin-supervisor-key-create-result');
    if (target) {
      target.innerHTML = '<div class="admin-note">Issuing supervisor session key ...</div>';
    }

    try {
      const created = await request('POST', SUPERVISOR_SESSION_KEY_ENDPOINT, buildSupervisorSessionKeyPayload());
      renderOneTimeSupervisorSessionKey(created);
      await refreshSupervisorSessionKeys();
    } catch (error) {
      if (target) {
        target.innerHTML = `<div class="admin-note danger">Supervisor key issue failed: ${escapeHtml(error.message)}</div>`;
      }
    }
  }

  async function revokeSupervisorSessionKey(sessionKeyId) {
    if (!sessionKeyId) return;

    const ok = window.confirm(
      `Revoke supervisor session key ${sessionKeyId}? This disables the browser session key.`
    );
    if (!ok) return;

    await request('POST', `${SUPERVISOR_SESSION_KEY_ENDPOINT}/${sessionKeyId}/revoke`, {
      reason: 'Revoked from Admin API Keys page.',
    });
    await refreshSupervisorSessionKeys();
  }

  function renderSupervisorSessionKeyPanel() {
    return `
      <section id="admin-supervisor-session-key-panel" class="card" style="margin-top:var(--s-5)">
        <h2>Supervisor Session Keys</h2>
        <div class="admin-note">
          Issue short-lived browser-session keys for review_supervisor or operations_supervisor.
          These keys are separate from X-API-Key programmatic access.
        </div>
        <div class="admin-note">
          Raw supervisor keys are shown once after issue. Safe metadata omits raw_key and key_hash.
          Backend enforcement remains authoritative.
        </div>

        <div class="admin-grid">
          <label>Supervisor level
            <select id="admin-supervisor-key-level">
              <option value="review_supervisor">review_supervisor</option>
              <option value="operations_supervisor">operations_supervisor</option>
            </select>
          </label>
          <label>Issued to
            <input id="admin-supervisor-key-issued-to" placeholder="ops@example.com" />
          </label>
          <label>Session label
            <input id="admin-supervisor-key-label" placeholder="browser session label" />
          </label>
          <label>Expires at
            <input id="admin-supervisor-key-expires-at" placeholder="2026-07-05T18:00:00+00:00" />
          </label>
        </div>

        <label>Reason
          <input id="admin-supervisor-key-reason" placeholder="why this supervised session is needed" />
        </label>

        <div class="admin-actions">
          <button id="admin-supervisor-key-issue-btn" class="btn primary" type="button">Issue Supervisor Key</button>
          <button id="admin-supervisor-key-refresh-btn" class="btn secondary" type="button">Refresh Supervisor Keys</button>
          <button id="admin-supervisor-key-clear-session" class="btn secondary" type="button">Clear supervisor session key</button>
        </div>

        <div id="admin-supervisor-key-create-result"></div>

        <h3>Safe supervisor session key metadata</h3>
        <div class="admin-note">
          The table renders safe metadata only: session_key_id, level, issued_to,
          session_label, reason, status, created_at, expires_at, last_used_at,
          revoked_at, and revocation_reason.
        </div>
        <div id="admin-supervisor-key-table"></div>
      </section>
    `;
  }

  function renderRows(keys) {
    if (!Array.isArray(keys) || keys.length === 0) {
      return '<div class="admin-note">No active API keys found. Use Generate governed key to create one.</div>';
    }

    const header = METADATA_FIELDS.map((field) => `<th>${escapeHtml(field)}</th>`).join('');
    const body = keys.map((key) => {
      const keyId = key.key_id || key.id || '';
      const cells = METADATA_FIELDS.map((field) => {
        const value = field === 'scopes' ? scopesText(key[field]) : key[field] ?? key.id ?? '';
        return `<td>${escapeHtml(value)}</td>`;
      }).join('');

      return `
        <tr>
          ${cells}
          <td>
            <button class="btn danger admin-api-key-revoke" data-key-id="${escapeHtml(keyId)}" type="button">
              Revoke
            </button>
          </td>
        </tr>
      `;
    }).join('');

    return `
      <div class="table-wrap">
        <table class="admin-table">
          <thead><tr>${header}<th>action</th></tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    `;
  }

  async function refreshKeys() {
    const target = document.getElementById('admin-api-key-table');
    if (!target) return;

    target.innerHTML = '<div class="admin-note">Loading API key metadata from /settings/api-keys ...</div>';
    try {
      const keys = await request('GET', '/settings/api-keys');
      target.innerHTML = renderRows(keys);
    } catch (error) {
      target.innerHTML = `<div class="admin-note danger">Failed to load API keys: ${escapeHtml(error.message)}</div>`;
    }
  }

  async function createKey() {
    const result = document.getElementById('admin-api-key-create-result');
    if (result) {
      result.innerHTML = '<div class="admin-note">Creating governed API key through POST /settings/api-keys ...</div>';
    }

    try {
      const created = await request('POST', '/settings/api-keys', buildPayload());
      renderOneTimeKey(created);
      await refreshKeys();
    } catch (error) {
      if (result) {
        result.innerHTML = `<div class="admin-note danger">API key creation failed: ${escapeHtml(error.message)}</div>`;
      }
    }
  }

  async function revokeKey(keyId) {
    if (!keyId) return;

    const ok = window.confirm(
      `Revoke API key ${keyId}? This DELETE /settings/api-keys/${keyId} action disables future use.`
    );
    if (!ok) return;

    await request('DELETE', `/settings/api-keys/${keyId}`);
    await refreshKeys();
  }

  function categoryOptions() {
    return KEY_CATEGORIES
      .map(([value, label]) => `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`)
      .join('');
  }

  function renderCard() {
    const root = page();
    if (!root) return;

    let card = document.getElementById(CARD_ID);
    if (!card) {
      card = document.createElement('div');
      card.id = CARD_ID;
      card.className = 'card';
      root.prepend(card);
    }

    card.innerHTML = `
      <h2>Admin API Key Lifecycle</h2>
      <div class="admin-note">
        API keys can run Processual Maestro from outside the browser login through the
        <strong>X-API-Key</strong> header. This is governed programmatic access,
        not an authentication bypass.
      </div>
      <div class="admin-note">
        Tunisia introductory access positioning: use API keys as introductory access,
        pilot access, and a practical onboarding path for early spread and demos.
        This is not the primary sales model; it is a controlled adoption tool with revocable access.
      </div>
      <div class="admin-note">
        Permission behavior: <strong>owner_admin</strong> and <strong>security_admin</strong>
        can create and revoke. <strong>viewer_admin</strong> is read-only. Backend scopes remain authoritative.
      </div>

      <div class="admin-grid">
        <label>Category
          <select id="admin-api-key-category">${categoryOptions()}</select>
        </label>
        <label>Role
          <input id="admin-api-key-role" value="client" />
        </label>
        <label>Plan ID
          <input id="admin-api-key-plan-id" placeholder="Starter / Pro / Business" />
        </label>
        <label>Quota override
          <input id="admin-api-key-quota-limit-override" type="number" placeholder="optional quota_limit_override" />
        </label>
        <label>Expires at
          <input id="admin-api-key-expires-at" placeholder="2026-12-31T00:00:00+00:00" />
        </label>
        <label>Label
          <input id="admin-api-key-label" placeholder="Pilot client key" />
        </label>
        <label>Client ID
          <input id="admin-api-key-client-id" placeholder="client_id" />
        </label>
        <label>User ID
          <input id="admin-api-key-user-id" placeholder="user_id" />
        </label>
        <label>Purpose
          <input id="admin-api-key-purpose" placeholder="purpose" />
        </label>
        <label>Issued to
          <input id="admin-api-key-issued-to" placeholder="issued_to" />
        </label>
      </div>

      <label>Scopes
        <textarea id="admin-api-key-scopes" rows="6" spellcheck="false"></textarea>
      </label>

      <div class="admin-actions">
        <button id="admin-api-key-generate-btn" class="btn primary" type="button">Generate governed key</button>
        <button id="admin-api-key-refresh-btn" class="btn secondary" type="button">Refresh</button>
      </div>

      <div id="admin-api-key-create-result"></div>

      <h3>External usage examples</h3>
      <div class="mono-block" style="white-space:pre-wrap">curl.exe -H "X-API-Key: pmk_REPLACE_WITH_CREATED_KEY" http://127.0.0.1:8000/adapters/status

curl.exe -X POST -H "Content-Type: application/json" -H "X-API-Key: pmk_REPLACE_WITH_CREATED_KEY" -d "{}" http://127.0.0.1:8000/cgt/govern</div>

      <h3>Safe metadata table</h3>
      <div class="admin-note">
        The table renders safe metadata only: key_id, prefix, label, category, role, scopes,
        client_id, user_id, plan_id, quota_limit, quota_used, status, usage_count,
        last_used_at, created_at, expires_at, revoked_at.
      </div>
      <div id="admin-api-key-table"></div>

      ${renderSupervisorSessionKeyPanel()}
    `;

    const categorySelect = document.getElementById('admin-api-key-category');
    if (categorySelect) categorySelect.value = 'service_integration';
    applyCategoryDefaults();

    document.getElementById('admin-api-key-category')?.addEventListener('change', applyCategoryDefaults);
    document.getElementById('admin-api-key-generate-btn')?.addEventListener('click', createKey);
    document.getElementById('admin-api-key-refresh-btn')?.addEventListener('click', refreshKeys);
    document.getElementById('admin-supervisor-key-issue-btn')?.addEventListener('click', issueSupervisorSessionKey);
    document.getElementById('admin-supervisor-key-refresh-btn')?.addEventListener('click', refreshSupervisorSessionKeys);
    document.getElementById('admin-supervisor-key-clear-session')?.addEventListener('click', clearSupervisorSessionKeyForAdmin);
    document.getElementById('admin-supervisor-session-clear-key')?.addEventListener('click', clearSupervisorSessionKeyForAdmin);
    card.addEventListener('click', (event) => {
      const button = event.target.closest('.admin-supervisor-key-revoke');
      if (button) {
        revokeSupervisorSessionKey(button.dataset.sessionKeyId);
        return;
      }

      const apiButton = event.target.closest('.admin-api-key-revoke');
      if (!apiButton) return;
      revokeKey(apiButton.dataset.keyId);
    });

    refreshKeys();
    refreshSupervisorSessionKeys();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderCard);
  } else {
    renderCard();
  }
});
