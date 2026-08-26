(function () {
  'use strict';

  const ROOT_ID = 'am-operational-dashboard';

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function safeDate(value) {
    if (!value) return '—';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return '—';
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(parsed);
  }

  function authHeaders() {
    const headers = window.PMK_ADMIN_AUTH && typeof window.PMK_ADMIN_AUTH.headers === 'function'
      ? window.PMK_ADMIN_AUTH.headers()
      : new Headers();
    headers.set('Accept', 'application/json');
    return headers;
  }

  function ensureRoot() {
    const page = document.getElementById('page-admin-marketplace');
    if (!page) return null;
    let root = document.getElementById(ROOT_ID);
    if (root) return root;

    root = document.createElement('section');
    root.id = ROOT_ID;
    root.className = 'am-ops-dashboard';
    root.innerHTML = [
      '<div class="am-ops-heading">',
      '<div><h3>Commercial Operations</h3>',
      '<p>Authoritative trials, subscriptions, quota balances, channel governance, and verified-order value.</p></div>',
      '<button type="button" class="btn secondary sm" data-am-ops-refresh>Refresh</button>',
      '</div>',
      '<div class="am-ops-note">Verified-order value is an operational payment summary, not an accounting revenue-recognition statement.</div>',
      '<div class="am-ops-kpis">',
      '<div><span>Active trials</span><strong data-am-kpi="trials">—</strong></div>',
      '<div><span>Active subscriptions</span><strong data-am-kpi="subscriptions">—</strong></div>',
      '<div><span>Quota cycles</span><strong data-am-kpi="quotas">—</strong></div>',
      '<div><span>Channel reviews</span><strong data-am-kpi="reviews">—</strong></div>',
      '</div>',
      '<div class="am-ops-grid">',
      '<article><h4>Trials</h4><div data-am-ops-list="trials" class="am-ops-list"></div></article>',
      '<article><h4>Subscriptions</h4><div data-am-ops-list="subscriptions" class="am-ops-list"></div></article>',
      '<article><h4>Usage vs quotas</h4><div data-am-ops-list="quotas" class="am-ops-list"></div></article>',
      '<article><h4>Channel governance</h4><div data-am-ops-list="channels" class="am-ops-list"></div></article>',
      '<article class="am-ops-wide"><h4>Verified order value</h4><div data-am-ops-list="values" class="am-ops-list"></div></article>',
      '</div>',
      '<div class="am-ops-state" data-am-ops-state>Loading authoritative commercial state…</div>',
    ].join('');
    page.appendChild(root);
    const refresh = root.querySelector('[data-am-ops-refresh]');
    if (refresh) refresh.addEventListener('click', loadDashboard);
    return root;
  }

  function item(title, rows, badge) {
    return [
      '<div class="am-ops-item">',
      '<div class="am-ops-item-title"><strong>' + escapeHtml(title) + '</strong>',
      badge ? '<span>' + escapeHtml(badge) + '</span>' : '',
      '</div>',
      rows.map((row) => '<div><span>' + escapeHtml(row[0]) + '</span><b>' + escapeHtml(row[1]) + '</b></div>').join(''),
      '</div>',
    ].join('');
  }

  function renderList(root, name, content, emptyText) {
    const target = root.querySelector('[data-am-ops-list="' + name + '"]');
    if (!target) return;
    target.innerHTML = content.length ? content.join('') : '<div class="am-ops-empty">' + escapeHtml(emptyText) + '</div>';
  }

  function render(root, data) {
    const trials = Array.isArray(data.trials) ? data.trials : [];
    const subscriptions = Array.isArray(data.subscriptions) ? data.subscriptions : [];
    const quotas = Array.isArray(data.quotas) ? data.quotas : [];
    const channels = Array.isArray(data.channels) ? data.channels : [];
    const values = Array.isArray(data.verified_order_values) ? data.verified_order_values : [];

    root.querySelector('[data-am-kpi="trials"]').textContent = String(trials.filter((row) => row.status === 'active').length);
    root.querySelector('[data-am-kpi="subscriptions"]').textContent = String(subscriptions.filter((row) => row.status === 'active').length);
    root.querySelector('[data-am-kpi="quotas"]').textContent = String(quotas.length);
    root.querySelector('[data-am-kpi="reviews"]').textContent = String(channels.filter((row) => row.admin_review_required).length);

    renderList(root, 'trials', trials.map((row) => item(
      row.trial_ref,
      [['Customer', row.customer_ref], ['Plan', row.plan_code], ['Ends', safeDate(row.ends_at)]],
      row.status
    )), 'No trials are recorded.');

    renderList(root, 'subscriptions', subscriptions.map((row) => item(
      row.subscription_ref,
      [['Customer', row.customer_ref], ['Plan', row.plan_code], ['Ends', safeDate(row.ends_at)]],
      row.status
    )), 'No subscriptions are recorded.');

    renderList(root, 'quotas', quotas.map((row) => item(
      row.customer_ref,
      [
        ['Metric', row.metric_code],
        ['Used', row.used_units],
        ['Remaining', row.remaining_units],
        ['Base / rollover / top-up', row.base_limit_units + ' / ' + row.rollover_units + ' / ' + row.top_up_units],
        ['Period ends', safeDate(row.period_end)],
      ],
      row.rollover_status
    )), 'No quota cycles are recorded.');

    renderList(root, 'channels', channels.map((row) => item(
      row.customer_ref,
      [
        ['Country', row.country_code || '—'],
        ['Maestro Direct', row.maestro_direct_status],
        ['Lemon Squeezy', row.lemon_squeezy_status],
        ['Selected', row.selected_channel || 'Not selected'],
        ['Customer choice', row.customer_choice_allowed ? 'Allowed' : 'Not allowed'],
        ['Restriction', row.restriction_reason || 'None'],
      ],
      row.admin_review_required ? 'review required' : 'policy resolved'
    )), 'No channel-governance records are available.');

    renderList(root, 'values', values.map((row) => item(
      row.currency,
      [['Verified orders', row.verified_order_count], ['Verified order value', row.verified_order_value + ' ' + row.currency]],
      'payment verified'
    )), 'No payment-verified commercial orders are recorded.');
  }

  async function loadDashboard() {
    const root = ensureRoot();
    if (!root) return;
    const state = root.querySelector('[data-am-ops-state]');
    if (state) state.textContent = 'Loading authoritative commercial state…';
    try {
      const response = await fetch('/admin-marketplace/dashboard', {
        method: 'GET',
        credentials: 'include',
        headers: authHeaders(),
      });
      if (!response.ok) throw new Error('dashboard request failed');
      const data = await response.json();
      render(root, data || {});
      if (state) state.textContent = 'Authoritative commercial dashboard loaded.';
    } catch (error) {
      if (state) state.textContent = 'Commercial dashboard is unavailable. No state change was attempted.';
    }
  }

  function boot() {
    if (!ensureRoot()) return;
    loadDashboard();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
