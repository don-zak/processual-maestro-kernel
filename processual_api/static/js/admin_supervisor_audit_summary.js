(function () {
  const ENDPOINT = '/settings/admin/audit-events?limit=12';
  const HOST_ID = 'admin-supervisor-audit-summary';

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

  function ensureHost() {
    return document.getElementById(HOST_ID);
  }

  function eventLabel(event) {
    const action = text(event.action) || 'audit_event';
    const result = text(event.result) || 'unknown';
    const actorLevel = text(event.actor_level) || 'supervisor';
    return `${action} | ${result} | ${actorLevel}`;
  }

  function eventMeta(event) {
    const at = text(event.at || event.created_at);
    const targetType = text(event.target_type);
    const targetId = text(event.target_id);
    const reason = text(event.reason || event.safe_note);

    return [at, targetType, targetId, reason].filter(Boolean).join(' | ');
  }

  function renderEvents(events) {
    const host = ensureHost();
    if (!host) return;

    const rows = events.length
      ? events
          .map(
            (event) => `
              <div class="admin-note">
                <strong>${escapeHtml(eventLabel(event))}</strong>
                <div class="muted">${escapeHtml(eventMeta(event))}</div>
              </div>
            `
          )
          .join('')
      : '<div class="admin-note">No supervisor audit events found yet.</div>';

    host.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">Recent Supervisor Audit</div>
        <div class="sh-sub">latest admin/supervisor audit events - visibility only</div>
      </div>
      ${rows}
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
        <div class="sh-title">Recent Supervisor Audit</div>
        <div class="sh-sub">latest admin/supervisor audit events - visibility only</div>
      </div>
      <div class="admin-note danger">Unable to load recent supervisor audit: ${escapeHtml(
        error.message || error
      )}</div>
      <div class="muted">Backend enforcement remains authoritative.</div>
    `;
  }

  async function refreshSupervisorAuditSummary() {
    const host = ensureHost();
    if (!host) return;

    try {
      const payload = await requestJson(ENDPOINT);
      const events = Array.isArray(payload.audit_events) ? payload.audit_events : [];
      renderEvents(events);
    } catch (error) {
      renderError(error);
    }
  }

  refreshSupervisorAuditSummary();

  window.addEventListener('load', () => {
    refreshSupervisorAuditSummary();
  });

  window.addEventListener('pmk-supervisor-session-key-updated', () => {
    refreshSupervisorAuditSummary();
  });
})();