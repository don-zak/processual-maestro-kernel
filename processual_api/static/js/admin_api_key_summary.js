document.addEventListener('DOMContentLoaded', () => {
  const API_KEYS_ENDPOINT = '/settings/api-keys';
  const SUPERVISOR_KEYS_ENDPOINT = '/settings/admin/supervisor-session-keys';
  const HOST_ID = 'admin-api-key-lifecycle-summary';

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

  function extractList(payload, keys) {
    if (Array.isArray(payload)) return payload;
    if (!payload || typeof payload !== 'object') return [];

    for (const key of keys) {
      if (Array.isArray(payload[key])) return payload[key];
    }

    if (payload.data && Array.isArray(payload.data)) return payload.data;

    for (const key of keys) {
      if (payload.data && Array.isArray(payload.data[key])) {
        return payload.data[key];
      }
    }

    return [];
  }

  function isRevoked(item) {
    const status = text(item.status || item.lifecycle_status).toLowerCase();
    return Boolean(item.revoked || item.revoked_at || status === 'revoked');
  }

  function isExpired(item) {
    const status = text(item.status || item.lifecycle_status).toLowerCase();
    if (item.expired || status === 'expired') return true;

    const expiresAt = text(item.expires_at || item.expiry || item.expires);
    if (!expiresAt) return false;

    const parsed = Date.parse(expiresAt);
    return Number.isFinite(parsed) && parsed < Date.now();
  }

  function summarizeKeys(items) {
    const summary = {
      total: 0,
      active: 0,
      revoked: 0,
      expired: 0,
    };

    items.forEach((item) => {
      summary.total += 1;

      if (isRevoked(item)) {
        summary.revoked += 1;
      } else if (isExpired(item)) {
        summary.expired += 1;
      } else {
        summary.active += 1;
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

    const page = document.getElementById('page-admin-api-keys');
    if (!page) return null;

    const card = document.createElement('div');
    card.className = 'card';
    card.id = HOST_ID;
    card.style.marginTop = 'var(--s-5)';
    card.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">API Key Lifecycle Summary</div>
        <div class="sh-sub">standard API keys and supervisor session keys - visibility only</div>
      </div>
      <div class="mono-block" style="font-size:11px;white-space:pre-wrap">Loading API key lifecycle summary...</div>
    `;

    const target = page.firstElementChild || page;
    target.appendChild(card);
    return card;
  }

  function renderSummary(apiSummary, supervisorSummary) {
    const host = ensureHost();
    if (!host) return;

    host.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">API Key Lifecycle Summary</div>
        <div class="sh-sub">standard API keys and supervisor session keys - visibility only</div>
      </div>
      <div class="grid-3">
        ${statTile('standard API keys total', apiSummary.total)}
        ${statTile('standard active', apiSummary.active)}
        ${statTile('standard revoked', apiSummary.revoked)}
        ${statTile('standard expired', apiSummary.expired)}
        ${statTile('supervisor session keys total', supervisorSummary.total)}
        ${statTile('supervisor active', supervisorSummary.active)}
        ${statTile('supervisor revoked', supervisorSummary.revoked)}
        ${statTile('supervisor expired', supervisorSummary.expired)}
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
        <div class="sh-title">API Key Lifecycle Summary</div>
        <div class="sh-sub">standard API keys and supervisor session keys - visibility only</div>
      </div>
      <div class="admin-note danger">Unable to load API key lifecycle summary: ${escapeHtml(
        error.message || error
      )}</div>
      <div class="muted">Backend enforcement remains authoritative.</div>
    `;
  }

  async function refreshApiKeyLifecycleSummary() {
    const host = ensureHost();
    if (!host) return;

    try {
      const apiPayload = await requestJson(API_KEYS_ENDPOINT);
      const supervisorPayload = await requestJson(SUPERVISOR_KEYS_ENDPOINT);

      const apiKeys = extractList(apiPayload, ['api_keys', 'keys', 'items', 'results']);
      const supervisorKeys = extractList(supervisorPayload, [
        'supervisor_session_keys',
        'keys',
        'items',
        'results',
      ]);

      renderSummary(summarizeKeys(apiKeys), summarizeKeys(supervisorKeys));
    } catch (error) {
      renderError(error);
    }
  }

  refreshApiKeyLifecycleSummary();

  window.addEventListener('pmk-supervisor-session-key-updated', () => {
    refreshApiKeyLifecycleSummary();
  });
});