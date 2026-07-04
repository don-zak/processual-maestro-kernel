(function () {
  const ENDPOINT = '/settings/admin/client-requests';
  const PAGE_ID = 'page-admin-clients';
  const CARD_ID = 'admin-client-requests-card';

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

  function ensureCard() {
    const page = byId(PAGE_ID);
    if (!page) return null;

    let card = byId(CARD_ID);
    if (card) return card;

    card = document.createElement('div');
    card.id = CARD_ID;
    card.className = 'card';

    card.innerHTML = [
      '<div class="sec-hdr">',
      '<div>',
      '<div class="sh-title">Client Requests Inbox</div>',
      '<div class="sh-sub">Read-only supervisor view of client request summaries</div>',
      '</div>',
      '<button id="admin-client-requests-refresh-btn" class="btn sm" type="button">Refresh Requests</button>',
      '</div>',
      '<div id="admin-client-requests-status" class="mono-block" style="font-size:11px;white-space:pre-wrap">Client request inbox not loaded yet.</div>',
      '<div id="admin-client-requests-counts" class="mono-block" style="margin-top:var(--s-3);font-size:11px;white-space:pre-wrap"></div>',
      '<div id="admin-client-requests-list" style="margin-top:var(--s-3)"></div>',
    ].join('');

    const firstCard = page.querySelector('.card');
    if (firstCard && firstCard.parentNode) {
      firstCard.parentNode.insertBefore(card, firstCard);
    } else {
      page.appendChild(card);
    }

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

  function renderList(requests) {
    const target = byId('admin-client-requests-list');
    clear(target);
    if (!target) return;

    if (!Array.isArray(requests) || requests.length === 0) {
      appendText(target, 'div', 'No client requests found.', 'admin-note');
      return;
    }

    const wrap = document.createElement('div');
    wrap.className = 'table-wrap';

    const table = document.createElement('table');
    table.className = 'admin-table';

    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    FIELDS.forEach((field) => appendText(headerRow, 'th', field));
    appendText(headerRow, 'th', 'action');
    thead.appendChild(headerRow);

    const tbody = document.createElement('tbody');
    requests.forEach((item) => {
      const row = document.createElement('tr');
      FIELDS.forEach((field) => appendText(row, 'td', item?.[field] ?? ''));

      const actionCell = document.createElement('td');
      const button = document.createElement('button');
      button.className = 'btn secondary sm admin-client-request-select';
      button.type = 'button';
      button.dataset.requestId = text(item?.request_id || '');
      button.textContent = 'Select';
      actionCell.appendChild(button);
      row.appendChild(actionCell);

      tbody.appendChild(row);
    });

    table.appendChild(thead);
    table.appendChild(tbody);
    wrap.appendChild(table);
    target.appendChild(wrap);
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

  async function loadAdminClientRequests() {
    ensureCard();

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
        loadAdminClientRequests();
      });
    }
  }

  function init() {
    bindAdminClientRequests();
    loadAdminClientRequests();
  }

  window.PMK_ADMIN_CLIENT_REQUESTS = {
    bindAdminClientRequests,
    loadAdminClientRequests,
    renderAdminClientRequests,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();