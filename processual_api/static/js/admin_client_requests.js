(function () {
  const ENDPOINT = '/settings/admin/client-requests';
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

    return {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
    ].join('');

    host.appendChild(card);
    return card;
  }

  function renderCounts(counts) {
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
    renderList(data?.latest_requests || []);
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

  window.PMK_ADMIN_CLIENT_REQUESTS = {
    bindAdminClientRequests,
    loadAdminClientRequests,
    renderAdminClientRequests,
    refreshAdminClientRequestsSoon,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
