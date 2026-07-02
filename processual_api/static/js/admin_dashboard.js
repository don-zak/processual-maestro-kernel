(function () {
  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function installDashboardStyle() {
    if (document.getElementById('admin-dashboard-style')) return;

    const style = document.createElement('style');
    style.id = 'admin-dashboard-style';
    style.textContent = [
      '.admin-dashboard-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:var(--s-4); margin-top:var(--s-4); }',
      '.admin-data-table { width:100%; border-collapse:collapse; font-size:11px; margin-top:var(--s-3); }',
      '.admin-data-table th,.admin-data-table td { border-bottom:1px solid var(--line); text-align:left; padding:7px 8px; vertical-align:top; }',
      '.admin-data-table th { color:var(--muted); font-weight:600; }',
      '.admin-status-ok { color:var(--ok); }',
      '.admin-status-warn { color:var(--warn); }',
      '.admin-status-error { color:var(--error); }',
      '.admin-bar-chart { display:grid; gap:8px; margin-top:var(--s-3); }',
      '.admin-bar-row { display:grid; grid-template-columns:120px 1fr 52px; align-items:center; gap:8px; font-size:11px; }',
      '.admin-bar-track { height:9px; border:1px solid var(--line); border-radius:999px; overflow:hidden; background:rgba(255,255,255,.04); }',
      '.admin-bar-fill { height:100%; width:0%; background:var(--accent); }',
      '.admin-card-note { color:var(--muted); font-size:11px; margin-top:var(--s-2); white-space:pre-wrap; }',
    ].join('\n');

    document.head.appendChild(style);
  }

  async function safeGet(path) {
    try {
      if (!window.CLIENT || typeof CLIENT.get !== 'function') {
        return { ok: false, path, status: 'client-missing', data: null };
      }

      const data = await CLIENT.get(path);
      return { ok: true, path, status: 200, data };
    } catch (error) {
      return {
        ok: false,
        path,
        status: error.status || error.status_code || error.code || 'not-wired',
        data: error.detail || error.message || 'Not wired yet',
      };
    }
  }

  function page(pageId) {
    return document.getElementById(pageId);
  }

  function ensureCard(pageId, cardId, title, subtitle) {
    const targetPage = page(pageId);
    if (!targetPage) return null;

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
      '<div data-admin-card-body class="admin-card-note">Loading...</div>',
    ].join('');

    let grid = targetPage.querySelector('.admin-dashboard-grid');
    if (!grid) {
      grid = document.createElement('div');
      grid.className = 'admin-dashboard-grid';
      const container = targetPage.querySelector('div') || targetPage;
      container.appendChild(grid);
    }

    grid.appendChild(card);
    return card;
  }

  function body(cardId) {
    const card = document.getElementById(cardId);
    if (!card) return null;
    return card.querySelector('[data-admin-card-body]');
  }

  function table(headers, rows) {
    if (!rows.length) {
      return '<div class="admin-card-note">No rows returned.</div>';
    }

    return [
      '<table class="admin-data-table">',
      '<thead><tr>' + headers.map((h) => '<th>' + escapeHtml(h) + '</th>').join('') + '</tr></thead>',
      '<tbody>',
      rows.map((row) =>
        '<tr>' + headers.map((h) => '<td>' + escapeHtml(row[h] ?? '') + '</td>').join('') + '</tr>'
      ).join(''),
      '</tbody></table>',
    ].join('');
  }

  function bars(items) {
    const max = Math.max(1, ...items.map((item) => Number(item.value) || 0));

    return [
      '<div class="admin-bar-chart">',
      items.map((item) => {
        const value = Number(item.value) || 0;
        const width = Math.max(4, Math.round((value / max) * 100));
        return [
          '<div class="admin-bar-row">',
          '<div>' + escapeHtml(item.label) + '</div>',
          '<div class="admin-bar-track"><div class="admin-bar-fill" style="width:' + width + '%"></div></div>',
          '<div>' + escapeHtml(value) + '</div>',
          '</div>',
        ].join('');
      }).join(''),
      '</div>',
    ].join('');
  }

  function write(cardId, html) {
    const target = body(cardId);
    if (!target) return;
    target.innerHTML = html;
  }

  function statusClass(result) {
    if (result.ok) return 'admin-status-ok';
    if (result.status === 'not-wired' || result.status === 404) return 'admin-status-warn';
    return 'admin-status-error';
  }

  function endpointTable(results) {
    return table(
      ['Endpoint', 'State', 'Status'],
      results.map((result) => ({
        Endpoint: result.path,
        State: result.ok ? 'wired' : 'Not wired yet',
        Status: result.status,
      }))
    );
  }

  function arrayFrom(data, keys) {
    if (Array.isArray(data)) return data;

    for (const key of keys) {
      if (data && Array.isArray(data[key])) return data[key];
    }

    return [];
  }

  async function refreshHome() {
    const session = await safeGet('/auth/me');
    const live = await safeGet('/health/live');
    const ready = await safeGet('/health/ready');
    const providers = await safeGet('/adapters/status');

    write(
      'admin-card-session',
      endpointTable([session]) +
        table(['Field', 'Value'], Object.entries(session.data || {}).slice(0, 8).map(([key, value]) => ({
          Field: key,
          Value: typeof value === 'object' ? JSON.stringify(value) : value,
        })))
    );

    write(
      'admin-card-health',
      endpointTable([live, ready]) +
        bars([
          { label: 'Live', value: live.ok ? 1 : 0 },
          { label: 'Ready', value: ready.ok ? 1 : 0 },
        ])
    );

    const providerRows = arrayFrom(providers.data, ['providers', 'items', 'data']).map((provider) => ({
      Provider: provider.name || provider.provider || provider.provider_id || 'provider',
      Status: provider.status || provider.state || (provider.ready ? 'ready' : 'unknown'),
      Ready: provider.ready ?? provider.configured ?? '',
    }));

    write(
      'admin-card-providers',
      endpointTable([providers]) +
        table(['Provider', 'Status', 'Ready'], providerRows) +
        bars(providerRows.map((row) => ({ label: row.Provider, value: String(row.Ready) === 'true' || row.Status === 'ready' ? 1 : 0 })))
    );
  }

  async function refreshApiKeys() {
    const keys = await safeGet('/settings/api-keys');
    const rows = arrayFrom(keys.data, ['keys', 'items', 'data']).map((key) => ({
      Name: key.name || key.label || key.key_id || key.id || 'key',
      Status: key.status || (key.revoked ? 'revoked' : 'active'),
      Scopes: Array.isArray(key.scopes) ? key.scopes.join(', ') : key.scopes || '',
      Usage: key.usage_count ?? key.used ?? '',
      LastUsed: key.last_used_at || '',
    }));

    const active = rows.filter((row) => String(row.Status).toLowerCase() !== 'revoked').length;
    const revoked = rows.length - active;

    write(
      'admin-card-api-keys',
      endpointTable([keys]) +
        table(['Name', 'Status', 'Scopes', 'Usage', 'LastUsed'], rows) +
        bars([
          { label: 'Active', value: active },
          { label: 'Revoked', value: revoked },
        ])
    );
  }

  async function refreshClients() {
    const applications = await safeGet('/applications');
    const billingEvents = await safeGet('/billing/events');
    const subscriptions = await safeGet('/billing/subscriptions');

    write(
      'admin-card-clients',
      endpointTable([applications, billingEvents, subscriptions]) +
        '<div class="admin-card-note">Client supervision needs backend routes for applications, subscriptions, billing state, pilot state, and Bridge to Client Console. Missing endpoints are shown explicitly, not mocked.</div>'
    );
  }

  async function refreshUsage() {
    const usageLogs = await safeGet('/settings/usage-logs');
    const apiKeys = await safeGet('/settings/api-keys');
    const providers = await safeGet('/adapters/status');

    const providerCount = arrayFrom(providers.data, ['providers', 'items', 'data']).length;
    const keyCount = arrayFrom(apiKeys.data, ['keys', 'items', 'data']).length;

    write(
      'admin-card-usage',
      endpointTable([usageLogs, apiKeys, providers]) +
        bars([
          { label: 'API keys', value: keyCount },
          { label: 'Providers', value: providerCount },
          { label: 'Usage route', value: usageLogs.ok ? 1 : 0 },
        ]) +
        '<div class="admin-card-note">Usage Monitor should eventually include evaluations used, evaluations remaining, requests today, monthly requests, reports generated, errors, latency, and quota status.</div>'
    );
  }

  async function refreshProgress() {
    const live = await safeGet('/health/live');
    const ready = await safeGet('/health/ready');
    const me = await safeGet('/auth/me');
    const providers = await safeGet('/adapters/status');
    const keys = await safeGet('/settings/api-keys');

    const checkpoints = [
      { label: 'Admin session', value: me.ok ? 1 : 0 },
      { label: 'Health live', value: live.ok ? 1 : 0 },
      { label: 'Health ready', value: ready.ok ? 1 : 0 },
      { label: 'Providers', value: providers.ok ? 1 : 0 },
      { label: 'API keys', value: keys.ok ? 1 : 0 },
      { label: 'Client supervision', value: 0 },
      { label: 'Subscriptions', value: 0 },
      { label: 'Cloud Run readiness', value: ready.ok ? 1 : 0 },
    ];

    write(
      'admin-card-progress',
      table(['Checkpoint', 'State'], checkpoints.map((item) => ({
        Checkpoint: item.label,
        State: item.value ? 'wired' : 'pending',
      }))) +
        bars(checkpoints)
    );
  }

  async function refreshSystemHealthDetail() {
    const live = await safeGet('/health/live');
    const ready = await safeGet('/health/ready');
    const providers = await safeGet('/adapters/status');

    write(
      'admin-card-health-detail',
      endpointTable([live, ready, providers]) +
        '<div class="admin-card-note">System Health should also include telemetry, backup state, audit storage, usage logging, and production warning status when backend endpoints are available.</div>'
    );
  }

  function ensureDashboardCards() {
    installDashboardStyle();

    ensureCard('page-admin-home', 'admin-card-session', 'Admin Session', 'JWT role and scopes from /auth/me');
    ensureCard('page-admin-home', 'admin-card-health', 'System Health', '/health/live and /health/ready');
    ensureCard('page-admin-home', 'admin-card-providers', 'Provider Status', '/adapters/status');

    ensureCard('page-admin-api-keys', 'admin-card-api-keys', 'API Keys Registry', '/settings/api-keys');
    ensureCard('page-admin-clients', 'admin-card-clients', 'Clients, Applications, Subscriptions', 'Backend route coverage for customer supervision');
    ensureCard('page-admin-usage', 'admin-card-usage', 'Usage Monitor', 'Usage, quota, providers, and API key state');
    ensureCard('page-admin-program-progress', 'admin-card-progress', 'Program Progress', 'Readiness checkpoints and pending backend coverage');
    ensureCard('page-admin-system-health', 'admin-card-health-detail', 'System Health Detail', 'Backend health and readiness coverage');
  }

  async function refreshDashboard() {
    ensureDashboardCards();

    await Promise.all([
      refreshHome(),
      refreshApiKeys(),
      refreshClients(),
      refreshUsage(),
      refreshProgress(),
      refreshSystemHealthDetail(),
    ]);
  }

  window.PMK_ADMIN_DASHBOARD = {
    refreshDashboard,
    safeGet,
  };

  function boot() {
    setTimeout(refreshDashboard, 50);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
