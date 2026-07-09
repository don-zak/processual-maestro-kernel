(function () {
  const ENDPOINT = '/settings/admin/client-requests';
  const DETAIL_ENDPOINT_PREFIX = '/settings/admin/client-requests/';
  const PAGE_ID = 'page-admin-clients';
  const HOST_ID = 'admin-client-requests-host';
  const CARD_ID = 'admin-client-requests-card';
  const STYLE_ID = 'admin-client-requests-style';

  const FIELDS = [
    'request_id',
    'short_id',
    'client_id',
    'request_type',
    'requested_plan',
    'status',
    'created_at',
    'source',
  ];

  const DIRECT_ADMIN_PLAN_OPTIONS = [
    'enterprise',
  ];

  let lastLoadAt = 0;
  let scheduledRefresh = 0;

  function byId(id) {
    return document.getElementById(id);
  }

  function text(value) {
    return String(value ?? '');
  }

  function clear(node) {
    if (!node) return;
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function appendText(parent, tagName, value, className) {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    node.textContent = text(value);
    parent.appendChild(node);
    return node;
  }

  function installStyles() {
    if (byId(STYLE_ID)) return;

    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #admin-client-requests-host {
        margin-bottom: var(--s-5);
      }

      #admin-client-requests-card {
        overflow: hidden;
      }

      .admin-client-requests-topline {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: var(--s-3);
        flex-wrap: wrap;
      }

      .admin-client-requests-summary {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: var(--s-3);
        margin-top: var(--s-3);
      }

      .admin-client-requests-summary .mono-block {
        min-height: 74px;
      }

      .admin-client-request-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: var(--s-3);
        margin-top: var(--s-4);
      }

      .admin-client-request-row {
        border: 1px solid rgba(120, 150, 210, 0.28);
        border-radius: 14px;
        padding: var(--s-3);
        background: rgba(6, 12, 24, 0.28);
        min-width: 0;
      }

      .admin-client-request-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: var(--s-3);
        margin-bottom: var(--s-3);
      }

      .admin-client-request-title {
        font-weight: 700;
        letter-spacing: 0.04em;
        overflow-wrap: anywhere;
      }

      .admin-client-request-status {
        white-space: nowrap;
        border: 1px solid rgba(120, 150, 210, 0.35);
        border-radius: 999px;
        padding: 2px 8px;
        font-size: 11px;
      }

      .admin-client-request-meta {
        display: grid;
        grid-template-columns: 112px minmax(0, 1fr);
        gap: 6px 10px;
        font-size: 12px;
      }

      .admin-client-request-meta-key {
        opacity: 0.72;
      }

      .admin-client-request-meta-value {
        overflow-wrap: anywhere;
      }

      .admin-client-request-actions {
        margin-top: var(--s-3);
        display: flex;
        justify-content: flex-end;
      }
    `;
    document.head.appendChild(style);
  }

  const CLIENTS_STATUS_REVIEW_SCOPE = 'admin:clients:status_review';
  const CLIENTS_STATUS_DECIDE_SCOPE = 'admin:clients:status_decide';
  const CLIENTS_DRAFT_SCOPE = 'admin:clients:draft';
  const CLIENTS_RESPOND_SCOPE = 'admin:clients:respond';

  const ADMIN_SUPERVISOR_SCOPES = {
    owner_supervisor: ['*'],
    operations_supervisor: [
      CLIENTS_STATUS_REVIEW_SCOPE,
      CLIENTS_STATUS_DECIDE_SCOPE,
      CLIENTS_DRAFT_SCOPE,
      CLIENTS_RESPOND_SCOPE,
    ],
    review_supervisor: [CLIENTS_STATUS_REVIEW_SCOPE, CLIENTS_DRAFT_SCOPE],
  };

  const SUPERVISOR_SESSION_KEY_STORAGE_KEYS = [
    'pmk_supervisor_session_key',
    'admin_supervisor_session_key',
    'supervisor_session_key',
    'pmk_sup_session_key',
  ];

  const adminSupervisorSessionState = {
    loaded: false,
    user: null,
    level: '',
    scopes: [],
    sessionKeyId: '',
    validated: false,
  };

  function readStorageValue(keys) {
    for (const key of keys) {
      try {
        const localValue = localStorage.getItem(key);
        if (localValue) return localValue;
      } catch {}

      try {
        const sessionValue = sessionStorage.getItem(key);
        if (sessionValue) return sessionValue;
      } catch {}
    }

    return '';
  }

  function getAdminSupervisorSessionKey() {
    return readStorageValue(SUPERVISOR_SESSION_KEY_STORAGE_KEYS);
  }

  function normalizeScopeList(value) {
    if (!Array.isArray(value)) return [];
    return value
      .map((scope) => String(scope || '').trim())
      .filter(Boolean);
  }

  function inferAdminSupervisorScopes(level, user) {
    const explicit = normalizeScopeList(user?.supervision_scopes);
    if (explicit.length) return explicit;

    const normalLevel = String(level || '').trim().toLowerCase();
    const mapped = ADMIN_SUPERVISOR_SCOPES[normalLevel] || [];
    return mapped.slice();
  }

  function setAdminSupervisorSessionState(user) {
    const level = String(user?.supervision_level || '').trim().toLowerCase();
    adminSupervisorSessionState.loaded = true;
    adminSupervisorSessionState.user = user || null;
    adminSupervisorSessionState.level = level;
    adminSupervisorSessionState.scopes = inferAdminSupervisorScopes(level, user || {});
    adminSupervisorSessionState.sessionKeyId = String(
      user?.session_key_id || user?.supervisor_session_key_id || ''
    ).trim();
    adminSupervisorSessionState.validated = Boolean(
      user?.supervisor_session_validated || adminSupervisorSessionState.sessionKeyId
    );
    renderAdminSupervisorSessionSummary();
  }

  function supervisorSessionLabel() {
    if (!adminSupervisorSessionState.loaded) return 'checking';
    if (adminSupervisorSessionState.validated) return 'validated';
    if (adminSupervisorSessionState.level) return 'legacy-compatible';
    return 'legacy admin fallback';
  }

  function renderAdminSupervisorSessionSummary() {
    const status = byId('admin-supervisor-session-status');
    const level = byId('admin-supervisor-session-level');
    const scopes = byId('admin-supervisor-session-scopes');

    if (status) {
      status.textContent = 'Supervisor session: ' + supervisorSessionLabel();
    }
    if (level) {
      level.textContent =
        'Level: ' + (adminSupervisorSessionState.level || 'owner-compatible legacy admin');
    }
    if (scopes) {
      const listed = adminSupervisorSessionState.scopes.length
        ? adminSupervisorSessionState.scopes.join(', ')
        : 'backend fallback only';
      scopes.textContent = 'Scopes: ' + listed;
    }
  }

  async function fetchAdminSupervisorSessionState() {
    try {
      const data = await request('/auth/me');
      setAdminSupervisorSessionState(data || {});
      return data;
    } catch (error) {
      adminSupervisorSessionState.loaded = true;
      renderAdminSupervisorSessionSummary();
      return null;
    }
  }

  function refreshAdminSupervisorPermissionButtons() {
    document.querySelectorAll('[data-supervisor-scope]').forEach((button) => {
      const scope = button.dataset.supervisorScope || '';
      const reason =
        button.dataset.supervisorDisabledReason ||
        button.getAttribute('data-disabled-reason') ||
        '';
      applyAdminSupervisorPermission(button, scope, reason);
    });
  }

  async function refreshAdminSupervisorSessionState() {
    adminSupervisorSessionState.loaded = false;
    renderAdminSupervisorSessionSummary();
    await fetchAdminSupervisorSessionState();
    refreshAdminSupervisorPermissionButtons();
  }

  window.addEventListener('pmk-supervisor-session-key-updated', () => {
    refreshAdminSupervisorSessionState();
  });

  function canAdminSupervisorUse(requiredScope) {
    const scope = String(requiredScope || '').trim();
    if (!scope) return true;

    const rawScopes = Array.isArray(adminSupervisorSessionState.scopes)
      ? adminSupervisorSessionState.scopes
      : [];
    const authUserScopes =
      adminSupervisorSessionState.user && Array.isArray(adminSupervisorSessionState.user.scopes)
        ? adminSupervisorSessionState.user.scopes
        : [];
    const scopes = [...new Set([...rawScopes, ...authUserScopes])];
    if (scopes.includes('*')) return true;
    if (scopes.includes(scope)) return true;

    const level = adminSupervisorSessionState.level;
    const mapped = ADMIN_SUPERVISOR_SCOPES[level] || [];
    return mapped.includes('*') || mapped.includes(scope);
  }

  function applyAdminSupervisorPermission(button, requiredScope, reason) {
    if (!button) return;

    const scope = String(requiredScope || '').trim();
    if (!scope) return;

    button.dataset.supervisorScope = scope;
    if (reason) {
      button.dataset.supervisorDisabledReason = reason;
    }

    button.setAttribute('data-required-scope', scope);

    if (canAdminSupervisorUse(scope)) {
      button.removeAttribute('data-disabled-reason');
      if (button.dataset.rbacDisabled === 'true') {
        button.disabled = false;
        delete button.dataset.rbacDisabled;
      }
      if (button.title && button.title.includes('Requires supervisor scope')) {
        button.removeAttribute('title');
      }
      return;
    }

    const disabledReason =
      reason || 'Requires supervisor scope: ' + scope;
    button.disabled = true;
    button.dataset.rbacDisabled = 'true';
    button.setAttribute('data-disabled-reason', disabledReason);
    button.title = disabledReason;
  }

  function authHeaders(extra) {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') {
      return { ...auth.headers(), ...(extra || {}) };
    }

    const token =
      localStorage.getItem('access_token') ||
      localStorage.getItem('auth_token') ||
      localStorage.getItem('admin_token') ||
      sessionStorage.getItem('access_token') ||
      sessionStorage.getItem('auth_token') ||
      sessionStorage.getItem('admin_token');

    const supervisorSessionKey = getAdminSupervisorSessionKey();

    return {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(supervisorSessionKey
        ? { 'X-Supervisor-Session-Key': supervisorSessionKey }
        : {}),
      ...(extra || {}),
    };
  }

  async function request(path) {
    const response = await fetch(path, {
      method: 'GET',
      credentials: 'include',
      headers: authHeaders({ Accept: 'application/json' }),
    });

    const rawText = await response.text();
    let data = {};
    if (rawText) {
      try {
        data = JSON.parse(rawText);
      } catch {
        data = { message: rawText };
      }
    }

    if (!response.ok) {
      const detail =
        data && typeof data === 'object'
          ? data.detail || data.message || `HTTP ${response.status}`
          : `HTTP ${response.status}`;
      throw new Error(detail);
    }

    return data;
  }

  function ensureHost() {
    const page = byId(PAGE_ID);
    if (!page) return null;

    let host = byId(HOST_ID);
    if (host) return host;

    host = document.createElement('div');
    host.id = HOST_ID;

    const wrapper = page.firstElementChild || page;
    wrapper.insertBefore(host, wrapper.firstChild);

    return host;
  }

  function ensureCard() {
    installStyles();

    const host = ensureHost();
    if (!host) return null;

    let card = byId(CARD_ID);
    if (card && card.parentNode !== host) {
      host.appendChild(card);
      return card;
    }

    if (card) return card;

    card = document.createElement('div');
    card.id = CARD_ID;
    card.className = 'card';
    card.dataset.adminClientRequestsCard = '1';

    card.innerHTML = [
      '<div class="admin-client-requests-topline sec-hdr">',
      '<div>',
      '<div class="sh-title">Client Requests Inbox</div>',
      '<div class="sh-sub">Read-only supervisor view of client request summaries</div>',
      '</div>',
      '<button id="admin-client-requests-refresh-btn" class="btn sm" type="button">Refresh Requests</button>',
      '</div>',
      '<div class="admin-client-requests-summary">',
      '<div id="admin-client-requests-status" class="mono-block" style="font-size:11px;white-space:pre-wrap">Client request inbox not loaded yet.</div>',
      '<div id="admin-client-requests-counts" class="mono-block" style="font-size:11px;white-space:pre-wrap"></div>',
      '</div>',
      '<div id="admin-client-requests-list"></div>',
      '<div id="admin-client-request-detail">',
      '<div class="admin-client-request-detail-title">Request Detail</div>',
      '<div id="admin-client-request-detail-status" class="mono-block" style="font-size:11px;white-space:pre-wrap">Select a request to view details.</div>',
      '<div id="admin-client-request-detail-body" style="margin-top:var(--s-3)"></div>',
      '</div>',
    ].join('');

    host.appendChild(card);
    return card;
  }

  function renderAdminClientApiKeysQuickBridge(parent) {   if (!parent || document.getElementById('admin-client-api-keys-quick-bridge')) return;   const panel = document.createElement('section');   panel.id = 'admin-client-api-keys-quick-bridge';   panel.className = 'admin-client-request-panel';   panel.setAttribute('aria-label', 'Admin API Keys quick bridge');   const title = document.createElement('h3');   title.textContent = 'Integration API Keys';   panel.appendChild(title);   const note = document.createElement('p');   note.className = 'text-muted';   note.textContent = 'Open the Admin API Keys panel from the Clients area. Select a client request first to pre-fill client-specific metadata.';   panel.appendChild(note);   const actions = document.createElement('div');   actions.className = 'admin-client-request-actions';   const button = document.createElement('button');   button.id = 'admin-client-open-api-keys-panel';   button.className = 'btn sm';   button.type = 'button';   button.textContent = 'Open Integration API Keys';   button.addEventListener('click', () => {     const payload = {       source: 'admin_clients_quick_bridge',       key_profile: 'service_integration',       category: 'service_integration',       production_connector_approved: false,       raw_secret_visible: false,     };     try {       sessionStorage.setItem(ADMIN_INTEGRATION_KEY_BRIDGE_STORAGE, JSON.stringify(payload));     } catch {}     window.dispatchEvent(new CustomEvent('pmk-admin-integration-key-bridge', { detail: payload }));     const target = document.getElementById('admin-api-key-client-id') || document.getElementById('admin-api-key-create-result') || document.getElementById('admin-api-key-table');     if (target && target.scrollIntoView) {       target.scrollIntoView({ behavior: 'smooth', block: 'center' });     }   });   actions.appendChild(button);   const status = document.createElement('div');   status.id = 'admin-client-api-keys-quick-bridge-status';   status.className = 'admin-status';   status.textContent = 'Visible admin shortcut only. No raw secret is shown and no production connector is approved.';   actions.appendChild(status);   panel.appendChild(actions);   parent.appendChild(panel); } function renderCounts(counts) {
    const target = byId('admin-client-requests-counts');
    clear(target);
    if (!target) return;

    const entries = Object.entries(counts || {});
    if (entries.length === 0) {
      target.textContent = 'status_counts: none';
      return;
    }

    target.textContent = entries
      .map(([key, value]) => `${key}: ${value}`)
      .join('\n');
  }

  function appendMeta(row, key, value) {
    appendText(row, 'div', key, 'admin-client-request-meta-key');
    appendText(row, 'div', value, 'admin-client-request-meta-value');
  }

  function renderRequestCard(item) {
    const row = document.createElement('div');
    row.className = 'admin-client-request-row';
    row.dataset.requestId = text(item?.request_id || '');

    const head = document.createElement('div');
    head.className = 'admin-client-request-head';

    const title = document.createElement('div');
    title.className = 'admin-client-request-title';
    title.textContent = text(item?.request_type || 'client_request');

    const status = document.createElement('div');
    status.className = 'admin-client-request-status';
    status.textContent = text(item?.status || 'pending');

    head.appendChild(title);
    head.appendChild(status);
    row.appendChild(head);

    const meta = document.createElement('div');
    meta.className = 'admin-client-request-meta';
    appendMeta(meta, 'request_id', item?.request_id || '');
    appendMeta(meta, 'short_id', item?.short_id || '');
    appendMeta(meta, 'client_id', item?.client_id || '');
    appendMeta(meta, 'requested_plan', item?.requested_plan || '');
    appendMeta(meta, 'created_at', item?.created_at || '');
    appendMeta(meta, 'source', item?.source || '');
    row.appendChild(meta);

    const actions = document.createElement('div');
    actions.className = 'admin-client-request-actions';

    const button = document.createElement('button');
    button.className = 'btn secondary sm admin-client-request-select';
    button.type = 'button';
    button.dataset.requestId = text(item?.request_id || '');
    button.textContent = 'Select';

    actions.appendChild(button);
    row.appendChild(actions);

    return row;
  }

  function renderList(requests) {
    const target = byId('admin-client-requests-list');
    clear(target);
    if (!target) return;

    if (!Array.isArray(requests) || requests.length === 0) {
      appendText(target, 'div', 'No client requests found.', 'admin-note');
      return;
    }

    const grid = document.createElement('div');
    grid.className = 'admin-client-request-grid';

    requests.forEach((item) => {
      grid.appendChild(renderRequestCard(item));
    });

    target.appendChild(grid);
  }



  async function postJson(path, payload) {
    const response = await fetch(path, {
      method: 'POST',
      credentials: 'include',
      headers: authHeaders({
        Accept: 'application/json',
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify(payload || {}),
    });

    const rawText = await response.text();
    let data = {};
    if (rawText) {
      try {
        data = JSON.parse(rawText);
      } catch {
        data = { message: rawText };
      }
    }

    if (!response.ok) {
      const detail =
        data && typeof data === 'object'
          ? data.detail || data.message || `HTTP ${response.status}`
          : `HTTP ${response.status}`;
      throw new Error(detail);
    }

    return data;
  }
  function detailPath(requestId) {
    return DETAIL_ENDPOINT_PREFIX + encodeURIComponent(text(requestId));
  }

  function statusPath(requestId) {
    return detailPath(requestId) + '/status';
  }

  function applyPlanPath(requestId) {
    return detailPath(requestId) + '/apply-plan';
  }

  function directClientPlanPath(clientId) {
    return '/settings/admin/clients/' + encodeURIComponent(text(clientId)) + '/plan';
  }



  function responseDraftPath(requestId) {
    return detailPath(requestId) + '/response-draft';
  }


  function supervisorResponsePath(requestId) {
    return detailPath(requestId) + '/supervisor-response';
  }


  function canShowAdminClientRequestApplyPlan(detail) {
    const requestStatus = text(detail?.status || '').trim().toLowerCase();
    const requestedPlan = text(detail?.requested_plan || '').trim();
    return Boolean(
      requestedPlan &&
        ['approved', 'completed'].includes(requestStatus) &&
        !detail?.plan_applied
    );
  }

  function hasAdminClientRequestPlanSummary(detail) {
    return Boolean(
      text(detail?.requested_plan || '').trim() ||
        text(detail?.approved_plan || '').trim() ||
        detail?.plan_applied
    );
  }

  function setAdminClientRequestApplyPlanStatus(message) {
    const target = byId('admin-client-request-apply-plan-status');
    if (target) {
      target.textContent = message;
    }
  }

  function renderAdminClientRequestApplyPlanPanel(detail, parent) {
    const requestId = text(detail?.request_id || detail?.short_id || '');
    if (!parent || !requestId || !hasAdminClientRequestPlanSummary(detail)) return;

    const section = document.createElement('section');
    section.id = 'admin-client-request-apply-plan';
    section.className = 'admin-client-request-apply-plan';
    section.style.marginTop = 'var(--s-3)';

    const title = document.createElement('h3');
    title.textContent = 'Requested Plan';
    section.appendChild(title);

    const summary = document.createElement('pre');
    summary.id = 'admin-client-request-apply-plan-summary';
    summary.className = 'admin-client-request-apply-plan-summary';
    summary.textContent = [
      'requested_plan: ' + text(detail?.requested_plan || ''),
      'approved_plan: ' + text(detail?.approved_plan || ''),
      'plan_source: ' + text(detail?.plan_source || ''),
      'plan_applied: ' + (detail?.plan_applied ? 'true' : 'false'),
      'plan_applied_at: ' + text(detail?.plan_applied_at || ''),
    ].join('\n');
    section.appendChild(summary);

    if (canShowAdminClientRequestApplyPlan(detail)) {
      const actions = document.createElement('div');
      actions.className = 'admin-client-request-apply-plan-actions';
      actions.style.display = 'flex';
      actions.style.gap = 'var(--s-2)';
      actions.style.flexWrap = 'wrap';

      const button = document.createElement('button');
      button.id = 'admin-client-request-apply-plan-button';
      button.className = 'primary-btn admin-client-request-apply-plan-button';
      button.type = 'button';
      button.dataset.requestId = requestId;
      button.dataset.supervisorScope = CLIENTS_STATUS_DECIDE_SCOPE;
      button.dataset.supervisorDisabledReason =
        'Requires supervisor scope: ' + CLIENTS_STATUS_DECIDE_SCOPE;
      button.textContent = 'Apply requested plan';
      applyAdminSupervisorPermission(
        button,
        CLIENTS_STATUS_DECIDE_SCOPE,
        'Requires supervisor scope: ' + CLIENTS_STATUS_DECIDE_SCOPE
      );
      button.addEventListener('click', () => {
        applyAdminClientRequestRequestedPlan(requestId);
      });
      actions.appendChild(button);
      section.appendChild(actions);
    }

    const status = document.createElement('pre');
    status.id = 'admin-client-request-apply-plan-status';
    status.className = 'admin-client-request-apply-plan-status';
    status.textContent = detail?.plan_applied
      ? 'Requested plan already applied.'
      : canShowAdminClientRequestApplyPlan(detail)
        ? 'Ready to apply requested plan.'
        : 'Requested plan is not ready to apply.';
    section.appendChild(status);

    parent.appendChild(section);
  }

  async function applyAdminClientRequestRequestedPlan(requestId) {
    setAdminClientRequestApplyPlanStatus(
      'Applying requested plan for request ' + text(requestId) + ' ...'
    );

    try {
      const data = await postJson(applyPlanPath(requestId), {});
      renderAdminClientRequestDetail(data?.request || {});
      setAdminClientRequestApplyPlanStatus(
        'Applied requested plan for request ' +
          text(requestId) +
          ': ' +
          text(data?.status || 'plan_applied') +
          '.'
      );
      return data;
    } catch (error) {
      setAdminClientRequestApplyPlanStatus(
        'Failed to apply requested plan: ' +
          (error && error.message ? error.message : String(error))
      );
      return null;
    }
  }

  function setAdminDirectClientPlanStatus(message) {
    const target = byId('admin-direct-client-plan-status');
    if (target) {
      target.textContent = message;
    }
  }

  function renderAdminDirectClientPlanPanel(detail, parent) {
    const clientId = text(detail?.client_id || detail?.user_id || '').trim();
    if (!parent || !clientId) return;

    const section = document.createElement('section');
    section.id = 'admin-direct-client-plan';
    section.className = 'admin-direct-client-plan';
    section.style.marginTop = 'var(--s-3)';

    const title = document.createElement('h3');
    title.textContent = 'Direct Client Plan';
    section.appendChild(title);

    const note = document.createElement('p');
    note.className = 'admin-note';
    note.textContent =
      'Set the verified client plan directly from Admin settings. Allowance is resolved from the pricing catalog; no manual allowance is stored.';
    section.appendChild(note);

    const summary = document.createElement('pre');
    summary.id = 'admin-direct-client-plan-summary';
    summary.className = 'admin-direct-client-plan-summary';
    summary.textContent = [
      'client_id: ' + clientId,
      'approved_plan: ' + text(detail?.approved_plan || ''),
      'plan_source: ' + text(detail?.plan_source || ''),
      'plan_applied: ' + (detail?.plan_applied ? 'true' : 'false'),
      'plan_applied_at: ' + text(detail?.plan_applied_at || ''),
      'plan_applied_by: ' + text(detail?.plan_applied_by || ''),
    ].join('\n');
    section.appendChild(summary);

    const actions = document.createElement('div');
    actions.className = 'admin-direct-client-plan-actions';
    actions.style.display = 'flex';
    actions.style.gap = 'var(--s-2)';
    actions.style.flexWrap = 'wrap';

    const select = document.createElement('select');
    select.id = 'admin-direct-client-plan-select';
    select.setAttribute('aria-label', 'Direct client plan');
    DIRECT_ADMIN_PLAN_OPTIONS.forEach((planId) => {
      const option = document.createElement('option');
      option.value = planId;
      option.textContent = planId;
      if (text(detail?.approved_plan || '').trim() === planId) {
        option.selected = true;
      }
      select.appendChild(option);
    });
    actions.appendChild(select);

    const button = document.createElement('button');
    button.id = 'admin-direct-client-plan-button';
    button.className = 'primary-btn admin-direct-client-plan-button';
    button.type = 'button';
    button.dataset.clientId = clientId;
    button.dataset.supervisorScope = CLIENTS_STATUS_DECIDE_SCOPE;
    button.dataset.supervisorDisabledReason =
      'Requires supervisor scope: ' + CLIENTS_STATUS_DECIDE_SCOPE;
    button.textContent = 'Set direct plan';
    applyAdminSupervisorPermission(
      button,
      CLIENTS_STATUS_DECIDE_SCOPE,
      'Requires supervisor scope: ' + CLIENTS_STATUS_DECIDE_SCOPE
    );
    button.addEventListener('click', () => {
      setAdminDirectClientPlan(clientId, select.value);
    });
    actions.appendChild(button);

    section.appendChild(actions);

    const status = document.createElement('pre');
    status.id = 'admin-direct-client-plan-status';
    status.className = 'admin-direct-client-plan-status';
    status.textContent =
      'Direct plan changes write plan_source=settings and use catalog allowance.';
    section.appendChild(status);

    parent.appendChild(section);
  }

  async function setAdminDirectClientPlan(clientId, planId) {
    setAdminDirectClientPlanStatus(
      'Setting direct client plan for ' +
        text(clientId) +
        ' to ' +
        text(planId) +
        ' ...'
    );

    try {
      const data = await postJson(directClientPlanPath(clientId), { plan_id: planId });
      const source = text(data?.settings?.plan_source || data?.plan?.source || 'settings');
      const allowance = text(data?.plan?.monthly_unit_allowance || '');
      setAdminDirectClientPlanStatus(
        'Direct client plan result: ' +
          text(data?.status || 'plan_set') +
          '; plan_id=' +
          text(data?.plan?.plan_id || planId) +
          '; plan_source=' +
          source +
          '; monthly_unit_allowance=' +
          allowance +
          '.'
      );
      return data;
    } catch (error) {
      setAdminDirectClientPlanStatus(
        'Failed to set direct client plan: ' +
          (error && error.message ? error.message : String(error))
      );
      return null;
    }
  }

  function renderAdminClientRequestStatusActions(detail, parent) {
    const requestId = text(detail?.request_id || '');
    if (!requestId) return;

    const actions = document.createElement('div');
    actions.id = 'admin-client-request-status-actions';
    actions.className = 'admin-client-request-status-actions';
    actions.style.marginTop = 'var(--s-3)';
    actions.style.display = 'flex';
    actions.style.gap = 'var(--s-2)';
    actions.style.flexWrap = 'wrap';

    const options = [
      ['reviewed', 'Mark Reviewed'],
      ['approved', 'Approve'],
      ['rejected', 'Reject'],
      ['completed', 'Complete'],
    ];

    options.forEach(([nextStatus, label]) => {
      const button = document.createElement('button');
      button.className = 'btn secondary sm admin-client-request-status-action';
      button.type = 'button';
      button.dataset.requestId = requestId;
      button.dataset.nextStatus = nextStatus;
      button.textContent = label;
      const requiredScope =
        nextStatus === 'reviewed'
          ? CLIENTS_STATUS_REVIEW_SCOPE
          : CLIENTS_STATUS_DECIDE_SCOPE;
      applyAdminSupervisorPermission(
        button,
        requiredScope,
        'Requires supervisor scope: ' + requiredScope
      );
      actions.appendChild(button);
    });

    const note = document.createElement('div');
    note.className = 'admin-note admin-client-request-action-scope-note';
    note.textContent =
      'Action permissions: Review requires admin:clients:status_review; Approve, Reject, Complete, and Apply requested plan require admin:clients:status_decide.';
    actions.appendChild(note);

    parent.appendChild(actions);
  }
  function renderTimeline(detail, parent) {
    const timeline = Array.isArray(detail?.timeline) ? detail.timeline : [];
    appendText(parent, 'div', 'timeline', 'admin-client-request-detail-title');

    const list = document.createElement('div');
    list.className = 'admin-client-request-timeline';

    if (timeline.length === 0) {
      appendText(list, 'div', 'No timeline entries returned.', 'admin-note');
    }

    timeline.forEach((item) => {
      const node = document.createElement('div');
      node.className = 'admin-client-request-timeline-item';
      node.textContent = [
        text(item?.status || item?.event || 'pending'),
        text(item?.at || ''),
        text(item?.source || ''),
      ]
        .filter(Boolean)
        .join(' | ');
      list.appendChild(node);
    });

    parent.appendChild(list);
  }


  function latestSupervisorResponseDraft(detail) {
    const drafts = Array.isArray(detail?.supervisor_response_drafts)
      ? detail.supervisor_response_drafts
      : [];
    return drafts.length ? drafts[drafts.length - 1] : null;
  }

  function setAdminClientRequestResponseDraftStatus(message) {
    const target = byId('admin-client-request-response-draft-status');
    if (target) {
      target.textContent = message;
    }
  }

  function adminClientRequestSupervisorResponses(detail) {
    return Array.isArray(detail?.supervisor_responses)
      ? detail.supervisor_responses
      : [];
  }

  function latestAdminClientRequestSupervisorResponse(detail) {
    const responses = adminClientRequestSupervisorResponses(detail);
    return responses.length ? responses[responses.length - 1] : null;
  }

  function adminClientRequestSupervisorResponseForDraft(detail, draftId) {
    const safeDraftId = text(draftId || '');
    if (!safeDraftId) return null;
    const responses = adminClientRequestSupervisorResponses(detail);
    for (let index = responses.length - 1; index >= 0; index -= 1) {
      const response = responses[index];
      if (text(response?.draft_id || '') === safeDraftId) {
        return response;
      }
    }
    return null;
  }

  function renderAdminClientRequestSentResponseSummary(detail, parent) {
    if (!parent) return;

    const responses = adminClientRequestSupervisorResponses(detail);
    const latestResponse = latestAdminClientRequestSupervisorResponse(detail);

    const summary = document.createElement('pre');
    summary.id = 'admin-client-request-supervisor-response-summary';
    summary.className = 'admin-client-request-supervisor-response-summary';

    if (!responses.length) {
      summary.textContent = 'Sent responses: 0';
    } else {
      summary.textContent = [
        'Sent responses: ' + String(responses.length),
        'Last sent response: ' +
          text(latestResponse?.sent_at || latestResponse?.response_id || ''),
        text(latestResponse?.body || ''),
      ]
        .filter(Boolean)
        .join('\n');
    }

    parent.appendChild(summary);
  }

  function renderAdminClientRequestResponseDraftPanel(detail, parent) {
    const requestId = detail?.request_id || detail?.short_id || '';
    if (!parent || !requestId) return;

    const latestDraft = latestSupervisorResponseDraft(detail);
    const sentDraftResponse = adminClientRequestSupervisorResponseForDraft(
      detail,
      latestDraft?.draft_id || ''
    );
    const isLatestDraftSent = Boolean(sentDraftResponse);
    const section = document.createElement('section');
    section.id = 'admin-client-request-response-draft';
    section.className = 'admin-client-request-response-draft';

    const title = document.createElement('h3');
    title.textContent = 'Supervisor Response Draft';
    section.appendChild(title);

    const help = document.createElement('p');
    help.className = 'muted';
    help.textContent = isLatestDraftSent
      ? 'This draft was already sent. Generate new response to continue safely.'
      : 'Draft, review, save, then send a supervisor response to the client timeline.';
    section.appendChild(help);

    const textarea = document.createElement('textarea');
    textarea.id = 'admin-client-request-response-draft-body';
    textarea.className = 'admin-client-request-response-draft-body';
    textarea.rows = 6;
    textarea.value = text(latestDraft?.body || '');
    textarea.dataset.draftId = text(latestDraft?.draft_id || '');
    textarea.placeholder = 'Generate or write a safe supervisor response draft.';
    section.appendChild(textarea);

    const actions = document.createElement('div');
    actions.className = 'admin-client-request-response-draft-actions';

    const generate = document.createElement('button');
    generate.id = 'admin-client-request-response-draft-generate';
    generate.className =
      'secondary-btn admin-client-request-response-draft-action admin-client-request-response-draft-generate';
    generate.type = 'button';
    generate.textContent = isLatestDraftSent ? 'Generate new response' : 'Generate Draft';
    applyAdminSupervisorPermission(generate, CLIENTS_DRAFT_SCOPE, 'Requires supervisor scope: ' + CLIENTS_DRAFT_SCOPE);
    generate.addEventListener('click', () => {
      generateAdminClientRequestResponseDraft(requestId);
    });
    actions.appendChild(generate);

    const save = document.createElement('button');
    save.id = 'admin-client-request-response-draft-save';
    save.className =
      'primary-btn admin-client-request-response-draft-action admin-client-request-response-draft-save';
    save.type = 'button';
    save.textContent = 'Save Draft';
    applyAdminSupervisorPermission(save, CLIENTS_DRAFT_SCOPE, 'Requires supervisor scope: ' + CLIENTS_DRAFT_SCOPE);
    save.addEventListener('click', () => {
      saveAdminClientRequestResponseDraft(requestId);
    });
    actions.appendChild(save);

    const send = document.createElement('button');
    send.id = 'admin-client-request-response-draft-send';
    send.className =
      'primary-btn admin-client-request-response-draft-action admin-client-request-response-draft-send';
    send.type = 'button';
    send.textContent = 'Send Response';
    send.disabled = isLatestDraftSent;
    if (isLatestDraftSent) {
      send.title = 'This draft was already sent. Generate new response before sending again.';
    }
    applyAdminSupervisorPermission(send, CLIENTS_RESPOND_SCOPE, 'Requires supervisor scope: ' + CLIENTS_RESPOND_SCOPE);
    send.addEventListener('click', () => {
      sendAdminClientRequestSupervisorResponse(requestId);
    });
    actions.appendChild(send);

    const copy = document.createElement('button');
    copy.id = 'admin-client-request-response-draft-copy';
    copy.className =
      'secondary-btn admin-client-request-response-draft-action admin-client-request-response-draft-copy';
    copy.type = 'button';
    copy.textContent = 'Copy Draft';
    copy.addEventListener('click', () => {
      copyAdminClientRequestResponseDraft();
    });
    actions.appendChild(copy);

    section.appendChild(actions);

    const status = document.createElement('pre');
    status.id = 'admin-client-request-response-draft-status';
    status.className = 'admin-client-request-response-draft-status';
    status.textContent = isLatestDraftSent
      ? 'Already sent: ' + text(sentDraftResponse?.sent_at || sentDraftResponse?.response_id || '')
      : latestDraft
        ? 'Draft saved: ' + text(latestDraft.updated_at || latestDraft.created_at || '')
        : 'No saved draft yet.';
    section.appendChild(status);
    renderAdminClientRequestSentResponseSummary(detail, section);

    parent.appendChild(section);
  }

  async function generateAdminClientRequestResponseDraft(requestId) {
    setAdminClientRequestResponseDraftStatus(
      'Generating draft for request ' + text(requestId) + ' ...'
    );

    try {
      const data = await postJson(responseDraftPath(requestId), {
        mode: 'generate',
      });
      renderAdminClientRequestDetail(data?.request || {});
      setAdminClientRequestResponseDraftStatus(
        'Generated draft for request ' + text(requestId) + '.'
      );
      return data;
    } catch (error) {
      setAdminClientRequestResponseDraftStatus(
        'Failed to generate draft: ' +
          (error && error.message ? error.message : String(error))
      );
      return null;
    }
  }

  async function saveAdminClientRequestResponseDraft(requestId, body) {
    const textarea = byId('admin-client-request-response-draft-body');
    const draftBody =
      typeof body === 'string' ? body : textarea && textarea.value ? textarea.value : '';

    setAdminClientRequestResponseDraftStatus(
      'Saving draft for request ' + text(requestId) + ' ...'
    );

    try {
      const data = await postJson(responseDraftPath(requestId), {
        mode: 'manual',
        draft: draftBody,
        note: 'Saved from Admin request detail panel.',
      });
      renderAdminClientRequestDetail(data?.request || {});
      setAdminClientRequestResponseDraftStatus(
        'Draft saved for request ' + text(requestId) + '.'
      );
      return data;
    } catch (error) {
      setAdminClientRequestResponseDraftStatus(
        'Failed to save draft: ' +
          (error && error.message ? error.message : String(error))
      );
      return null;
    }
  }


  async function sendAdminClientRequestSupervisorResponse(requestId, body) {
    const textarea = byId('admin-client-request-response-draft-body');
    const draftBody =
      typeof body === 'string' ? body : textarea && textarea.value ? textarea.value : '';
    const draftId = textarea?.dataset?.draftId || '';

    setAdminClientRequestResponseDraftStatus(
      'Sending supervisor response for request ' + text(requestId) + ' ...'
    );

    try {
      const data = await postJson(supervisorResponsePath(requestId), {
        body: draftBody,
        draft_id: draftId,
      });
      renderAdminClientRequestDetail(data?.request || {});
      await loadAdminClientRequests(true);
      if (data?.status === 'already_sent') {
        setAdminClientRequestResponseDraftStatus(
          'already_sent: Response already sent for request ' + text(requestId) + '.'
        );
      } else {
        setAdminClientRequestResponseDraftStatus(
          'supervisor_response_sent: Sent response for request ' + text(requestId) + '.'
        );
      }
      return data;
    } catch (error) {
      setAdminClientRequestResponseDraftStatus(
        'Failed to send supervisor response: ' +
          (error && error.message ? error.message : String(error))
      );
      return null;
    }
  }

  async function copyAdminClientRequestResponseDraft() {
    const textarea = byId('admin-client-request-response-draft-body');
    const value = textarea && textarea.value ? textarea.value : '';
    if (!value) {
      setAdminClientRequestResponseDraftStatus('No draft text to copy.');
      return false;
    }

    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(value);
      } else {
        textarea.focus();
        textarea.select();
        document.execCommand('copy');
      }
      setAdminClientRequestResponseDraftStatus('Draft copied.');
      return true;
    } catch (error) {
      setAdminClientRequestResponseDraftStatus(
        'Failed to copy draft: ' +
          (error && error.message ? error.message : String(error))
      );
      return false;
    }
  }



  // ADMIN-INTEGRATION-KEYS-11F bridge begin
  const ADMIN_INTEGRATION_KEY_BRIDGE_STORAGE = 'pmk_admin_integration_key_bridge';

  function adminIntegrationBridgeValue(value) {
    if (value === null || value === undefined) return '';
    return String(value);
  }

  function adminIntegrationKeyBridgePayload(detail) {
    const clientId = adminIntegrationBridgeValue(detail && detail.client_id);
    const userId = adminIntegrationBridgeValue(detail && detail.user_id);
    const requestId = adminIntegrationBridgeValue(
      detail && (detail.request_id || detail.short_id)
    );
    const requestedPlan = adminIntegrationBridgeValue(
      detail && (detail.requested_plan || detail.approved_plan)
    );

    return {
      source: 'admin_client_request_detail',
      request_id: requestId,
      client_id: clientId,
      user_id: userId,
      requested_plan: requestedPlan,
      key_profile: 'service_integration',
      category: 'service_integration',
      purpose: requestId
        ? 'Integration key provisioning review for request ' + requestId
        : 'Integration key provisioning review',
      label: clientId
        ? clientId + ' service integration key'
        : 'Service integration key',
      issued_to: userId || clientId,
      production_connector_approved: false,
      raw_secret_visible: false,
    };
  }

  function setAdminIntegrationKeyBridgeStatus(message) {
    const target = byId('admin-client-request-integration-key-bridge-status');
    if (target) target.textContent = message || '';
  }

  function setAdminIntegrationBridgeInput(id, value) {
    const input = document.getElementById(id);
    if (!input) return false;
    input.value = adminIntegrationBridgeValue(value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  function applyAdminIntegrationKeyBridgeDom(payload) {
    if (!payload) return false;

    let applied = false;

    const category = document.getElementById('admin-api-key-category');
    if (category) {
      category.value = 'service_integration';
      category.dispatchEvent(new Event('change', { bubbles: true }));
      applied = true;
    }

    applied =
      setAdminIntegrationBridgeInput('admin-api-key-client-id', payload.client_id) ||
      applied;
    applied =
      setAdminIntegrationBridgeInput('admin-api-key-user-id', payload.user_id) ||
      applied;
    applied =
      setAdminIntegrationBridgeInput(
        'admin-api-key-plan-id',
        payload.requested_plan
      ) || applied;
    applied =
      setAdminIntegrationBridgeInput('admin-api-key-purpose', payload.purpose) ||
      applied;
    applied =
      setAdminIntegrationBridgeInput('admin-api-key-label', payload.label) ||
      applied;
    applied =
      setAdminIntegrationBridgeInput('admin-api-key-issued-to', payload.issued_to) ||
      applied;

    const result = document.getElementById('admin-api-key-create-result');
    if (result && applied) {
      result.textContent =
        'Client integration key context loaded from Admin request detail. ' +
        'No raw secrets are shown. Production connector approval remains separate.';
    }

    return applied;
  }

  function openAdminIntegrationKeyBridge(detail) {
    const payload = adminIntegrationKeyBridgePayload(detail);

    if (!payload.client_id) {
      setAdminIntegrationKeyBridgeStatus(
        'Client ID is missing; cannot prepare integration key context.'
      );
      return;
    }

    try {
      sessionStorage.setItem(
        ADMIN_INTEGRATION_KEY_BRIDGE_STORAGE,
        JSON.stringify(payload)
      );
    } catch (error) {
      // Browser storage is optional; the custom event still carries the payload.
    }

    window.dispatchEvent(
      new CustomEvent('pmk-admin-integration-key-bridge', { detail: payload })
    );

    const applied = applyAdminIntegrationKeyBridgeDom(payload);
    const target =
      document.getElementById('admin-api-key-client-id') ||
      document.getElementById('admin-api-key-table') ||
      document.getElementById('admin-api-key-create-result');

    if (target && target.scrollIntoView) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    setAdminIntegrationKeyBridgeStatus(
      applied
        ? 'Integration key admin fields prepared for this client.'
        : 'Integration key context saved. Open the Admin API Keys panel to apply it.'
    );
  }

  function appendAdminIntegrationBridgeMeta(parent, label, value) {
    const row = document.createElement('div');
    row.className = 'admin-client-request-detail-row';

    const key = document.createElement('span');
    key.className = 'admin-client-request-detail-key';
    key.textContent = label;

    const val = document.createElement('span');
    val.className = 'admin-client-request-detail-value';
    val.textContent = adminIntegrationBridgeValue(value) || '-';

    row.appendChild(key);
    row.appendChild(val);
    parent.appendChild(row);
  }

  function renderAdminIntegrationKeyBridgePanel(detail, parent) {
    if (!parent) return;

    const payload = adminIntegrationKeyBridgePayload(detail);
    const panel = document.createElement('section');
    panel.id = 'admin-client-request-integration-key-bridge';
    panel.className = 'admin-client-request-panel';
    panel.setAttribute('aria-label', 'Admin integration key bridge');

    const title = document.createElement('h3');
    title.textContent = 'Integration Key Admin Bridge';
    panel.appendChild(title);

    const note = document.createElement('p');
    note.className = 'text-muted';
    note.textContent =
      'Prepare the Admin API Keys panel with this client context. This does not reveal raw secrets and does not approve a production connector.';
    panel.appendChild(note);

    const meta = document.createElement('div');
    meta.className = 'admin-client-request-detail-grid';
    appendAdminIntegrationBridgeMeta(meta, 'client_id', payload.client_id);
    appendAdminIntegrationBridgeMeta(meta, 'user_id', payload.user_id);
    appendAdminIntegrationBridgeMeta(meta, 'key_profile', 'service_integration');
    appendAdminIntegrationBridgeMeta(meta, 'production_connector_approved', 'false');
    panel.appendChild(meta);

    const actions = document.createElement('div');
    actions.className = 'admin-client-request-actions';

    const button = document.createElement('button');
    button.id = 'admin-client-request-open-integration-keys';
    button.className = 'btn sm';
    button.type = 'button';
    button.textContent = 'Open Integration API Keys';
    button.dataset.clientId = payload.client_id;
    button.dataset.keyProfile = 'service_integration';
    button.addEventListener('click', () => openAdminIntegrationKeyBridge(detail));
    actions.appendChild(button);

    const status = document.createElement('div');
    status.id = 'admin-client-request-integration-key-bridge-status';
    status.className = 'admin-status';
    status.textContent =
      'Ready to prepare service_integration key metadata. No raw integration key is displayed.';
    actions.appendChild(status);

    panel.appendChild(actions);
    parent.appendChild(panel);
  }
  // ADMIN-INTEGRATION-KEYS-11F bridge end


  function renderAdminClientRequestDetail(detail) {
    ensureCard();

    const statusTarget = byId('admin-client-request-detail-status');
    const body = byId('admin-client-request-detail-body');

    if (statusTarget) {
      statusTarget.textContent =
        'Loaded detail for ' + text(detail?.request_id || detail?.short_id || '');
    }

    clear(body);
    if (!body) return;

    const grid = document.createElement('div');
    grid.className = 'admin-client-request-detail-grid';

    appendMeta(grid, 'request_id', detail?.request_id || '');
    appendMeta(grid, 'short_id', detail?.short_id || '');
    appendMeta(grid, 'client_id', detail?.client_id || '');
    appendMeta(grid, 'user_id', detail?.user_id || '');
    appendMeta(grid, 'role', detail?.role || '');
    appendMeta(grid, 'request_type', detail?.request_type || '');
    appendMeta(grid, 'request_label', detail?.request_label || '');
    appendMeta(grid, 'requested_plan', detail?.requested_plan || '');
    appendMeta(grid, 'approved_plan', detail?.approved_plan || '');
    appendMeta(grid, 'plan_source', detail?.plan_source || '');
    appendMeta(grid, 'plan_applied', detail?.plan_applied ? 'true' : 'false');
    appendMeta(grid, 'plan_applied_at', detail?.plan_applied_at || '');
    appendMeta(grid, 'plan_applied_by', detail?.plan_applied_by || '');
    appendMeta(grid, 'status', detail?.status || '');
    appendMeta(grid, 'source', detail?.source || '');
    appendMeta(grid, 'created_at', detail?.created_at || '');
    appendMeta(grid, 'updated_at', detail?.updated_at || '');
    appendMeta(grid, 'message', detail?.message || '');
    appendMeta(grid, 'next_admin_action', detail?.next_admin_action || '');

    body.appendChild(grid);
    renderAdminClientRequestStatusActions(detail, body);
    renderAdminClientRequestApplyPlanPanel(detail, body);
    renderAdminDirectClientPlanPanel(detail, body);
    renderAdminIntegrationKeyBridgePanel(detail, body);
    renderAdminClientRequestResponseDraftPanel(detail, body);
    renderTimeline(detail, body);
    refreshAdminSupervisorPermissionButtons();
  }

  async function loadAdminClientRequestDetail(requestId) {
    ensureCard();

    const statusTarget = byId('admin-client-request-detail-status');
    const body = byId('admin-client-request-detail-body');
    clear(body);

    if (statusTarget) {
      statusTarget.textContent =
        'Loading detail for request ' + text(requestId) + ' ...';
    }

    try {
      const data = await request(detailPath(requestId));
      renderAdminClientRequestDetail(data?.request || {});
      return data;
    } catch (error) {
      if (statusTarget) {
        statusTarget.textContent =
          'Failed to load request detail: ' +
          (error && error.message ? error.message : String(error));
      }
      return null;
    }
  }

  async function updateAdminClientRequestStatus(requestId, nextStatus) {
    ensureCard();

    const statusTarget = byId('admin-client-request-detail-status');
    if (statusTarget) {
      statusTarget.textContent =
        'Updating request ' + text(requestId) + ' to ' + text(nextStatus) + ' ...';
    }

    try {
      const data = await postJson(statusPath(requestId), {
        status: nextStatus,
        note: 'Updated from Admin request detail panel.',
      });
      renderAdminClientRequestDetail(data?.request || {});
      await loadAdminClientRequests(true);
      return data;
    } catch (error) {
      if (statusTarget) {
        statusTarget.textContent =
          'Failed to update request status: ' +
          (error && error.message ? error.message : String(error));
      }
      return null;
    }
  }
  function renderAdminClientRequests(data) {
    ensureCard();

    const statusTarget = byId('admin-client-requests-status');
    if (statusTarget) {
      statusTarget.textContent = [
        `status: ${text(data?.status || 'unknown')}`,
        `request_count: ${text(data?.request_count ?? 0)}`,
        `latest_count: ${text(data?.latest_count ?? 0)}`,
        text(data?.message || ''),
      ].join('\n');
    }

    renderCounts(data?.status_counts || {});
    const card = byId(CARD_ID); renderAdminClientApiKeysQuickBridge(card); renderList(data?.latest_requests || []);
  }

  async function loadAdminClientRequests(force) {
    ensureCard();

    const now = Date.now();
    if (!force && now - lastLoadAt < 1500) {
      return null;
    }
    lastLoadAt = now;

    const statusTarget = byId('admin-client-requests-status');
    if (statusTarget) {
      statusTarget.textContent =
        'Loading admin client requests from ' + ENDPOINT + ' ...';
    }

    try {
      const data = await request(ENDPOINT);
      renderAdminClientRequests(data);
      return data;
    } catch (error) {
      if (statusTarget) {
        statusTarget.textContent =
          'Failed to load admin client requests: ' +
          (error && error.message ? error.message : String(error));
      }
      renderCounts({});
      renderList([]);
      return null;
    }
  }

  function bindAdminClientRequests() {
    ensureCard();

    const refresh = byId('admin-client-requests-refresh-btn');
    if (refresh && !refresh.dataset.boundAdminClientRequests) {
      refresh.dataset.boundAdminClientRequests = '1';
      refresh.addEventListener('click', () => {
        loadAdminClientRequests(true);
      });
    }
  }

  function refreshAdminClientRequestsSoon(force) {
    window.clearTimeout(scheduledRefresh);
    scheduledRefresh = window.setTimeout(() => {
      bindAdminClientRequests();
      loadAdminClientRequests(Boolean(force));
    }, 80);
  }

  function installPageActivationHooks() {
    document.addEventListener(
      'click',
      (event) => {
        const statusButton = event.target.closest('.admin-client-request-status-action');
        if (!statusButton) return;

        event.preventDefault();
        updateAdminClientRequestStatus(
          statusButton.dataset.requestId || '',
          statusButton.dataset.nextStatus || ''
        );
      },
      true
    );
    document.addEventListener(
      'click',
      (event) => {
        const selectButton = event.target.closest('.admin-client-request-select');
        if (!selectButton) return;
        event.preventDefault();
        loadAdminClientRequestDetail(selectButton.dataset.requestId || '');
      },
      true
    );
    document.addEventListener(
      'click',
      (event) => {
        const button = event.target.closest('[data-admin-page], .nav-btn');
        if (!button) return;

        const targetPage = button.dataset?.adminPage || '';
        const label = String(button.textContent || '').toLowerCase();
        if (targetPage === 'clients' || label.includes('clients')) {
          refreshAdminClientRequestsSoon(true);
        }
      },
      true
    );

    window.addEventListener('hashchange', () => {
      if (window.location.hash === '#clients') {
        refreshAdminClientRequestsSoon(true);
      }
    });

    const observer = new MutationObserver(() => {
      const page = byId(PAGE_ID);
      const host = byId(HOST_ID);
      const card = byId(CARD_ID);
      if (page && (!host || !card)) {
        refreshAdminClientRequestsSoon(false);
      }
    });

    if (document.body) {
      observer.observe(document.body, {
        childList: true,
        subtree: true,
      });
    }
  }

  function init() {
    bindAdminClientRequests();
    loadAdminClientRequests(false);
    installPageActivationHooks();

    [150, 500, 1000, 1800].forEach((delay) => {
      window.setTimeout(() => {
        bindAdminClientRequests();
        loadAdminClientRequests(false);
      }, delay);
    });
  }

  fetchAdminSupervisorSessionState();

  window.PMK_ADMIN_CLIENT_REQUESTS_RBAC_UI = {
    ADMIN_SUPERVISOR_SCOPES,
    SUPERVISOR_SESSION_KEY_STORAGE_KEYS,
    getAdminSupervisorSessionKey,
    canAdminSupervisorUse,
    applyAdminSupervisorPermission,
    renderAdminSupervisorSessionSummary,
    fetchAdminSupervisorSessionState,
  };

  window.PMK_ADMIN_CLIENT_REQUESTS = {
    bindAdminClientRequests,
    loadAdminClientRequests,
    loadAdminClientRequestDetail,
    updateAdminClientRequestStatus,
    generateAdminClientRequestResponseDraft,
    saveAdminClientRequestResponseDraft,
    sendAdminClientRequestSupervisorResponse,
    copyAdminClientRequestResponseDraft,
    renderAdminClientRequests,
    renderAdminClientRequestDetail,
    refreshAdminClientRequestsSoon,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

(function () {
  const CARD_ID = "admin-integration-readiness-card";
  const BODY_ID = "admin-integration-readiness-body";
  const ENDPOINT = "/settings/admin/integration-readiness";

  function readinessById(id) {
    return document.getElementById(id);
  }

  function readinessSetText(id, value) {
    const node = readinessById(id);
    if (node) node.textContent = value == null ? "-" : String(value);
  }

  function readinessAdminHeaders() {
    if (window.PMK_ADMIN_AUTH && typeof window.PMK_ADMIN_AUTH.headers === "function") {
      return window.PMK_ADMIN_AUTH.headers();
    }
    return { Accept: "application/json" };
  }

  function ensureIntegrationReadinessCard() {
    if (readinessById(CARD_ID)) return readinessById(CARD_ID);
    const parent = document.querySelector("main") || document.body;
    const card = document.createElement("section");
    card.id = CARD_ID;
    card.className = "admin-card";
    card.setAttribute("aria-label", "Admin integration readiness");
    card.innerHTML = [
      "<h2>Integration Readiness</h2>",
      "<p class=\"muted\">Read-only integration readiness checks for supervisors. No raw secrets, no external HTTP, no runtime connector approval.</p>",
      "<div class=\"admin-grid\">",
      "<div><strong>Total checks</strong><span id=\"admin-integration-readiness-total\">-</span></div>",
      "<div><strong>Blocked</strong><span id=\"admin-integration-readiness-blocked\">-</span></div>",
      "<div><strong>Sandbox ready</strong><span id=\"admin-integration-readiness-sandbox-ready\">-</span></div>",
      "<div><strong>Production allowed</strong><span id=\"admin-integration-readiness-production\">0</span></div>",
      "<div><strong>Runtime connector approved</strong><span id=\"admin-integration-readiness-runtime\">0</span></div>",
      "</div>",
      "<pre id=\"admin-integration-readiness-body\" class=\"mono-block\">Loading integration readiness...</pre>",
    ].join("");
    parent.appendChild(card);
    return card;
  }

  function displaySecurityItem13eH1(item) {
    return String(item || "-")
      .replaceAll("raw_secret_visible", "secret_visibility")
      .replaceAll("raw_secret", "secret_value")
      .replaceAll("raw_key", "one_time_key")
      .replaceAll("key_hash", "stored_hash");
  }

  function displaySecurityList13eH1(items) {
    return (items || []).map(displaySecurityItem13eH1).join(", ") || "-";
  }

  function readinessCheckLine(check) {
    return [
      "readiness_check_id=" + (check.readiness_check_id || "-"),
      "adapter_contract_id=" + (check.adapter_contract_id || "-"),
      "credential_profile_id=" + (check.credential_profile_id || "-"),
      "status=" + (check.status || "-"),
      "sandbox_ready=" + String(check.sandbox_ready === true),
      "production_allowed=" + String(check.production_allowed === true),
      "runtime_connector_approved=" + String(check.runtime_connector_approved === true),
      "missing_inputs=" + ((check.missing_inputs || []).join(", ") || "-"),
      "missing_security_controls=" + displaySecurityList13eH1(check.missing_security_controls),
      "blocking_reasons=" + ((check.blocking_reasons || []).join(", ") || "-"),
      "next_action=" + (check.next_action || "-"),
    ].join(" | ");
  }

  function renderIntegrationReadiness(data) {
    ensureIntegrationReadinessCard();
    const summary = data && data.summary ? data.summary : {};
    const checks = Array.isArray(data && data.checks) ? data.checks : [];
    readinessSetText("admin-integration-readiness-total", summary.total || 0);
    readinessSetText("admin-integration-readiness-blocked", summary.blocked || 0);
    readinessSetText("admin-integration-readiness-sandbox-ready", summary.sandbox_ready || 0);
    readinessSetText("admin-integration-readiness-production", summary.production_allowed || 0);
    readinessSetText("admin-integration-readiness-runtime", summary.runtime_connector_approved || 0);
    const lines = checks.map(readinessCheckLine);
    lines.unshift("Integration readiness is read-only. Production and runtime connector approvals remain false.");
    readinessSetText(BODY_ID, lines.join("\n\n"));
  }

  async function loadIntegrationReadiness() {
    ensureIntegrationReadinessCard();
    try {
      const response = await fetch(ENDPOINT, {
        credentials: "include",
        headers: readinessAdminHeaders(),
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const data = await response.json();
      renderIntegrationReadiness(data);
    } catch (error) {
      readinessSetText(BODY_ID, "Integration readiness unavailable: " + (error && error.message ? error.message : error));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadIntegrationReadiness);
  } else {
    loadIntegrationReadiness();
  }

  window.PMK_ADMIN_INTEGRATION_READINESS = { loadIntegrationReadiness };
})();

/* ADMIN_CLIENT_REQUEST_INTEGRATION_READINESS_WORKFLOW_11M_MARKER:
   supervisor workflow for integration readiness requests. */
(function () {
  "use strict";

  const WORKFLOW_MARKER = "adminreadinessworkflow11m";
  const WORKFLOW_EVENT = "pmk-admin-integration-key-bridge";

  let lastBridgeDetail = null;

  function getById(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    const element = getById(id);
    if (element) {
      element.textContent = value;
    }
  }

  function replaceList(id, items) {
    const list = getById(id);
    if (!list) {
      return;
    }

    list.innerHTML = "";
    items.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      list.appendChild(li);
    });
  }

  function workflowAnchor() {
    return (
      getById("admin-client-request-integration-key-bridge") ||
      getById("admin-client-api-keys-quick-bridge") ||
      getById("admin-client-request-detail") ||
      getById("admin-client-request-detail-card") ||
      document.querySelector("[data-admin-client-request-detail]") ||
      document.querySelector("main") ||
      document.body
    );
  }

  function ensureWorkflowCard() {
    let card = getById("admin-client-request-integration-readiness-workflow-card");
    if (card) {
      const host = trackingHost();
      if (host && card.parentNode !== host) {
        host.appendChild(card);
      }
      return card;
    }

    card = document.createElement("section");
    card.id = "admin-client-request-integration-readiness-workflow-card";
    card.className = "admin-card settings-card";
    card.dataset.phase = "INTEGRATION-READINESS-11M";
    card.dataset.cacheMarker = WORKFLOW_MARKER;
    card.setAttribute("aria-label", "Supervisor integration readiness workflow");

    card.innerHTML = `
      <div class="settings-card-header">
        <div>
          <p class="eyebrow">Supervisor workflow</p>
          <h3>Integration Readiness Review</h3>
        </div>
        <span
          id="admin-client-request-integration-readiness-status"
          class="status-pill"
        >Pending request context</span>
      </div>

      <p class="muted">
        Supervisor-only workflow for reviewing integration key/profile requests.
        This panel prepares sandbox review, client follow-up, and safe response
        drafting without enabling production connectors.
      </p>

      <dl class="settings-summary-grid" aria-label="Supervisor readiness summary">
        <div>
          <dt>Requested profile</dt>
          <dd id="admin-client-request-integration-readiness-profile">Not selected</dd>
        </div>
        <div>
          <dt>Sandbox review</dt>
          <dd id="admin-client-request-integration-readiness-sandbox">Pending</dd>
        </div>
        <div>
          <dt>Production connector approved</dt>
          <dd id="admin-client-request-integration-readiness-production">false</dd>
        </div>
        <div>
          <dt>Runtime connector approved</dt>
          <dd id="admin-client-request-integration-readiness-runtime">false</dd>
        </div>
      </dl>

      <div class="settings-grid two">
        <div>
          <h4>Readiness blockers</h4>
          <ul id="admin-client-request-integration-readiness-blockers">
            <li>Open an integration request or use the Integration API Keys bridge.</li>
          </ul>
        </div>
        <div>
          <h4>Supervisor next actions</h4>
          <ul id="admin-client-request-integration-readiness-actions">
            <li>Confirm the requested operational profile.</li>
            <li>Ask the client for missing sandbox documentation.</li>
            <li>Keep production approval separate.</li>
          </ul>
        </div>
      </div>

      <p id="admin-client-request-integration-readiness-safety" class="muted">
        Safety: no raw secrets, no customer credentials, no external HTTP calls,
        no runtime connector, and no production connector approval are enabled
        from this workflow.
      </p>

      <div class="settings-actions">
        <button
          id="admin-client-request-integration-readiness-draft-button"
          type="button"
        >Generate safe supervisor draft</button>
      </div>

      <textarea
        id="admin-client-request-integration-readiness-draft"
        rows="8"
        readonly
        aria-label="Safe supervisor response draft"
      ></textarea>
    `;

    const anchor = workflowAnchor();

    if (
      anchor &&
      anchor !== document.body &&
      anchor.parentNode &&
      anchor.parentNode.insertBefore
    ) {
      anchor.parentNode.insertBefore(card, anchor.nextSibling);
    } else if (anchor && anchor.appendChild) {
      anchor.appendChild(card);
    } else {
      document.body.appendChild(card);
    }

    return card;
  }

  function normalizeBridgeDetail(detail) {
    const source = detail && typeof detail === "object" ? detail : {};

    const requestedProfile =
      source.integrationKeyProfileId ||
      source.integration_key_profile_id ||
      source.operationalProfileId ||
      source.key_profile ||
      source.category ||
      "";

    const displayName =
      source.operationalProfileDisplayName ||
      source.operational_profile_display_name ||
      source.displayName ||
      source.display_name ||
      requestedProfile ||
      "Not selected";

    return {
      requestedProfile,
      displayName,
      source: source.source || "admin_client_request",
      category: source.category || source.key_profile || "",
      hasProfile: Boolean(requestedProfile),
    };
  }

  function supervisorDraftText(context) {
    const profile = context.hasProfile ? context.displayName : "the requested profile";

    return [
      "Hello,",
      "",
      `We reviewed your integration request for ${profile}.`,
      "",
      "Before sandbox readiness can be confirmed, please provide or confirm:",
      "- Sandbox API documentation or integration reference.",
      "- Customer-side technical contact and review path.",
      "- Expected read/write scope boundaries.",
      "- Security controls for sandbox-before-production review.",
      "",
      "Production connector approval remains separate.",
      "Runtime connectors are not approved from this request.",
      "No raw integration secret should be sent in this request.",
      "",
      "Once the missing items are provided, a supervisor can continue the sandbox readiness review.",
    ].join("\n");
  }

  function renderSupervisorIntegrationReadinessWorkflow(detail) {
    if (detail && typeof detail === "object") {
      lastBridgeDetail = detail;
    }

    const card = ensureWorkflowCard();
    const context = normalizeBridgeDetail(lastBridgeDetail || {});
    const productionConnectorApproved = false;
    const runtimeConnectorApproved = false;
    const externalHttpEnabled = false;
    const rawSecretVisible = false;

    const blockers = [
      "Confirm sandbox API documentation or integration reference.",
      "Confirm customer-side technical contact and review path.",
      "Confirm requested read/write scope boundaries.",
      "Confirm sandbox-before-production controls.",
    ];

    const actions = [
      "Review the requested operational profile.",
      "Ask the client for missing documents or security controls.",
      "Approve sandbox review only when readiness blockers are resolved.",
      "Keep production write approval separate from this request.",
    ];

    if (!context.hasProfile) {
      blockers.unshift(
        "No operational profile context is selected yet. Use the Integration API Keys bridge from a client request."
      );
    }

    setText(
      "admin-client-request-integration-readiness-status",
      context.hasProfile ? "Ready for supervisor review" : "Pending request context"
    );
    setText(
      "admin-client-request-integration-readiness-profile",
      context.displayName || "Not selected"
    );
    setText(
      "admin-client-request-integration-readiness-sandbox",
      context.hasProfile ? "Pending blocker review" : "Pending profile context"
    );
    setText(
      "admin-client-request-integration-readiness-production",
      String(productionConnectorApproved)
    );
    setText(
      "admin-client-request-integration-readiness-runtime",
      String(runtimeConnectorApproved)
    );
    setText(
      "admin-client-request-integration-readiness-safety",
      "Safety: no raw secrets, no customer credentials, no external HTTP calls, no runtime connector, and no production connector approval are enabled from this workflow."
    );

    replaceList("admin-client-request-integration-readiness-blockers", blockers);
    replaceList("admin-client-request-integration-readiness-actions", actions);

    card.dataset.state = context.hasProfile ? "profile-context" : "pending-context";
    card.dataset.productionConnectorApproved = String(productionConnectorApproved);
    card.dataset.runtimeConnectorApproved = String(runtimeConnectorApproved);
    card.dataset.externalHttpEnabled = String(externalHttpEnabled);
    card.dataset.rawSecretVisible = String(rawSecretVisible);

    return {
      marker: WORKFLOW_MARKER,
      hasProfile: context.hasProfile,
      requestedProfile: context.requestedProfile,
      productionConnectorApproved,
      runtimeConnectorApproved,
      externalHttpEnabled,
      rawSecretVisible,
    };
  }

  function generateSafeSupervisorDraft() {
    const context = normalizeBridgeDetail(lastBridgeDetail || {});
    const draft = supervisorDraftText(context);
    const output = getById("admin-client-request-integration-readiness-draft");

    if (output) {
      output.value = draft;
    }

    return draft;
  }

  function initSupervisorIntegrationReadinessWorkflow() {
    renderSupervisorIntegrationReadinessWorkflow();

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (
        target &&
        target.id === "admin-client-request-integration-readiness-draft-button"
      ) {
        generateSafeSupervisorDraft();
      }
    });

    window.addEventListener(WORKFLOW_EVENT, (event) => {
      renderSupervisorIntegrationReadinessWorkflow(event.detail || {});
    });
  }

  window.PMK_ADMIN_CLIENT_REQUEST_INTEGRATION_READINESS_WORKFLOW = {
    marker: WORKFLOW_MARKER,
    renderSupervisorIntegrationReadinessWorkflow,
    generateSafeSupervisorDraft,
    initSupervisorIntegrationReadinessWorkflow,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSupervisorIntegrationReadinessWorkflow);
  } else {
    initSupervisorIntegrationReadinessWorkflow();
  }
})();

/* ADMIN_INTEGRATION_READINESS_TRACKING_SUMMARY_11O_MARKER:
   admin-visible readiness tracking summary without fake client cases. */
(function () {
  "use strict";

  const TRACKING_MARKER = "admintracking11o-admintrackingroute11p-visiblehost";

  function getById(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    const element = getById(id);
    if (element) {
      element.textContent = value;
    }
  }

  /* ADMIN_INTEGRATION_READINESS_TRACKING_VISIBLE_HOST_11P_MARKER:
     force the tracking summary into a visible static admin host. */
  function trackingHost() {
    return getById("admin-integration-readiness-tracking-summary-host");
  }

  function trackingAnchor() {
    return (
      trackingHost() ||
      document.querySelector("main") ||
      document.body
    );
  }

  function ensureTrackingSummaryCard() {
    let card = getById("admin-integration-readiness-tracking-summary-card");
    if (card) {
      const host = trackingHost();
      if (host && card.parentNode !== host) {
        host.appendChild(card);
      }
      return card;
    }

    card = document.createElement("section");
    card.id = "admin-integration-readiness-tracking-summary-card";
    card.className = "admin-card settings-card";
    card.dataset.phase = "INTEGRATION-READINESS-11O";
    card.dataset.cacheMarker = TRACKING_MARKER;
    card.dataset.productionConnectorApproved = "false";
    card.dataset.runtimeConnectorApproved = "false";
    card.dataset.externalHttpEnabled = "false";
    card.dataset.rawSecretVisible = "false";
    card.setAttribute("aria-label", "Admin integration readiness tracking summary");

    card.innerHTML = `
      <div class="settings-card-header">
        <div>
          <p class="eyebrow">Readiness tracking</p>
          <h3>Integration Readiness Tracking Summary</h3>
        </div>
        <span
          id="admin-integration-readiness-tracking-state"
          class="status-pill"
        >Foundation ready</span>
      </div>

      <p class="muted">
        This supervisor summary distinguishes declarative readiness checks from
        client-specific tracking cases. It does not invent customer submissions.
      </p>

      <dl class="settings-summary-grid" aria-label="Integration readiness tracking counters">
        <div>
          <dt>Tracking foundation</dt>
          <dd id="admin-integration-readiness-tracking-foundation">available</dd>
        </div>
        <div>
          <dt>Persisted cases</dt>
          <dd id="admin-integration-readiness-tracking-cases">0</dd>
        </div>
        <div>
          <dt>Provided inputs</dt>
          <dd id="admin-integration-readiness-tracking-provided">0</dd>
        </div>
        <div>
          <dt>Verified items</dt>
          <dd id="admin-integration-readiness-tracking-verified">0</dd>
        </div>
        <div>
          <dt>Rejected items</dt>
          <dd id="admin-integration-readiness-tracking-rejected">0</dd>
        </div>
        <div>
          <dt>Timeline events</dt>
          <dd id="admin-integration-readiness-tracking-events">0</dd>
        </div>
      </dl>

      <table
        id="admin-integration-readiness-tracking-cases-table"
        class="admin-table"
        aria-label="Integration readiness tracking cases"
      >
        <thead>
          <tr>
            <th>Case</th>
            <th>Client</th>
            <th>Request</th>
            <th>Status</th>
            <th>Inputs</th>
            <th>Controls</th>
            <th>Sandbox</th>
          </tr>
        </thead>
        <tbody id="admin-integration-readiness-tracking-cases-body">
          <tr>
            <td colspan="7">
              No persisted readiness tracking cases yet. Use 11N tracking
              foundation first, then connect a safe admin route or storage layer
              in a later phase.
            </td>
          </tr>
        </tbody>
      </table>

      <p id="admin-integration-readiness-tracking-empty" class="muted">
        Empty state is intentional: current readiness checks are declarative.
        Client-specific tracking requires persisted cases or a safe admin
        tracking route.
      </p>

      <p id="admin-integration-readiness-tracking-safety" class="muted">
        Safety: no raw secrets, no customer credentials, no external HTTP calls,
        no runtime connector, and no production connector approval are enabled
        from this tracking summary.
      </p>
    `;

    const host = trackingHost();
    const anchor = trackingAnchor();

    if (host && host.appendChild) {
      host.innerHTML = "";
      host.appendChild(card);
    } else if (
      anchor &&
      anchor !== document.body &&
      anchor.parentNode &&
      anchor.parentNode.insertBefore
    ) {
      anchor.parentNode.insertBefore(card, anchor.nextSibling);
    } else if (anchor && anchor.appendChild) {
      anchor.appendChild(card);
    } else {
      document.body.appendChild(card);
    }

    return card;
  }

  function renderIntegrationReadinessTrackingSummary(summary) {
    const card = ensureTrackingSummaryCard();
    const safeSummary = summary && typeof summary === "object" ? summary : {};

    const persistedCases = Number(safeSummary.persistedCases || 0);
    const providedInputs = Number(safeSummary.providedInputs || 0);
    const verifiedItems = Number(safeSummary.verifiedItems || 0);
    const rejectedItems = Number(safeSummary.rejectedItems || 0);
    const timelineEvents = Number(safeSummary.timelineEvents || 0);

    setText("admin-integration-readiness-tracking-foundation", "available");
    setText("admin-integration-readiness-tracking-cases", String(persistedCases));
    setText("admin-integration-readiness-tracking-provided", String(providedInputs));
    setText("admin-integration-readiness-tracking-verified", String(verifiedItems));
    setText("admin-integration-readiness-tracking-rejected", String(rejectedItems));
    setText("admin-integration-readiness-tracking-events", String(timelineEvents));
    setText(
      "admin-integration-readiness-tracking-state",
      persistedCases > 0 ? "Tracking cases available" : "Foundation ready"
    );

    card.dataset.persistedCases = String(persistedCases);
    card.dataset.providedInputs = String(providedInputs);
    card.dataset.verifiedItems = String(verifiedItems);
    card.dataset.rejectedItems = String(rejectedItems);
    card.dataset.timelineEvents = String(timelineEvents);
    card.dataset.productionConnectorApproved = "false";
    card.dataset.runtimeConnectorApproved = "false";
    card.dataset.externalHttpEnabled = "false";
    card.dataset.rawSecretVisible = "false";

    return {
      marker: TRACKING_MARKER,
      persistedCases,
      providedInputs,
      verifiedItems,
      rejectedItems,
      timelineEvents,
      productionConnectorApproved: false,
      runtimeConnectorApproved: false,
      externalHttpEnabled: false,
      rawSecretVisible: false,
    };
  }

  /* ADMIN_INTEGRATION_READINESS_TRACKING_ROUTE_11P_MARKER:
     same-origin admin tracking route loader. */
  async function loadIntegrationReadinessTrackingSummary() {
    const fallback = {
      persistedCases: 0,
      providedInputs: 0,
      verifiedItems: 0,
      rejectedItems: 0,
      timelineEvents: 0,
    };

    try {
      const headers =
        window.PMK_ADMIN_AUTH && typeof window.PMK_ADMIN_AUTH.headers === "function"
          ? window.PMK_ADMIN_AUTH.headers()
          : {};

      const response = await fetch("/settings/admin/integration-readiness-tracking", {
        credentials: "same-origin",
        headers,
      });

      if (!response.ok) {
        renderIntegrationReadinessTrackingSummary(fallback);
        return {
          marker: TRACKING_MARKER,
          loaded: false,
          status: response.status,
          productionConnectorApproved: false,
          runtimeConnectorApproved: false,
          externalHttpEnabled: false,
          rawSecretVisible: false,
        };
      }

      const payload = await response.json();
      return renderIntegrationReadinessTrackingSummary({
        persistedCases: payload.persisted_cases || 0,
        providedInputs: payload.provided_inputs || 0,
        verifiedItems: payload.verified_items || 0,
        rejectedItems: payload.rejected_items || 0,
        timelineEvents: payload.timeline_events || 0,
      });
    } catch (error) {
      renderIntegrationReadinessTrackingSummary(fallback);
      return {
        marker: TRACKING_MARKER,
        loaded: false,
        error: String(error && error.message ? error.message : error),
        productionConnectorApproved: false,
        runtimeConnectorApproved: false,
        externalHttpEnabled: false,
        rawSecretVisible: false,
      };
    }
  }
  function initIntegrationReadinessTrackingSummary() {
    loadIntegrationReadinessTrackingSummary();
  }

  window.PMK_ADMIN_INTEGRATION_READINESS_TRACKING_SUMMARY = {
    marker: TRACKING_MARKER,
    renderIntegrationReadinessTrackingSummary,
    loadIntegrationReadinessTrackingSummary,
    initIntegrationReadinessTrackingSummary,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initIntegrationReadinessTrackingSummary);
  } else {
    initIntegrationReadinessTrackingSummary();
  }
})();

// BEGIN INTEGRATION_READINESS_12A_CASE_MANAGEMENT_UI

(function () {
  "use strict";

  const marker = "admincase12a";
  const listEndpoint = "/settings/admin/integration-readiness-tracking/cases";
  const detailEndpoint = "/settings/admin/integration-readiness-tracking/case-detail";
  const actionEndpoint = "/settings/admin/integration-readiness-tracking/case-item-action";

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function visibleText(value, fallback) {
    const text = String(value == null ? "" : value).trim();
    return text || fallback || "—";
  }

  function ensureCaseManagementHost() {
    let host = document.querySelector("#admin-integration-readiness-case-management-host");
    if (host) {
      return host;
    }

    host = document.createElement("section");
    host.id = "admin-integration-readiness-case-management-host";
    host.setAttribute("data-admin-integration-readiness-case-management", "12a");
    host.setAttribute("aria-label", "Integration readiness case management");
    host.className = "admin-card admin-integration-readiness-case-management";
    host.innerHTML = [
      "<h2>Integration readiness case management</h2>",
      "<p class=\"admin-muted\">Supervisor-safe case tracking for external integration readiness.</p>",
      "<div data-admin-integration-readiness-case-table data-admincase12a=\"case-table\">Loading integration readiness cases…</div>",
      "<div data-admin-integration-readiness-case-detail data-admincase12a=\"case-detail\">Select a readiness case to review required inputs, controls, and timeline.</div>",
    ].join("");

    const anchor = document.querySelector("#admin-integration-readiness-tracking-summary-host");
    if (anchor && anchor.parentElement) {
      anchor.parentElement.insertBefore(host, anchor.nextSibling);
    } else {
      document.body.appendChild(host);
    }
    return host;
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, Object.assign({ credentials: "same-origin" }, options || {}));
    let payload = null;
    try {
      payload = await response.json();
    } catch (_error) {
      payload = {};
    }
    if (!response.ok) {
      throw new Error(payload.detail || `Request failed: ${response.status}`);
    }
    return payload;
  }

  function renderEmptyDetail(host, message) {
    const detail = host.querySelector("[data-admin-integration-readiness-case-detail]");
    if (!detail) {
      return;
    }
    detail.innerHTML = [
      "<section class=\"admin-integration-readiness-case-detail-empty\" data-admin-integration-readiness-case-detail-empty>",
      `<p>${escapeHtml(message || "No readiness case selected.")}</p>`,
      "<button type=\"button\" disabled data-admin-integration-readiness-item-action-provided>Mark Provided</button>",
      "<button type=\"button\" disabled data-admin-integration-readiness-item-action-verified>Verify</button>",
      "<button type=\"button\" disabled data-admin-integration-readiness-item-action-rejected>Reject</button>",
      "<div data-admin-integration-readiness-case-timeline>No timeline events yet.</div>",
      "</section>",
    ].join("");
  }

  function renderCaseTable(host, cases) {
    const tableHost = host.querySelector("[data-admin-integration-readiness-case-table]");
    if (!tableHost) {
      return;
    }

    if (!cases.length) {
      tableHost.innerHTML = [
        "<div class=\"admin-empty\" data-admin-integration-readiness-case-table-empty>",
        "No persisted readiness cases yet.",
        "</div>",
      ].join("");
      renderEmptyDetail(host, "No readiness case selected yet.");
      return;
    }

    const rows = cases.map((item) => {
      const caseId = visibleText(item.case_id, "");
      return [
        "<tr>",
        `<td><button type="button" data-admin-integration-readiness-open-case data-case-id="${escapeHtml(caseId)}">${escapeHtml(caseId)}</button></td>`,
        `<td>${escapeHtml(visibleText(item.client_id))}</td>`,
        `<td>${escapeHtml(visibleText(item.adapter_id))}</td>`,
        `<td>${escapeHtml(String(item.provided_inputs || 0))}</td>`,
        `<td>${escapeHtml(String(item.verified_items || 0))}</td>`,
        `<td>${escapeHtml(String(item.rejected_items || 0))}</td>`,
        `<td>${escapeHtml(String(item.timeline_events || 0))}</td>`,
        "</tr>",
      ].join("");
    }).join("");

    tableHost.innerHTML = [
      `<table data-admincase12a="${marker}" class="admin-table admin-integration-readiness-case-table">`,
      "<thead><tr>",
      "<th>Case</th><th>Client</th><th>Adapter</th><th>Provided</th><th>Verified</th><th>Rejected</th><th>Timeline</th>",
      "</tr></thead>",
      `<tbody>${rows}</tbody>`,
      "</table>",
    ].join("");
  }

  function itemRows(caseId, title, items) {
    const rows = (items || []).map((item) => {
      const itemKey = visibleText(item.item_key, "");
      return [
        `<tr data-admin-integration-readiness-item-row data-case-id="${escapeHtml(caseId)}" data-item-key="${escapeHtml(itemKey)}">`,
        `<td>${escapeHtml(visibleText(item.label, itemKey))}</td>`,
        `<td>${escapeHtml(visibleText(item.status, "missing"))}</td>`,
        `<td><input type="text" data-admin-integration-readiness-safe-reference-input placeholder="safe reference only" value="${escapeHtml(item.safe_reference || "")}"></td>`,
        "<td>",
        `<button type="button" data-admin-integration-readiness-item-action-provided data-case-id="${escapeHtml(caseId)}" data-item-key="${escapeHtml(itemKey)}">Mark Provided</button> `,
        `<button type="button" data-admin-integration-readiness-item-action-verified data-case-id="${escapeHtml(caseId)}" data-item-key="${escapeHtml(itemKey)}">Verify</button> `,
        `<button type="button" data-admin-integration-readiness-item-action-rejected data-case-id="${escapeHtml(caseId)}" data-item-key="${escapeHtml(itemKey)}">Reject</button>`,
        "</td>",
        "</tr>",
      ].join("");
    }).join("");

    return [
      `<h4>${escapeHtml(title)}</h4>`,
      "<table class=\"admin-table admin-integration-readiness-items\">",
      "<thead><tr><th>Item</th><th>Status</th><th>Safe reference</th><th>Action</th></tr></thead>",
      `<tbody>${rows || "<tr><td colspan=\"4\">No items.</td></tr>"}</tbody>`,
      "</table>",
    ].join("");
  }

  function timelineRows(timeline) {
    const events = timeline || [];
    if (!events.length) {
      return "<div data-admin-integration-readiness-case-timeline>No timeline events yet.</div>";
    }

    const rows = events.map((event) => {
      return [
        "<li>",
        `<strong>${escapeHtml(visibleText(event.event, "event"))}</strong>`,
        ` — ${escapeHtml(visibleText(event.item_key))}`,
        ` — ${escapeHtml(visibleText(event.status))}`,
        ` — ${escapeHtml(visibleText(event.at))}`,
        "</li>",
      ].join("");
    }).join("");

    return `<ul data-admin-integration-readiness-case-timeline>${rows}</ul>`;
  }

  function renderCaseDetail(host, payload) {
    const detail = host.querySelector("[data-admin-integration-readiness-case-detail]");
    if (!detail) {
      return;
    }

    const casePayload = payload.case || payload;
    const caseId = visibleText(casePayload.case_id || payload.case_id, "");

    detail.innerHTML = [
      `<section class="admin-integration-readiness-case-detail" data-admincase12a="${marker}">`,
      `<h3>Readiness case: ${escapeHtml(caseId)}</h3>`,
      `<p><strong>Client:</strong> ${escapeHtml(visibleText(casePayload.client_id))}</p>`,
      `<p><strong>Request:</strong> ${escapeHtml(visibleText(casePayload.request_id))}</p>`,
      `<p><strong>Adapter:</strong> ${escapeHtml(visibleText(casePayload.adapter_id))}</p>`,
      itemRows(caseId, "Required inputs", casePayload.input_statuses || payload.input_statuses || []),
      itemRows(caseId, "Security controls", casePayload.security_control_statuses || payload.security_control_statuses || []),
      "<h4>Timeline</h4>",
      timelineRows(casePayload.timeline || payload.timeline || []),
      "</section>",
    ].join("");
  }

  async function openCase(host, caseId) {
    const payload = await fetchJson(`${detailEndpoint}?case_id=${encodeURIComponent(caseId)}`);
    renderCaseDetail(host, payload);
  }

  async function refreshSummaryCounters() {
    if (typeof window.loadIntegrationReadinessTrackingSummary === "function") {
      await window.loadIntegrationReadinessTrackingSummary();
    }
    window.dispatchEvent(new CustomEvent("pmk-integration-readiness-tracking-updated", {
      detail: { marker },
    }));
  }

  async function applyItemAction(host, button, status) {
    const row = button.closest("[data-admin-integration-readiness-item-row]");
    if (!row) {
      return;
    }

    const caseId = button.getAttribute("data-case-id") || row.getAttribute("data-case-id") || "";
    const itemKey = button.getAttribute("data-item-key") || row.getAttribute("data-item-key") || "";
    const referenceInput = row.querySelector("[data-admin-integration-readiness-safe-reference-input]");
    const safeReference = referenceInput ? referenceInput.value : "";

    button.disabled = true;
    try {
      const payload = await fetchJson(actionEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          case_id: caseId,
          item_key: itemKey,
          status,
          safe_reference: safeReference,
          note: "admin-ui-12a",
        }),
      });
      renderCaseDetail(host, payload);
      await refreshSummaryCounters();
      await loadIntegrationReadinessCaseManagement();
    } finally {
      button.disabled = false;
    }
  }

  async function loadIntegrationReadinessCaseManagement() {
    const host = ensureCaseManagementHost();
    host.setAttribute("data-admincase12a-loader", marker);

    try {
      const payload = await fetchJson(listEndpoint);
      const cases = Array.isArray(payload.cases) ? payload.cases : [];
      renderCaseTable(host, cases);
      if (cases.length) {
        await openCase(host, cases[0].case_id);
      } else {
        renderEmptyDetail(host, "No readiness case selected yet.");
      }
      host.dataset.state = "ready";
    } catch (error) {
      host.dataset.state = "error";
      renderEmptyDetail(host, error.message || "Unable to load integration readiness cases.");
    }
  }

  document.addEventListener("click", function (event) {
    const host = ensureCaseManagementHost();

    const openButton = event.target.closest("[data-admin-integration-readiness-open-case]");
    if (openButton) {
      event.preventDefault();
      openCase(host, openButton.getAttribute("data-case-id") || "");
      return;
    }

    const providedButton = event.target.closest("[data-admin-integration-readiness-item-action-provided]");
    if (providedButton && !providedButton.disabled) {
      event.preventDefault();
      applyItemAction(host, providedButton, "provided");
      return;
    }

    const verifiedButton = event.target.closest("[data-admin-integration-readiness-item-action-verified]");
    if (verifiedButton && !verifiedButton.disabled) {
      event.preventDefault();
      applyItemAction(host, verifiedButton, "verified");
      return;
    }

    const rejectedButton = event.target.closest("[data-admin-integration-readiness-item-action-rejected]");
    if (rejectedButton && !rejectedButton.disabled) {
      event.preventDefault();
      applyItemAction(host, rejectedButton, "rejected");
    }
  });

  window.PMK_INTEGRATION_READINESS_CASE_MANAGEMENT_12A = {
    marker,
    load: loadIntegrationReadinessCaseManagement,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadIntegrationReadinessCaseManagement);
  } else {
    loadIntegrationReadinessCaseManagement();
  }
})();
// END INTEGRATION_READINESS_12A_CASE_MANAGEMENT_UI

// BEGIN INTEGRATION_READINESS_12B_SUPERVISOR_SCOPE_HEADERS

(function () {
  "use strict";

  function supervisorHeaders12b() {
    const headers = {};
    const auth = window.PMK_ADMIN_AUTH || {};
    if (auth && typeof auth.headers === "function") {
      try {
        Object.assign(headers, auth.headers() || {});
      } catch (_error) {
        // Keep fallback headers below.
      }
    } else if (auth && auth.headers && typeof auth.headers === "object") {
      Object.assign(headers, auth.headers);
    }

    try {
      const sessionKey = window.sessionStorage.getItem("pmk_supervisor_session_key");
      if (sessionKey && !headers["X-Admin-Supervisor-Session"]) {
        headers["X-Admin-Supervisor-Session"] = sessionKey;
      }
    } catch (_error) {
      // sessionStorage can be unavailable in hardened browser contexts.
    }

    if (!headers["X-Admin-Supervisor-Scope"]) {
      headers["X-Admin-Supervisor-Scope"] = "admin:integration_readiness:review";
    }

    return headers;
  }

  window.PMK_INTEGRATION_READINESS_SUPERVISOR_SCOPE_12B = {
    marker: "admincase12b",
    headers: supervisorHeaders12b,
  };
})();
// END INTEGRATION_READINESS_12B_SUPERVISOR_SCOPE_HEADERS

// BEGIN INTEGRATION_READINESS_12C_OPERATOR_PACKAGE_UI

(function () {
  "use strict";

  const packageEndpoint = "/settings/admin/integration-readiness-operator-package";
  const exportEndpoint = "/settings/admin/integration-readiness-operator-package/export";

  function escapeHtml12c(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function boolText12c(value) {
    return String(value) === "true" ? "true" : "false";
  }

  function listRows12c(items, title, keyName) {
    const list = Array.isArray(items) ? items : [];
    if (!list.length) {
      return `<section><h3>${escapeHtml12c(title)}</h3><p>No items.</p></section>`;
    }

    const rows = list.map((item) => {
      const key = escapeHtml12c(item[keyName] || item.item_key || item.step_key || "");
      const label = escapeHtml12c(item.label || "");
      const status = escapeHtml12c(item.status || item.required_before || "");
      return `<li><strong>${key}</strong> - ${label} <span>${status}</span></li>`;
    });

    return `<section><h3>${escapeHtml12c(title)}</h3><ul>${rows.join("")}</ul></section>`;
  }

  function renderOperatorPackage12c(payload) {
    const body = document.querySelector("#admin-integration-readiness-operator-package-body");
    if (!body) {
      return;
    }

    const blockers = Array.isArray(payload.production_blockers)
      ? payload.production_blockers
      : [];

    body.innerHTML = [
      `<p><strong>Package:</strong> ${escapeHtml12c(payload.package_version)}</p>`,
      `<p><strong>Status:</strong> ${escapeHtml12c(payload.package_status)}</p>`,
      `<p><strong>Handoff:</strong> ${escapeHtml12c(payload.handoff_status)}</p>`,
      `<p><strong>Cases:</strong> <span data-admin-operator-package-case-count>${
        escapeHtml12c(payload.case_count || 0)
      }</span></p>`,
      `<p><strong>Pilot ready:</strong> <span data-admin-operator-package-pilot-ready>${
        boolText12c(payload.pilot_handoff_ready)
      }</span></p>`,
      listRows12c(payload.operator_required_inputs, "Operator required inputs", "item_key"),
      listRows12c(payload.pilot_handoff_steps, "Pilot handoff steps", "step_key"),
      listRows12c(blockers, "Production blockers", "blocker_key"),
      "<section><h3>Guardrails</h3>",
      `<p data-admin-operator-package-production-allowed>${
        boolText12c(payload.production_allowed)
      }</p>`,
      `<p data-admin-operator-package-runtime-approved>${
        boolText12c(payload.runtime_connector_approved)
      }</p>`,
      `<p data-admin-operator-package-external-http>${
        boolText12c(payload.external_http_enabled)
      }</p>`,
      `<p data-admin-operator-package-raw-secret>${boolText12c(payload.raw_secret_visible)}</p>`,
      "</section>",
      `<p><a href="${exportEndpoint}" data-admin-operator-package-export>Export Markdown</a></p>`,
    ].join("");
  }

  async function loadOperatorReadinessPackage12c() {
    const body = document.querySelector("#admin-integration-readiness-operator-package-body");
    if (!body) {
      return null;
    }

    try {
      const response = await fetch(packageEndpoint, {
        credentials: "same-origin",
      });
      const payload = await response.json();
      renderOperatorPackage12c(payload);
      body.dataset.state = "ready";
      return payload;
    } catch (error) {
      body.dataset.state = "error";
      body.textContent = "Operator readiness package unavailable.";
      return { error: String(error) };
    }
  }

  window.PMK_OPERATOR_READINESS_PACKAGE_12C = {
    marker: "adminpackage12c",
    endpoint: packageEndpoint,
    exportEndpoint,
    load: loadOperatorReadinessPackage12c,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadOperatorReadinessPackage12c);
  } else {
    loadOperatorReadinessPackage12c();
  }
})();
// END INTEGRATION_READINESS_12C_OPERATOR_PACKAGE_UI

// PMK INTEGRATION CLAIM KEYS 13A START
(() => {
  const marker = "adminclaim13a";
  const listEndpoint = "/settings/admin/integration-claim-keys";
  const issueEndpoint = "/settings/admin/integration-claim-keys";
  const revokeEndpoint = (claimKeyId) =>
    `/settings/admin/integration-claim-keys/${encodeURIComponent(claimKeyId)}/revoke`;

  const state = {
    lastPayload: null,
    lastIssued: null,
  };

  function mergeHeaders(extra) {
    const headers = { "Content-Type": "application/json" };

    try {
      const authHeaders = window.PMK_ADMIN_AUTH?.headers?.();
      if (authHeaders?.forEach) {
        authHeaders.forEach((value, key) => {
          headers[key] = value;
        });
      } else if (authHeaders && typeof authHeaders === "object") {
        Object.assign(headers, authHeaders);
      }
    } catch (_) {
      // keep local safe headers only
    }

    try {
      const session =
        window.localStorage?.getItem("pmk_admin_supervisor_session") ||
        window.sessionStorage?.getItem("pmk_admin_supervisor_session");
      if (session && !headers["X-Admin-Supervisor-Session"]) {
        headers["X-Admin-Supervisor-Session"] = session;
      }
      if (
        session &&
        !headers["X-Admin-Supervisor-Scope"] &&
        !headers["X-Admin-Supervisor-Scopes"]
      ) {
        headers["X-Admin-Supervisor-Scope"] = "admin:integration_readiness:write";
      }
    } catch (_) {
      // storage may be unavailable
    }

    return Object.assign(headers, extra || {});
  }

  async function requestJson(endpoint, options) {
    const response = await fetch(endpoint, {
      credentials: "include",
      ...options,
      headers: mergeHeaders(options?.headers),
    });
    const text = await response.text();
    let payload = {};
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch (_) {
        payload = { raw: text };
      }
    }
    if (!response.ok) {
      return {
        error: true,
        status: response.status,
        payload,
      };
    }
    return payload;
  }

  async function load() {
    const payload = await requestJson(listEndpoint);
    state.lastPayload = payload;
    render(payload);
    return payload;
  }

  async function issue(payload) {
    const result = await requestJson(issueEndpoint, {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
    state.lastIssued = result;
    await load();
    renderIssued(result);
    return result;
  }

  async function revoke(claimKeyId, reason) {
    const result = await requestJson(revokeEndpoint(claimKeyId), {
      method: "POST",
      body: JSON.stringify({ reason: reason || "Revoked by supervisor" }),
    });
    await load();
    return result;
  }

  function ensureHost() {
    let host = document.querySelector("#admin-integration-claim-keys-host");
    if (!host) {
      host = document.createElement("section");
      host.id = "admin-integration-claim-keys-host";
      host.className = "admin-card";
      host.setAttribute("aria-label", "Integration claim keys");
      host.innerHTML = `
        <h2>Integration Claim Keys</h2>
        <p>Supervisor-issued onboarding keys for operator integration officers.</p>
        <div id="admin-integration-claim-keys-body" data-state="idle"></div>
      `;
      const target =
        document.querySelector("main") ||
        document.querySelector("#admin-root") ||
        document.body;
      target.appendChild(host);
    }
    return host;
  }

  function guardrailHtml(guardrails) {
    const safe = guardrails || {};
    return `
      <dl data-admin-integration-claim-guardrails>
        <dt>runtime_enabled</dt>
        <dd data-admin-integration-claim-runtime-enabled>${String(safe.runtime_enabled)}</dd>
        <dt>production_allowed</dt>
        <dd data-admin-integration-claim-production-allowed>${String(safe.production_allowed)}</dd>
        <dt>external_http_enabled</dt>
        <dd data-admin-integration-claim-external-http>${String(safe.external_http_enabled)}</dd>
        <dt>secret_visibility</dt>
        <dd data-admin-integration-claim-raw-secret>${String(safe.raw_secret_visible)}</dd>
      </dl>
    `;
  }

  function renderIssued(result) {
    const output = document.querySelector("[data-admin-integration-claim-issued-once]");
    if (!output) return;

    if (result?.claim_key_once) {
      output.textContent = result.claim_key_once;
      output.dataset.visibleOnce = "true";
    } else if (result?.error) {
      output.textContent = `Issue failed: ${result.status || ""}`;
      output.dataset.visibleOnce = "false";
    } else {
      output.textContent = "No claim key issued yet.";
      output.dataset.visibleOnce = "false";
    }
  }

  function render(payload) {
    const host = ensureHost();
    const body =
      host.querySelector("#admin-integration-claim-keys-body") ||
      host.appendChild(document.createElement("div"));
    body.id = "admin-integration-claim-keys-body";
    body.dataset.state = payload?.error ? "error" : "ready";

    const claimKeys = Array.isArray(payload?.claim_keys) ? payload.claim_keys : [];

    body.innerHTML = `
      <div data-admin-integration-claim-marker="${marker}">
        <p>
          Version:
          <strong data-admin-integration-claim-version>${payload?.package_version || "integration-claim-keys-13a"}</strong>
        </p>

        <form data-admin-integration-claim-issue-form>
          <label>
            Client ID
            <input data-admin-integration-claim-client-id value="operator-demo-client" />
          </label>
          <label>
            Issued to
            <input data-admin-integration-claim-issued-to value="operator.integration@example.invalid" />
          </label>
          <label>
            Operator org
            <input data-admin-integration-claim-operator-org value="operator-demo-org" />
          </label>
          <label>
            Pilot terms note
            <textarea data-admin-integration-claim-terms>Sandbox onboarding only. No production connector approval.</textarea>
          </label>
          <button type="submit" data-admin-integration-claim-issue-button>
            Issue Integration Claim Key
          </button>
        </form>

        <section>
          <h3>Visible once</h3>
          <code data-admin-integration-claim-issued-once>No claim key issued yet.</code>
        </section>

        <p>
          Claim key count:
          <strong data-admin-integration-claim-count>${String(payload?.claim_key_count ?? claimKeys.length)}</strong>
        </p>

        ${guardrailHtml(payload?.guardrails)}

        <table data-admin-integration-claim-table>
          <thead>
            <tr>
              <th>Claim key</th>
              <th>Client</th>
              <th>Status</th>
              <th>Revoked</th>
              <th>Claimed</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${
              claimKeys.length
                ? claimKeys
                    .map(
                      (claim) => `
                        <tr data-admin-integration-claim-row="${claim.claim_key_id}">
                          <td>${claim.masked_claim_key || claim.claim_key_id}</td>
                          <td>${claim.client_id || ""}</td>
                          <td>${claim.status || ""}</td>
                          <td>${String(!!claim.revoked)}</td>
                          <td>${claim.claimed_at || ""}</td>
                          <td>
                            <button
                              type="button"
                              data-admin-integration-claim-revoke="${claim.claim_key_id}"
                              ${claim.revoked ? "disabled" : ""}
                            >
                              Revoke
                            </button>
                          </td>
                        </tr>
                      `,
                    )
                    .join("")
                : `<tr><td colspan="6">No integration claim keys yet.</td></tr>`
            }
          </tbody>
        </table>
      </div>
    `;

    const form = body.querySelector("[data-admin-integration-claim-issue-form]");
    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      await issue({
        client_id: body.querySelector("[data-admin-integration-claim-client-id]")?.value,
        issued_to: body.querySelector("[data-admin-integration-claim-issued-to]")?.value,
        operator_org_id: body.querySelector("[data-admin-integration-claim-operator-org]")?.value,
        pilot_terms_note: body.querySelector("[data-admin-integration-claim-terms]")?.value,
        one_time_use: true,
        allowed_domains: ["telecom"],
      });
    });

    body.querySelectorAll("[data-admin-integration-claim-revoke]").forEach((button) => {
      button.addEventListener("click", async () => {
        const claimKeyId = button.getAttribute("data-admin-integration-claim-revoke");
        if (!claimKeyId) return;
        await revoke(claimKeyId, "Revoked from Admin 13A panel");
      });
    });

    renderIssued(state.lastIssued);
  }

  window.PMK_ADMIN_INTEGRATION_CLAIM_KEYS_13A = {
    marker,
    listEndpoint,
    issueEndpoint,
    revokeEndpoint,
    load,
    issue,
    revoke,
    render,
    state,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      load().catch((error) => {
        render({ error: true, message: String(error), guardrails: {} });
      });
    });
  } else {
    load().catch((error) => {
      render({ error: true, message: String(error), guardrails: {} });
    });
  }
})();
// PMK INTEGRATION CLAIM KEYS 13A END
