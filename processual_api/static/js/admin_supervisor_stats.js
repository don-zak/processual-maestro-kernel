(function () {
  const ENDPOINT = '/settings/admin/client-requests';
  const HOST_ID = 'admin-supervisor-overview-counters';
  const STATUS_KEYS = ['pending', 'reviewed', 'approved', 'rejected', 'completed'];

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function text(value) {
    return String(value ?? '').trim();
  }

  function normalizeStatus(value) {
    const normalized = text(value).toLowerCase().replace(/[\s-]+/g, '_');
    return STATUS_KEYS.includes(normalized) ? normalized : 'pending';
  }

  function authHeaders(extra = {}) {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') {
      return auth.headers(extra);
    }

    return new Headers(extra);
  }

  async function requestJson(path) {
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

  function extractRequests(payload) {
    if (Array.isArray(payload)) return payload;
    if (!payload || typeof payload !== 'object') return [];

    const candidateKeys = ['client_requests', 'requests', 'items', 'results'];
    for (const key of candidateKeys) {
      if (Array.isArray(payload[key])) return payload[key];
    }

    if (payload.data && Array.isArray(payload.data)) return payload.data;
    if (payload.data && Array.isArray(payload.data.client_requests)) {
      return payload.data.client_requests;
    }

    return [];
  }

  function requestStatus(item) {
    return normalizeStatus(
      item.status ||
        item.request_status ||
        item.state ||
        item.lifecycle_status ||
        item.current_status
    );
  }

  function hasDraftSaved(item) {
    return Boolean(
      item.supervisor_response_draft ||
        item.supervisor_draft ||
        item.draft_saved ||
        item.supervisor_response_draft_saved ||
        item.response_draft_saved
    );
  }

  function hasResponseSent(item) {
    return Boolean(
      item.supervisor_response_sent ||
        item.response_sent ||
        item.supervisor_sent_at ||
        item.response_sent_at
    );
  }

  function summarizeRequests(items) {
    const summary = {
      total: 0,
      pending: 0,
      reviewed: 0,
      approved: 0,
      rejected: 0,
      completed: 0,
      draftSaved: 0,
      responseSent: 0,
    };

    items.forEach((item) => {
      summary.total += 1;
      summary[requestStatus(item)] += 1;

      if (hasDraftSaved(item)) {
        summary.draftSaved += 1;
      }

      if (hasResponseSent(item)) {
        summary.responseSent += 1;
      }
    });

    return summary;
  }

  function statTile(label, value) {
    return `
      <div class="card flat">
        <div class="muted" style="font-size:10px">${escapeHtml(label)}</div>
        <div class="font-data" style="font-size:18px">${escapeHtml(value)}</div>
      </div>
    `;
  }

  function ensureHost() {
    let host = document.getElementById(HOST_ID);
    if (host) return host;

    const page = document.getElementById('page-admin-home') || document.getElementById('page-admin-clients');
    if (!page) return null;

    const card = document.createElement('div');
    card.className = 'card';
    card.id = HOST_ID;
    card.style.marginTop = 'var(--s-5)';
    card.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">Supervisor Overview</div>
        <div class="sh-sub">requests by status - visibility only</div>
      </div>
      <div class="mono-block" style="font-size:11px;white-space:pre-wrap">Loading supervisor overview...</div>
    `;

    const section = page.querySelector('section') || page.firstElementChild || page;
    section.appendChild(card);
    return card;
  }

  function renderSummary(summary) {
    const host = ensureHost();
    if (!host) return;

    host.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">Supervisor Overview</div>
        <div class="sh-sub">requests by status - visibility only</div>
      </div>
      <div class="grid-3">
        ${statTile('Total requests', summary.total)}
        ${statTile('Pending requests', summary.pending)}
        ${statTile('Reviewed requests', summary.reviewed)}
        ${statTile('Approved requests', summary.approved)}
        ${statTile('Rejected requests', summary.rejected)}
        ${statTile('Completed requests', summary.completed)}
        ${statTile('draft saved', summary.draftSaved)}
        ${statTile('response sent', summary.responseSent)}
      </div>
      <div class="muted" style="margin-top:var(--s-3)">
        Backend enforcement remains authoritative. Do not display raw supervisor session keys.
      </div>
    `;
  }

  function renderError(error) {
    const host = ensureHost();
    if (!host) return;

    host.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">Supervisor Overview</div>
        <div class="sh-sub">requests by status - visibility only</div>
      </div>
      <div class="admin-note danger">Unable to load supervisor overview: ${escapeHtml(
        error.message || error
      )}</div>
      <div class="muted">Backend enforcement remains authoritative.</div>
    `;
  }

  async function refreshSupervisorOverviewCounters() {
    const host = ensureHost();
    if (!host) return;

    try {
      const payload = await requestJson(ENDPOINT);
      const requests = extractRequests(payload);
      renderSummary(summarizeRequests(requests));
    } catch (error) {
      renderError(error);
    }
  }

  refreshSupervisorOverviewCounters();

  window.addEventListener('pmk-supervisor-session-key-updated', () => {
    refreshSupervisorOverviewCounters();
  });

})();
