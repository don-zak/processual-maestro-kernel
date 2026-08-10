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
      '.admin-data-table th,.admin-data-table td { border-bottom:1px solid var(--rim); text-align:left; padding:7px 8px; vertical-align:top; }',
      '.admin-data-table th { color:var(--ghost); font-family:var(--font-data); font-size:10px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; }',
      '.admin-status-ok { color:var(--ok); }',
      '.admin-status-warn { color:var(--warn); }',
      '.admin-status-error { color:var(--error); }',
      '.admin-bar-chart { display:grid; gap:8px; margin-top:var(--s-3); }',
      '.admin-bar-row { display:grid; grid-template-columns:minmax(96px,140px) 1fr 52px; align-items:center; gap:8px; font-family:var(--font-data); font-size:11px; }',
      '.admin-bar-row > :first-child { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--soft); }',
      '.admin-bar-row > :last-child { text-align:right; font-family:var(--font-mono); color:var(--bright); }',
      '.admin-bar-track { height:6px; border:1px solid var(--rim); border-radius:999px; overflow:hidden; background:var(--surface-0); }',
      '.admin-bar-fill { height:100%; width:0%; border-radius:999px; background:var(--amber); transition:width .25s ease; }',
      '.admin-card-note { color:var(--ghost); font-family:var(--font-data); font-size:11px; margin-top:var(--s-2); white-space:pre-wrap; }',
      '#admin-card-execution-observability { grid-column:1 / -1; }',
      '.admin-exec-shell { display:grid; gap:var(--s-4); }',
      '.admin-exec-context { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:var(--s-3); padding:10px 12px; border:1px solid var(--rim); border-radius:var(--radius); background:var(--surface-0); }',
      '.admin-exec-context-main { display:flex; flex-wrap:wrap; align-items:center; gap:8px; min-width:0; }',
      '.admin-exec-context-copy { color:var(--ghost); font-family:var(--font-data); font-size:10px; }',
      '.admin-exec-chip { display:inline-flex; align-items:center; min-height:24px; padding:3px 8px; border:1px solid var(--rim); border-radius:999px; background:var(--surface-2); color:var(--soft); font-family:var(--font-data); font-size:9px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; white-space:nowrap; }',
      '.admin-exec-chip.ok { border-color:rgba(34,211,160,.34); background:rgba(34,211,160,.09); color:var(--ok); }',
      '.admin-exec-chip.warn { border-color:rgba(251,191,36,.34); background:rgba(251,191,36,.09); color:var(--warn); }',
      '.admin-exec-chip.error { border-color:rgba(248,113,113,.34); background:rgba(248,113,113,.09); color:var(--error); }',
      '.admin-exec-kpis { display:grid; grid-template-columns:repeat(6,minmax(110px,1fr)); gap:var(--s-3); }',
      '.admin-exec-kpi { min-width:0; border:1px solid var(--rim); border-radius:var(--radius-lg); padding:12px; background:var(--surface-0); }',
      '.admin-exec-kpi .label { color:var(--ghost); font-family:var(--font-data); font-size:9px; letter-spacing:.08em; text-transform:uppercase; }',
      '.admin-exec-kpi .value { display:block; margin-top:3px; color:var(--bright); font-family:var(--font-mono); font-size:22px; font-weight:700; line-height:1.2; overflow-wrap:anywhere; }',
      '.admin-exec-kpi .hint { display:block; margin-top:4px; color:var(--muted); font-family:var(--font-data); font-size:9px; line-height:1.35; }',
      '.admin-exec-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:var(--s-3); }',
      '.admin-exec-panel { min-width:0; border:1px solid var(--rim); border-radius:var(--radius-lg); padding:12px; background:rgba(17,22,32,.55); }',
      '.admin-exec-panel-title { color:var(--soft); font-family:var(--font-data); font-size:10px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }',
      '.admin-exec-panel-sub { margin-top:2px; color:var(--muted); font-family:var(--font-data); font-size:9px; }',
      '.admin-exec-table-frame { width:100%; max-width:100%; overflow-x:auto; border:1px solid var(--rim); border-radius:var(--radius-lg); background:var(--surface-0); }',
      '.admin-exec-table { width:100%; min-width:880px; border-collapse:collapse; }',
      '.admin-exec-table th,.admin-exec-table td { padding:9px 10px; border-bottom:1px solid var(--rim); text-align:left; vertical-align:middle; }',
      '.admin-exec-table th { position:sticky; top:0; z-index:1; background:var(--surface-0); color:var(--ghost); font-family:var(--font-data); font-size:9px; letter-spacing:.07em; text-transform:uppercase; }',
      '.admin-exec-table td { color:var(--text); font-family:var(--font-data); font-size:10px; }',
      '.admin-exec-table tr:last-child td { border-bottom:0; }',
      '.admin-exec-id { display:block; max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--soft); font-family:var(--font-mono); font-size:9px; }',
      '.admin-exec-task { color:var(--bright); font-weight:600; }',
      '.admin-exec-secondary { color:var(--ghost); font-size:9px; }',
      '.admin-exec-empty { display:grid; place-items:center; min-height:128px; padding:var(--s-5); border:1px dashed var(--rim); border-radius:var(--radius-lg); text-align:center; background:var(--surface-0); }',
      '.admin-exec-empty strong { color:var(--bright); font-size:12px; }',
      '.admin-exec-empty span { max-width:520px; margin-top:4px; color:var(--ghost); font-family:var(--font-data); font-size:10px; }',
      '.admin-exec-footer { display:flex; flex-wrap:wrap; justify-content:space-between; gap:8px; color:var(--muted); font-family:var(--font-data); font-size:9px; }',
      '@media (max-width:1100px) { .admin-exec-kpis { grid-template-columns:repeat(3,minmax(110px,1fr)); } .admin-exec-grid { grid-template-columns:1fr 1fr; } .admin-exec-grid .admin-exec-panel:last-child { grid-column:1 / -1; } }',
      '@media (max-width:720px) { .admin-exec-kpis { grid-template-columns:repeat(2,minmax(0,1fr)); } .admin-exec-grid { grid-template-columns:1fr; } .admin-exec-grid .admin-exec-panel:last-child { grid-column:auto; } .admin-bar-row { grid-template-columns:90px 1fr 42px; } .admin-exec-context { align-items:flex-start; } }',
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
      '<div data-admin-card-body class="admin-card-note" aria-live="polite">Loading...</div>',
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
        const width = Math.max(value > 0 ? 4 : 0, Math.round((value / max) * 100));
        return [
          '<div class="admin-bar-row" title="' + escapeHtml(item.label) + ': ' + escapeHtml(value) + '">',
          '<div>' + escapeHtml(item.label) + '</div>',
          '<div class="admin-bar-track" role="img" aria-label="' + escapeHtml(item.label) + ' ' + escapeHtml(value) + '"><div class="admin-bar-fill" style="width:' + width + '%"></div></div>',
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

  function executionStatusTone(status) {
    const value = String(status || '').toLowerCase();
    if (value === 'success') return 'ok';
    if (value === 'partial_error') return 'warn';
    if (value === 'failed' || value === 'saturated') return 'error';
    return '';
  }

  function executionChip(value, tone) {
    return '<span class="admin-exec-chip ' + escapeHtml(tone || '') + '">' + escapeHtml(value || 'unknown') + '</span>';
  }

  function distributionPanel(title, subtitle, values) {
    const items = Object.entries(values || {}).map(([label, value]) => ({ label, value }));
    return [
      '<section class="admin-exec-panel" aria-label="' + escapeHtml(title) + '">',
      '<div class="admin-exec-panel-title">' + escapeHtml(title) + '</div>',
      '<div class="admin-exec-panel-sub">' + escapeHtml(subtitle) + '</div>',
      items.length ? bars(items) : '<div class="admin-card-note">No data yet.</div>',
      '</section>',
    ].join('');
  }

  function executionTable(records) {
    if (!records.length) {
      return [
        '<div class="admin-exec-empty" role="status">',
        '<div><strong>No execution evidence yet</strong><br>',
        '<span>The card will populate after a governed workflow run or Enterprise sandbox proof is recorded.</span></div>',
        '</div>',
      ].join('');
    }

    return [
      '<div class="admin-exec-table-frame" tabindex="0" aria-label="Recent task execution evidence">',
      '<table class="admin-exec-table">',
      '<thead><tr><th>Execution</th><th>Task</th><th>Kind</th><th>Environment</th><th>Status</th><th>Binding / Provider</th><th>Duration</th></tr></thead>',
      '<tbody>',
      records.map((item) => {
        const bindingOrProvider = item.binding_id || item.provider || '—';
        const secondary = item.binding_id && item.provider ? '<div class="admin-exec-secondary">' + escapeHtml(item.provider) + '</div>' : '';
        return [
          '<tr>',
          '<td><span class="admin-exec-id" title="' + escapeHtml(item.execution_id) + '">' + escapeHtml(item.execution_id) + '</span></td>',
          '<td><span class="admin-exec-task">' + escapeHtml(item.task_id) + '</span></td>',
          '<td>' + executionChip(item.execution_kind || 'task', '') + '</td>',
          '<td>' + executionChip(item.environment || 'runtime', item.environment === 'sandbox' ? 'warn' : '') + '</td>',
          '<td>' + executionChip(item.status, executionStatusTone(item.status)) + '</td>',
          '<td><span class="admin-exec-secondary">' + escapeHtml(bindingOrProvider) + '</span>' + secondary + '</td>',
          '<td><span class="font-mono">' + escapeHtml(Math.round(Number(item.duration_ms) || 0)) + ' ms</span></td>',
          '</tr>',
        ].join('');
      }).join(''),
      '</tbody></table></div>',
    ].join('');
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
        '<div class="admin-card-note">System usage remains separate from task execution observability below.</div>'
    );
  }

  async function refreshExecutionObservability() {
    const result = await safeGet('/settings/execution-observability/summary?limit=20');
    if (!result.ok || !result.data) {
      write(
        'admin-card-execution-observability',
        '<div class="admin-exec-shell"><div class="admin-exec-empty" role="alert"><div><strong>Execution observability unavailable</strong><br><span>The canonical execution endpoint could not be read. No synthetic execution metrics are displayed.</span></div></div></div>'
      );
      return;
    }

    const summary = result.data.summary || {};
    const recent = Array.isArray(result.data.recent_executions) ? result.data.recent_executions : [];
    const kpis = [
      ['Executions', summary.executions_total ?? 0, 'Canonical records'],
      ['Success rate', String(summary.success_rate_percent ?? 0) + '%', 'Completed executions'],
      ['Failed', summary.executions_failed ?? 0, 'Failed + saturated'],
      ['Avg latency', String(summary.average_latency_ms ?? 0) + ' ms', 'Across recorded executions'],
      ['Items succeeded', summary.items_succeeded ?? 0, 'Successful work items'],
      ['Items failed', summary.items_failed ?? 0, 'Failed work items'],
    ];
    const kpiHtml = '<div class="admin-exec-kpis">' + kpis.map(([label, value, hint]) => [
      '<div class="admin-exec-kpi">',
      '<span class="label">' + escapeHtml(label) + '</span>',
      '<strong class="value">' + escapeHtml(value) + '</strong>',
      '<span class="hint">' + escapeHtml(hint) + '</span>',
      '</div>',
    ].join('')).join('') + '</div>';
    const sourceReady = result.data.source_of_truth === 'canonical_execution_records';
    const reconciliation = result.data.reconciliation || {};
    const contextHtml = [
      '<div class="admin-exec-context">',
      '<div class="admin-exec-context-main">',
      executionChip('canonical source', sourceReady ? 'ok' : 'warn'),
      executionChip(reconciliation.aggregates_derived_from_records ? 'reconciled' : 'unverified', reconciliation.aggregates_derived_from_records ? 'ok' : 'warn'),
      '<span class="admin-exec-context-copy">Runtime and governed sandbox evidence share one read model, but remain visibly separated by kind and environment.</span>',
      '</div>',
      '<span class="admin-exec-context-copy">Showing ' + escapeHtml(recent.length) + ' of ' + escapeHtml(result.data.record_count ?? 0) + ' records</span>',
      '</div>',
    ].join('');
    const distributionHtml = [
      '<div class="admin-exec-grid">',
      distributionPanel('Execution kind', 'Workflow runs vs governed proof executions', result.data.by_execution_kind),
      distributionPanel('Environment', 'Runtime and sandbox stay distinct', result.data.by_environment),
      distributionPanel('Task distribution', 'Canonical Maestro task ids', result.data.by_task),
      '</div>',
    ].join('');

    write(
      'admin-card-execution-observability',
      [
        '<div class="admin-exec-shell">',
        contextHtml,
        kpiHtml,
        distributionHtml,
        executionTable(recent),
        '<div class="admin-exec-footer">',
        '<span>Source: canonical execution records · scope: admin:usage:read</span>',
        '<span>Health/readiness is operational state, not task execution evidence.</span>',
        '</div>',
        '</div>',
      ].join('')
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
        '<div class="admin-card-note">System health is operational state; it is intentionally not used as evidence that tasks executed successfully.</div>'
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
    ensureCard('page-admin-usage', 'admin-card-execution-observability', 'Task Execution Observability', 'Canonical task evidence, environment posture, and recent executions');
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
      refreshExecutionObservability(),
      refreshProgress(),
      refreshSystemHealthDetail(),
    ]);
  }

  window.PMK_ADMIN_DASHBOARD = {
    refreshDashboard,
    safeGet,
    refreshExecutionObservability,
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
