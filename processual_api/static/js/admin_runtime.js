(function () {

  const ADMIN_ENDPOINT_REGISTRY = {
    wired: [
      '/auth/me',
      '/health/live',
      '/health/ready',
      '/adapters/status',
      '/settings/api-keys',
      '/applications',
    ],
    planned: [
      '/settings/usage-logs',
      '/billing/events',
      '/billing/subscriptions',
      '/billing/plans',
    ],
  };

  function isPlannedOnlyEndpoint(path) {
    return ADMIN_ENDPOINT_REGISTRY.planned.includes(path);
  }

  function plannedEndpointResult(path) {
    return {
      ok: false,
      path,
      status: 'not-wired',
      data: 'Not wired yet: backend route is planned but not implemented.',
    };
  }


  const AUTH_KEYS = [
    'token',
    'access_token',
    'auth_token',
    'maestro_token',
    'maestro_auth_token',
    'pmk_token',
    'pmk_auth_token',
  ];

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function token() {
    function tokenFromValue(value) {
      if (!value) return '';

      if (typeof value !== 'string') {
        return '';
      }

      const raw = value.trim();

      if (!raw) return '';

      if (raw.startsWith('Bearer ')) {
        return raw.slice('Bearer '.length).trim();
      }

      if (raw.startsWith('{') || raw.startsWith('[')) {
        try {
          const parsed = JSON.parse(raw);
          return (
            parsed.access_token ||
            parsed.token ||
            parsed.auth_token ||
            parsed.jwt ||
            parsed.bearer ||
            parsed.api_token ||
            parsed?.user?.access_token ||
            parsed?.user?.token ||
            ''
          );
        } catch (error) {}
      }

      if (raw.split('.').length === 3) {
        return raw;
      }

      if (raw.startsWith('eyJ')) {
        return raw;
      }

      return '';
    }

    const preferredKeys = [
      'token',
      'access_token',
      'auth_token',
      'jwt',
      'bearer',
      'maestro_token',
      'maestro_auth_token',
      'pmk_token',
      'pmk_auth_token',
      'admin_token',
      'admin_access_token',
      'processual_token',
      'processual_auth_token',
    ];

    for (const storage of [localStorage, sessionStorage]) {
      for (const key of preferredKeys) {
        try {
          const found = tokenFromValue(storage.getItem(key));
          if (found) return found;
        } catch (error) {}
      }
    }

    for (const storage of [localStorage, sessionStorage]) {
      try {
        for (let index = 0; index < storage.length; index += 1) {
          const key = storage.key(index);
          if (!key) continue;

          const keyName = key.toLowerCase();

          if (
            !keyName.includes('token') &&
            !keyName.includes('auth') &&
            !keyName.includes('jwt') &&
            !keyName.includes('session')
          ) {
            continue;
          }

          const found = tokenFromValue(storage.getItem(key));
          if (found) return found;
        }
      } catch (error) {}
    }

    return '';
  }

  function authHeaders() {
    if (window.PMK_ADMIN_AUTH && typeof PMK_ADMIN_AUTH.headers === 'function') {
      return PMK_ADMIN_AUTH.headers();
    }

    const headers = { 'Content-Type': 'application/json' };
    const authToken = token();

    if (authToken) {
      headers.Authorization = 'Bearer ' + authToken;
    }

    return headers;
  }

  async function request(method, path, body) {
    const response = await fetch(path, {
      method,
      credentials: 'include',
      headers: authHeaders(),
      body: method === 'GET' ? undefined : JSON.stringify(body || {}),
    });

    const text = await response.text();
    let data = text;

    try {
      data = text ? JSON.parse(text) : {};
    } catch (error) {}

    if (!response.ok) {
      const detail =
        data && typeof data === 'object'
          ? data.detail || data.message || JSON.stringify(data)
          : data;

      const failure = new Error(detail || response.statusText);
      failure.status = response.status;
      failure.data = data;
      throw failure;
    }

    return data;
  }


  function hasHeader(headers, name) {
    if (!headers) return false;

    if (typeof headers.has === 'function') {
      return headers.has(name);
    }

    const target = String(name).toLowerCase();

    return Object.keys(headers).some((key) => {
      return key.toLowerCase() === target && Boolean(headers[key]);
    });
  }

  function hasAuthTransport(headers) {
    return hasHeader(headers, 'Authorization') || hasHeader(headers, 'X-API-Key');
  }

  async function safeGet(path) {
    if (isPlannedOnlyEndpoint(path)) {
      return plannedEndpointResult(path);
    }
const headers = authHeaders();

    if (
      !hasAuthTransport(headers) &&
      !path.startsWith('/health/')
    ) {
      return {
        ok: false,
        path,
        status: 'auth-missing',
        data: 'Admin token missing in browser storage. Login must persist a Bearer token for admin endpoints.',
      };
    }

    try {
      const data = await request('GET', path);
      return { ok: true, path, status: 200, data };
    } catch (error) {
      return {
        ok: false,
        path,
        status: error.status || 'not-wired',
        data: error.data || error.message || 'Not wired yet',
      };
    }
  }

  async function safePost(path, body) {
    const headers = authHeaders();

    if (!hasAuthTransport(headers)) {
      return {
        ok: false,
        path,
        status: 'auth-missing',
        data: 'Admin token missing in browser storage. Login must persist a Bearer token for admin endpoints.',
      };
    }

    try {
      const data = await request('POST', path, body);
      return { ok: true, path, status: 200, data };
    } catch (error) {
      return {
        ok: false,
        path,
        status: error.status || 'not-wired',
        data: error.data || error.message || 'Not wired yet',
      };
    }
  }

  function installStyle() {
    if (document.getElementById('admin-runtime-style')) return;

    const style = document.createElement('style');
    style.id = 'admin-runtime-style';
    style.textContent = [
      '.admin-runtime-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:var(--s-4);margin-top:var(--s-4);position:relative;z-index:3}',
      '.admin-page{padding-bottom:64px}',
      '.admin-page:not(.active){display:none!important}',
      '.admin-kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:var(--s-3);margin-top:var(--s-3)}',
      '.admin-kpi{border:1px solid var(--line);border-radius:14px;padding:12px;background:rgba(255,255,255,.025)}',
      '.admin-kpi .label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.12em}',
      '.admin-kpi .value{font-size:22px;font-weight:700;margin-top:6px}',
      '.admin-data-table{width:100%;border-collapse:collapse;font-size:11px;margin-top:var(--s-3)}',
      '.admin-data-table th,.admin-data-table td{border-bottom:1px solid var(--line);text-align:left;padding:7px 8px;vertical-align:top}',
      '.admin-data-table th{color:var(--muted);font-weight:600}',
      '.admin-note{font-size:11px;color:var(--muted);white-space:pre-wrap;margin-top:var(--s-2)}',
      '.admin-ok{color:var(--ok)}',
      '.admin-warn{color:var(--warn)}',
      '.admin-error{color:var(--error)}',
      '.admin-bar-chart{display:grid;gap:8px;margin-top:var(--s-3)}',
      '.admin-bar-row{display:grid;grid-template-columns:140px 1fr 52px;gap:8px;align-items:center;font-size:11px}',
      '.admin-bar-track{height:9px;border:1px solid var(--line);border-radius:999px;overflow:hidden;background:rgba(255,255,255,.04)}',
      '.admin-bar-fill{height:100%;background:var(--accent);width:0%}',
      '.admin-runtime-error{color:var(--error);font-size:11px;white-space:pre-wrap}',
      '.admin-runtime-grid .card{max-height:440px;overflow:auto}',
      '#admin-api-key-create-result,#admin-api-key-list{max-height:440px;overflow:auto;white-space:pre-wrap}',
      '.admin-runtime-grid .card{max-height:420px;overflow:auto}',
      '#admin-api-key-create-result,#admin-api-key-list{max-height:420px;overflow:auto;white-space:pre-wrap}',
    ].join('\n');

    document.head.appendChild(style);
  }

  function table(headers, rows) {
    if (!rows || rows.length === 0) {
      return '<div class="admin-note">No rows returned.</div>';
    }

    return [
      '<table class="admin-data-table">',
      '<thead><tr>' + headers.map((h) => '<th>' + escapeHtml(h) + '</th>').join('') + '</tr></thead>',
      '<tbody>',
      rows
        .map((row) =>
          '<tr>' +
          headers.map((h) => '<td>' + escapeHtml(row[h] ?? '') + '</td>').join('') +
          '</tr>'
        )
        .join(''),
      '</tbody></table>',
    ].join('');
  }

  function bars(items) {
    const max = Math.max(1, ...items.map((item) => Number(item.value) || 0));

    return [
      '<div class="admin-bar-chart">',
      items
        .map((item) => {
          const value = Number(item.value) || 0;
          const width = Math.max(value > 0 ? 4 : 0, Math.round((value / max) * 100));
          return [
            '<div class="admin-bar-row">',
            '<div>' + escapeHtml(item.label) + '</div>',
            '<div class="admin-bar-track"><div class="admin-bar-fill" style="width:' + width + '%"></div></div>',
            '<div>' + escapeHtml(value) + '</div>',
            '</div>',
          ].join('');
        })
        .join(''),
      '</div>',
    ].join('');
  }

  function kpis(items) {
    return [
      '<div class="admin-kpi-grid">',
      items
        .map(
          (item) =>
            '<div class="admin-kpi"><div class="label">' +
            escapeHtml(item.label) +
            '</div><div class="value">' +
            escapeHtml(item.value) +
            '</div></div>'
        )
        .join(''),
      '</div>',
    ].join('');
  }

  function arrayFrom(data, keys) {
    if (Array.isArray(data)) return data;

    for (const key of keys) {
      if (data && Array.isArray(data[key])) return data[key];
    }

    return [];
  }

  function endpointRows(results) {
    return results.map((result) => ({
      Endpoint: result.path,
      State: result.ok ? 'wired' : 'Not wired yet',
      Status: result.status,
    }));
  }

  function page(id) {
    return document.getElementById(id);
  }

  function ensureGrid(pageId) {
    const target = page(pageId);
    if (!target) return null;

    let grid = target.querySelector('[data-admin-runtime-grid]');
    if (grid) return grid;

    grid = document.createElement('div');
    grid.className = 'admin-runtime-grid';
    grid.setAttribute('data-admin-runtime-grid', '1');

    const container = target.querySelector('div') || target;
    container.appendChild(grid);

    return grid;
  }

  function ensureCard(pageId, cardId, title, subtitle) {
    const grid = ensureGrid(pageId);
    if (!grid) return null;

    let card = document.getElementById(cardId);
    if (card) return card;

    card = document.createElement('div');
    card.className = 'card';
    card.id = cardId;
    card.innerHTML = [
      '<div class="sec-hdr">',
      '<div class="sh-title">' + escapeHtml(title) + '</div>',
      '<div class="sh-sub">' + escapeHtml(subtitle) + '</div>',
      '</div>',
      '<div data-admin-runtime-body class="admin-note">Loading...</div>',
    ].join('');

    grid.appendChild(card);
    return card;
  }

  function write(cardId, html) {
    const card = document.getElementById(cardId);
    if (!card) return;

    const body = card.querySelector('[data-admin-runtime-body]');
    if (!body) return;

    body.innerHTML = html;
  }

  function clearAuthState() {
    const keys = [
      'token',
      'access_token',
      'auth_token',
      'maestro_token',
      'maestro_auth_token',
      'pmk_token',
      'pmk_auth_token',
      'user',
      'role',
    ];

    keys.forEach((key) => {
      try { localStorage.removeItem(key); } catch (error) {}
      try { sessionStorage.removeItem(key); } catch (error) {}
    });

    try {
      document.cookie.split(';').forEach((cookie) => {
        const name = cookie.split('=')[0].trim();
        if (!name) return;
        document.cookie = name + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/';
      });
    } catch (error) {}
  }

  function bindTopActions() {
    const clientButton = document.getElementById('admin-client-console-btn');
    const logoutButton = document.getElementById('admin-logout-btn');

    if (clientButton) {
      clientButton.setAttribute('href', '/console');
      clientButton.onclick = function (event) {
        event.preventDefault();
        window.location.assign('/console');
        return false;
      };
    }

    if (logoutButton) {
      logoutButton.setAttribute('href', '/login?mode=admin');
      logoutButton.onclick = function (event) {
        event.preventDefault();
        clearAuthState();
        window.location.replace('/login?mode=admin');
        return false;
      };
    }
  }

  async function refreshHome() {
    const session = await safeGet('/auth/me');
    const live = await safeGet('/health/live');
    const ready = await safeGet('/health/ready');
    const providers = await safeGet('/adapters/status');
    const keys = await safeGet('/settings/api-keys');

    const providerRows = arrayFrom(providers.data, ['providers', 'items', 'data']);
    const keyRows = arrayFrom(keys.data, ['keys', 'items', 'data']);

    write(
      'admin-runtime-home-summary',
      kpis([
        { label: 'Session', value: session.ok ? 'OK' : 'ERR' },
        { label: 'Live', value: live.ok ? 'OK' : 'ERR' },
        { label: 'Ready', value: ready.ok ? 'OK' : 'ERR' },
        { label: 'Providers', value: providerRows.length },
        { label: 'API keys', value: keyRows.length },
      ]) +
        table(['Endpoint', 'State', 'Status'], endpointRows([session, live, ready, providers, keys])) +
        bars([
          { label: 'Session', value: session.ok ? 1 : 0 },
          { label: 'Live', value: live.ok ? 1 : 0 },
          { label: 'Ready', value: ready.ok ? 1 : 0 },
          { label: 'Providers', value: providerRows.length },
          { label: 'API keys', value: keyRows.length },
        ])
    );
  }

  async function refreshAdapters() {
    const providers = await safeGet('/adapters/status');
    const rows = arrayFrom(providers.data, ['providers', 'items', 'data']).map((provider) => ({
      Provider: provider.name || provider.provider || provider.provider_id || 'provider',
      Status: provider.status || provider.state || (provider.ready ? 'ready' : 'unknown'),
      Ready: provider.ready ?? provider.configured ?? '',
      Model: provider.model || '',
    }));

    write(
      'admin-runtime-adapters',
      table(['Endpoint', 'State', 'Status'], endpointRows([providers])) +
        table(['Provider', 'Status', 'Ready', 'Model'], rows) +
        bars(rows.map((row) => ({
          label: row.Provider,
          value: String(row.Ready) === 'true' || row.Status === 'ready' || row.Status === 'configured' ? 1 : 0,
        })))
    );
  }

  function renderApiKeys(result) {
    const rows = arrayFrom(result.data, ['keys', 'items', 'data']).map((key) => ({
      Name: key.name || key.label || key.key_id || key.id || 'key',
      Status: key.status || (key.revoked ? 'revoked' : 'active'),
      Scopes: Array.isArray(key.scopes) ? key.scopes.join(', ') : key.scopes || '',
      Usage: key.usage_count ?? key.used ?? key.monthly_usage ?? '',
      LastUsed: key.last_used_at || '',
    }));

    const active = rows.filter((row) => String(row.Status).toLowerCase() !== 'revoked').length;
    const revoked = rows.length - active;

    write(
      'admin-runtime-api-keys',
      table(['Endpoint', 'State', 'Status'], endpointRows([result])) +
        table(['Name', 'Status', 'Scopes', 'Usage', 'LastUsed'], rows) +
        bars([
          { label: 'Active', value: active },
          { label: 'Revoked', value: revoked },
        ])
    );
  }

  async function refreshApiKeys() {
    const keys = await safeGet('/settings/api-keys');
    renderApiKeys(keys);

    const listTarget = document.getElementById('admin-api-key-list');
    if (listTarget) {
      listTarget.textContent = JSON.stringify(keys.data, null, 2);
    }
  }

  async function generateApiKey() {
    const output = document.getElementById('admin-api-key-create-result');
    const button = document.getElementById('admin-api-key-generate-btn');

    if (button) button.disabled = true;
    if (output) output.textContent = 'Generating...';

    const name = 'admin-generated-' + new Date().toISOString().replaceAll(':', '-').slice(0, 19);

    const payloads = [
      { name, label: name, scopes: ['cgt:govern', 'reports:read'] },
      { name, scopes: ['admin:settings'] },
      { label: name },
      {},
    ];

    const failures = [];

    for (const payload of payloads) {
      const result = await safePost('/settings/api-keys', payload);

      if (result.ok) {
        if (output) output.textContent = JSON.stringify(result.data, null, 2);
        await refreshApiKeys();
        if (button) button.disabled = false;
        return;
      }

      failures.push(result);
    }

    const fallback = await safePost('/settings/api-keys/generate', { name });

    if (fallback.ok) {
      if (output) output.textContent = JSON.stringify(fallback.data, null, 2);
      await refreshApiKeys();
      if (button) button.disabled = false;
      return;
    }

    failures.push(fallback);

    if (output) {
      output.textContent = JSON.stringify({
        error: 'API key generation failed',
        note: 'The admin runtime tried the known API key endpoints and payload shapes. Check backend schema or route availability.',
        attempts: failures,
      }, null, 2);
    }

    if (button) button.disabled = false;
  }

  function bindApiKeyButtons() {
    const generateButton = document.getElementById('admin-api-key-generate-btn');
    const refreshButton = document.getElementById('admin-api-key-refresh-btn');

    if (generateButton) {
      generateButton.onclick = function (event) {
        event.preventDefault();
        generateApiKey();
        return false;
      };
    }

    if (refreshButton) {
      refreshButton.onclick = function (event) {
        event.preventDefault();
        refreshApiKeys();
        return false;
      };
    }
  }

  async function refreshClients() {
    const applications = await safeGet('/applications');
    const billingEvents = await safeGet('/billing/events');
    const subscriptions = await safeGet('/billing/subscriptions');
    const plans = await safeGet('/billing/plans');

    write(
      'admin-runtime-clients',
      table(['Endpoint', 'State', 'Status'], endpointRows([applications, billingEvents, subscriptions, plans])) +
        '<div class="admin-note">Client supervision is ready on the frontend. Missing backend routes are shown as Not wired yet instead of mocked customer data.</div>'
    );
  }

  async function refreshUsage() {
    const usageLogs = await safeGet('/settings/usage-logs');
    const apiKeys = await safeGet('/settings/api-keys');
    const providers = await safeGet('/adapters/status');

    const keyCount = arrayFrom(apiKeys.data, ['keys', 'items', 'data']).length;
    const providerCount = arrayFrom(providers.data, ['providers', 'items', 'data']).length;

    write(
      'admin-runtime-usage',
      table(['Endpoint', 'State', 'Status'], endpointRows([usageLogs, apiKeys, providers])) +
        bars([
          { label: 'API keys', value: keyCount },
          { label: 'Providers', value: providerCount },
          { label: 'Usage route', value: usageLogs.ok ? 1 : 0 },
        ]) +
        '<div class="admin-note">Usage Monitor should include evaluations used, evaluations remaining, requests today, monthly requests, reports generated, errors, average latency, last API key usage, and quota status as backend endpoints become available.</div>'
    );
  }

  async function refreshProgress() {
    const checks = [
      { label: 'Admin/client separation', value: 1 },
      { label: 'Admin navigation', value: 1 },
      { label: 'Adapter Manager', value: (await safeGet('/adapters/status')).ok ? 1 : 0 },
      { label: 'API Keys registry', value: (await safeGet('/settings/api-keys')).ok ? 1 : 0 },
      { label: 'Health live', value: (await safeGet('/health/live')).ok ? 1 : 0 },
      { label: 'Health ready', value: (await safeGet('/health/ready')).ok ? 1 : 0 },
      { label: 'Clients backend', value: (await safeGet('/applications')).ok ? 1 : 0 },
      { label: 'Subscriptions backend', value: (await safeGet('/billing/subscriptions')).ok ? 1 : 0 },
    ];

    write(
      'admin-runtime-progress',
      table(['Checkpoint', 'State'], checks.map((item) => ({
        Checkpoint: item.label,
        State: item.value ? 'wired' : 'pending',
      }))) +
        bars(checks)
    );
  }

  async function refreshHealth() {
    const live = await safeGet('/health/live');
    const ready = await safeGet('/health/ready');
    const providers = await safeGet('/adapters/status');
    const usageLogs = await safeGet('/settings/usage-logs');

    write(
      'admin-runtime-health',
      table(['Endpoint', 'State', 'Status'], endpointRows([live, ready, providers, usageLogs])) +
        bars([
          { label: 'Live', value: live.ok ? 1 : 0 },
          { label: 'Ready', value: ready.ok ? 1 : 0 },
          { label: 'Providers', value: providers.ok ? 1 : 0 },
          { label: 'Usage logs', value: usageLogs.ok ? 1 : 0 },
        ]) +
        '<div class="admin-note">Future system health fields: telemetry state, audit storage, backup state, production warnings, and deployment runtime state.</div>'
    );
  }

  async function refreshSystemSettings() {
    const providers = await safeGet('/adapters/status');
    const keys = await safeGet('/settings/api-keys');
    const ready = await safeGet('/health/ready');

    write(
      'admin-runtime-system-settings',
      table(['Endpoint', 'State', 'Status'], endpointRows([providers, keys, ready])) +
        '<div class="admin-note">System Settings will host provider policy, notification routing, deployment controls, and production configuration checks. Only backend-backed state is shown here for now.</div>'
    );
  }

  function ensureCards() {
    installStyle();

    ensureCard('page-admin-home', 'admin-runtime-home-summary', 'Operations Summary', 'Live backend checks, provider readiness, and API key state');
    ensureCard('page-admin-home', 'admin-runtime-auth-state', 'Admin Auth Transport', 'Token/header availability used by backend calls');
    ensureCard('page-admin-adapters', 'admin-runtime-adapters', 'Provider Registry Table', 'Provider state from /adapters/status');
    ensureCard('page-admin-api-keys', 'admin-runtime-api-keys', 'API Keys Registry Table', 'Key metadata from /settings/api-keys');
    ensureCard('page-admin-clients', 'admin-runtime-clients', 'Client Supervision Coverage', 'Applications, billing, subscriptions, and plan endpoints');
    ensureCard('page-admin-usage', 'admin-runtime-usage', 'Usage Monitor Table', 'Usage, quota, provider, and API key backend coverage');
    ensureCard('page-admin-program-progress', 'admin-runtime-progress', 'Readiness Checklist', 'Program progress and pending backend coverage');
    ensureCard('page-admin-system-health', 'admin-runtime-health', 'Health and Readiness Table', 'Operational endpoint state');
    ensureCard('page-admin-system-settings', 'admin-runtime-system-settings', 'System Settings Coverage', 'Provider/settings/deployment route coverage');
  }

  async function refreshDashboard() {
    ensureCards();
    bindTopActions();
    bindApiKeyButtons();

    const authDiagnostic = window.PMK_ADMIN_AUTH ? PMK_ADMIN_AUTH.diagnostic() : {};
    write('admin-runtime-auth-state', table(['Field', 'Value'], [
      { Field: 'Bearer token found', Value: authHeaders().Authorization ? 'yes' : 'no' },
      { Field: 'Bearer storage key', Value: authDiagnostic.bearerKey || 'missing' },
      { Field: 'Authorization header', Value: hasHeader(authHeaders(), 'Authorization') ? 'present' : 'missing' },
      { Field: 'X-API-Key header', Value: hasHeader(authHeaders(), 'X-API-Key') ? 'present' : 'missing' },
      { Field: 'Local token keys', Value: JSON.stringify(authDiagnostic.localStorageKeys || []) },
      { Field: 'Session token keys', Value: JSON.stringify(authDiagnostic.sessionStorageKeys || []) },
    ]));

    await Promise.all([
      refreshHome(),
      refreshAdapters(),
      refreshApiKeys(),
      refreshClients(),
      refreshUsage(),
      refreshProgress(),
      refreshHealth(),
      refreshSystemSettings(),
    ]);
  }

  function boot() {
    bindTopActions();
    bindApiKeyButtons();
    setTimeout(refreshDashboard, 100);
    setTimeout(bindApiKeyButtons, 250);
  }

  window.PMK_ADMIN_ENDPOINT_REGISTRY = ADMIN_ENDPOINT_REGISTRY;

  window.PMK_ADMIN_RUNTIME = {
    refreshDashboard,
    generateApiKey,
    refreshApiKeys,
    safeGet,
    safePost,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
