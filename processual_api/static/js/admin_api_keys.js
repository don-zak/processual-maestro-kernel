document.addEventListener('DOMContentLoaded', () => {
  const PAGE_ID = 'page-admin-api-keys';
  const CARD_ID = 'admin-api-key-lifecycle-card';

  const KEY_CATEGORIES = [
    ['client_api', 'Client API — normal client access'],
    ['pilot_client', 'Pilot Client — introductory access / pilot access'],
    ['external_partner', 'External Partner — scoped partner access'],
    ['service_integration', 'Service Integration — server-to-server access'],
    ['billing_service', 'Billing Service — Lemon Squeezy or billing sync'],
    ['support_viewer', 'Support Viewer — read-only support access'],
    ['ops_admin', 'Ops Admin — provider, usage, and health operations'],
    ['billing_admin', 'Billing Admin — clients, plans, subscriptions'],
    ['security_admin', 'Security Admin — API keys and audit'],
    ['owner_admin', 'Owner Admin — full owner-controlled access'],
    ['emergency_bootstrap', 'Emergency Bootstrap — short-lived emergency access'],
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
      scopes: ['read:health'],
      purpose: 'Service-to-service integration',
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

    if (role) role.value = defaults.role;
    if (scopes) scopes.value = defaults.scopes.join('\n');
    if (purpose && !purpose.value.trim()) purpose.value = defaults.purpose;
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

    const raw = result['api_key'] ?? '';
    target.innerHTML = `
      <div class="admin-note ok">
        <strong>One-time raw key created.</strong> This one-time value is the raw key.
        Copy this raw key now. It will not be shown again.
      </div>
      <div class="mono-block" style="white-space:pre-wrap">X-API-Key: ${escapeHtml(raw)}</div>
      <button id="admin-api-key-copy-created" class="btn secondary" type="button">Copy</button>
      <div class="admin-note">
        This is governed programmatic access outside the browser login.
        It is not an authentication bypass. It is scoped, quota-bound, revocable access and auditable.
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
    `;

    applyCategoryDefaults();

    document.getElementById('admin-api-key-category')?.addEventListener('change', applyCategoryDefaults);
    document.getElementById('admin-api-key-generate-btn')?.addEventListener('click', createKey);
    document.getElementById('admin-api-key-refresh-btn')?.addEventListener('click', refreshKeys);
    card.addEventListener('click', (event) => {
      const button = event.target.closest('.admin-api-key-revoke');
      if (!button) return;
      revokeKey(button.dataset.keyId);
    });

    refreshKeys();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderCard);
  } else {
    renderCard();
  }
});
