(function () {
  const HOST_ID = 'admin-program-supervision-readiness';
  const TITLE = 'Program & Supervision Readiness';

  const CHECKS = [
    {
      group: 'program readiness',
      label: 'Application health',
      path: '/health',
      auth: false,
    },
    {
      group: 'program readiness',
      label: 'Application readiness',
      path: '/ready',
      auth: false,
      optional: true,
    },
    {
      group: 'supervision readiness',
      label: 'Admin session identity',
      path: '/auth/me',
      auth: true,
    },
    {
      group: 'supervision readiness',
      label: 'Client request inbox',
      path: '/settings/admin/client-requests',
      auth: true,
    },
    {
      group: 'supervision readiness',
      label: 'Recent supervisor audit',
      path: '/settings/admin/audit-events?limit=3',
      auth: true,
    },
    {
      group: 'supervision readiness',
      label: 'API key lifecycle',
      path: '/settings/api-keys',
      auth: true,
    },
  ];

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function authHeaders(extra = {}) {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') {
      return auth.headers(extra);
    }

    return new Headers(extra);
  }

  function ensureReadinessHost() {
    const existing = document.getElementById(HOST_ID);
    if (existing) return existing;

    const overviewHost = document.getElementById('admin-supervisor-overview-counters');
    const homeConsole = document.getElementById('admin-supervisor-home-console');
    const parent = overviewHost?.parentNode || homeConsole?.parentNode;
    if (!parent) return null;

    const host = document.createElement('div');
    host.id = HOST_ID;
    host.className = 'card';
    host.style.marginTop = 'var(--s-5)';
    host.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">${escapeHtml(TITLE)}</div>
        <div class="sh-sub">program runtime and supervision readiness - visibility-only</div>
      </div>
      <div class="mono-block" style="font-size:11px;white-space:pre-wrap">
        Loading program and supervision readiness...
      </div>
    `;

    if (overviewHost) {
      parent.insertBefore(host, overviewHost);
    } else {
      parent.appendChild(host);
    }

    return host;
  }

  async function checkEndpoint(check) {
    const startedAt = performance.now();

    try {
      const response = await fetch(check.path, {
        method: 'GET',
        credentials: 'include',
        cache: 'no-store',
        headers: check.auth
          ? authHeaders({ Accept: 'application/json' })
          : { Accept: 'application/json' },
      });

      const elapsedMs = Math.max(0, Math.round(performance.now() - startedAt));
      return {
        ...check,
        ok: response.ok,
        status: response.status,
        elapsedMs,
      };
    } catch (error) {
      return {
        ...check,
        ok: false,
        status: 'network_error',
        message: error.message || String(error),
        elapsedMs: Math.max(0, Math.round(performance.now() - startedAt)),
      };
    }
  }

  function statusLabel(result) {
    if (result.ok) return 'ready';
    if (result.optional && result.status === 404) return 'not configured';
    return 'needs attention';
  }

  function summarize(results, group) {
    const items = results.filter((result) => result.group === group);
    const ready = items.filter((result) => result.ok).length;
    const optionalUnavailable = items.filter(
      (result) => result.optional && result.status === 404
    ).length;

    return `${ready}/${items.length} ready${
      optionalUnavailable ? `, ${optionalUnavailable} optional unavailable` : ''
    }`;
  }

  function renderReadiness(results) {
    const host = ensureReadinessHost();
    if (!host) return;

    const rows = results
      .map((result) => {
        const label = statusLabel(result);
        const detail = result.message
          ? `${result.status} | ${result.message}`
          : `${result.status} | ${result.elapsedMs}ms`;

        return `
          <div class="admin-note">
            <strong>${escapeHtml(result.label)}: ${escapeHtml(label)}</strong>
            <div class="muted">${escapeHtml(result.group)} | ${escapeHtml(
          result.path
        )} | ${escapeHtml(detail)}</div>
          </div>
        `;
      })
      .join('');

    host.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">${escapeHtml(TITLE)}</div>
        <div class="sh-sub">program runtime and supervision readiness - visibility-only</div>
      </div>
      <div class="admin-note">
        <strong>Program:</strong> ${escapeHtml(summarize(results, 'program readiness'))}
        <br>
        <strong>Supervision:</strong> ${escapeHtml(
          summarize(results, 'supervision readiness')
        )}
      </div>
      ${rows}
      <div class="muted" style="margin-top:var(--s-3)">
        Backend enforcement remains authoritative. This card only reports readiness signals.
      </div>
    `;
  }

  function renderError(error) {
    const host = ensureReadinessHost();
    if (!host) return;

    host.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">${escapeHtml(TITLE)}</div>
        <div class="sh-sub">program runtime and supervision readiness - visibility-only</div>
      </div>
      <div class="admin-note danger">Unable to load readiness summary: ${escapeHtml(
        error.message || error
      )}</div>
      <div class="muted">Backend enforcement remains authoritative.</div>
    `;
  }

  async function refreshReadinessSummary() {
    ensureReadinessHost();

    try {
      const results = await Promise.all(CHECKS.map((check) => checkEndpoint(check)));
      renderReadiness(results);
    } catch (error) {
      renderError(error);
    }
  }

  let readinessTimer = null;

  function scheduleReadinessRefresh() {
    if (readinessTimer) {
      window.clearTimeout(readinessTimer);
    }

    readinessTimer = window.setTimeout(() => {
      readinessTimer = null;
      refreshReadinessSummary();
    }, 0);
  }

  function installReadinessRefreshHooks() {
    window.addEventListener('load', () => {
      scheduleReadinessRefresh();
    });

    window.addEventListener('pmk-supervisor-session-key-updated', () => {
      scheduleReadinessRefresh();
    });

    if (typeof MutationObserver === 'function') {
      const main = document.getElementById('main') || document.body;
      const observer = new MutationObserver(() => {
        if (!document.getElementById(HOST_ID)) {
          scheduleReadinessRefresh();
        }
      });

      observer.observe(main, { childList: true, subtree: true });
    }
  }

  installReadinessRefreshHooks();
  scheduleReadinessRefresh();
  setTimeout(() => scheduleReadinessRefresh(), 250);
  setTimeout(() => scheduleReadinessRefresh(), 1000);
})();