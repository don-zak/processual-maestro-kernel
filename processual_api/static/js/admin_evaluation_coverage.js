(function () {
  const PLAN_ENDPOINT = '/settings/admin/evaluation-grants/coverage-plan';
  const STATUS_ENDPOINT = '/settings/admin/evaluation-grants/coverage-status';
  const PREVIEW_STAGE_ID = 'admin-api-key-evaluation-preview';
  const COVERAGE_HOST_ID = 'admin-evaluation-coverage';

  let coveragePlan = null;
  let refreshTimer = null;

  function text(value) { return String(value ?? '').trim(); }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function authorized() {
    return document.body.dataset.adminSession === 'ok' &&
      document.body.dataset.adminEvaluationGrants === 'authorized';
  }

  function authHeaders() {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') return auth.headers({ Accept: 'application/json' });
    return new Headers({ Accept: 'application/json' });
  }

  async function request(path) {
    const response = await fetch(path, {
      method: 'GET',
      credentials: 'include',
      headers: authHeaders(),
    });
    const raw = await response.text();
    let payload = {};
    if (raw) {
      try { payload = JSON.parse(raw); }
      catch { payload = { message: raw }; }
    }
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || `HTTP ${response.status}`);
    }
    return payload;
  }

  function campaignClientId() {
    return text(document.getElementById('admin-eval-client-id')?.value);
  }

  function ensureHost() {
    const preview = document.getElementById(PREVIEW_STAGE_ID);
    if (!preview) return null;
    let host = document.getElementById(COVERAGE_HOST_ID);
    if (host) return host;
    host = document.createElement('div');
    host.id = COVERAGE_HOST_ID;
    host.className = 'card flat';
    host.style.marginTop = 'var(--s-3)';
    host.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">Complete Endpoint Evaluation Coverage</div>
        <div class="sh-sub">declared plan vs runtime evidence across bounded evaluation keys</div>
      </div>
      <div data-eval-coverage-content class="admin-note">
        LOCKED — verify Super Administrator authority to load the complete evaluation campaign plan.
      </div>
    `;
    preview.appendChild(host);
    return host;
  }

  function renderPlanOnly(message = '') {
    const host = ensureHost();
    const target = host?.querySelector('[data-eval-coverage-content]');
    if (!target) return;
    const plan = coveragePlan || {};
    const campaigns = Array.isArray(plan.campaigns) ? plan.campaigns : [];
    const endpointCount = Number(plan.policy_endpoint_count || 0);
    const complete = plan.complete === true;
    target.className = complete ? 'admin-note ok' : 'admin-note';
    target.innerHTML = `
      <strong>Declared coverage:</strong> ${escapeHtml(endpointCount)}/${escapeHtml(endpointCount)} endpoint(s) · ${escapeHtml(campaigns.length)} bounded key group(s) · ${complete ? '100%' : 'incomplete'}<br>
      <span class="muted">Correlation: one unique campaign Client ID reused across the bounded grants. No single all-powerful key is required.</span>
      ${campaigns.map((campaign) => `<div class="admin-api-key-metadata-card-row" style="margin-top:var(--s-2)"><strong>${escapeHtml(campaign.operational_profile_id)}</strong><span>${escapeHtml(campaign.endpoint_count)} endpoint(s) · ${escapeHtml((campaign.required_scopes || []).join(', '))}</span></div>`).join('')}
      <div class="muted" style="margin-top:var(--s-2)">${escapeHtml(message || 'Enter the campaign Client ID to load measured runtime evidence.')}</div>
    `;
  }

  function renderStatus(status) {
    const host = ensureHost();
    const target = host?.querySelector('[data-eval-coverage-content]');
    if (!target) return;
    const endpoints = Array.isArray(status.endpoints) ? status.endpoints : [];
    const protectedRows = endpoints.filter((row) => row.proof_mode === 'evaluation_key_runtime');
    const publicRows = endpoints.filter((row) => row.proof_mode === 'public_availability_probe');
    const complete = status.protected_runtime_coverage_complete === true;
    target.className = complete ? 'admin-note ok' : 'admin-note';
    target.innerHTML = `
      <strong>Measured protected runtime coverage:</strong> ${escapeHtml(status.protected_endpoint_success_count || 0)}/${escapeHtml(status.protected_endpoint_count || 0)} · ${escapeHtml(status.protected_coverage_percent || 0)}%<br>
      <span class="muted">Campaign Client ID: ${escapeHtml(status.client_id || 'none')} · evidence is aggregated across bounded grants/keys without exposing raw secrets.</span>
      <div style="margin-top:var(--s-2)">
        ${protectedRows.map((row) => `<div class="admin-api-key-metadata-card-row"><strong>${escapeHtml(row.method)} ${escapeHtml(row.path)}</strong><span>${row.observed_success ? 'PASS' : 'PENDING'} · attempts ${escapeHtml(row.attempt_count)} · failures ${escapeHtml(row.failure_count)} · avg ${escapeHtml(row.avg_latency_ms)} ms</span></div>`).join('')}
      </div>
      <div class="admin-note" style="margin-top:var(--s-2)"><strong>Public availability probes:</strong> ${escapeHtml(publicRows.length)} remain separate from API-key proof. Validate /health/live and /health/ready externally; public reachability must not be misreported as key authorization evidence.</div>
      <div class="muted" style="margin-top:var(--s-2)">${complete ? 'All protected policy endpoints have successful runtime evidence. Full campaign still requires public probe evidence, task outcome quality, failure/retry checks, and cross-application repetition.' : 'Coverage is not complete. Missing protected endpoints must be exercised successfully with the bounded campaign keys.'}</div>
    `;
  }

  async function loadPlan() {
    if (!authorized()) return;
    coveragePlan = await request(PLAN_ENDPOINT);
    renderPlanOnly();
  }

  async function loadStatus() {
    if (!authorized()) return;
    const clientId = campaignClientId();
    if (!clientId) {
      renderPlanOnly('Enter the campaign Client ID to correlate evidence across the bounded grants/keys.');
      return;
    }
    try {
      const status = await request(`${STATUS_ENDPOINT}?client_id=${encodeURIComponent(clientId)}`);
      renderStatus(status);
    } catch (error) {
      renderPlanOnly(`Unable to load measured coverage: ${error.message || error}`);
    }
  }

  function scheduleStatusRefresh() {
    window.clearTimeout(refreshTimer);
    refreshTimer = window.setTimeout(loadStatus, 180);
  }

  async function hydrate() {
    ensureHost();
    if (!authorized()) return;
    try {
      await loadPlan();
      await loadStatus();
    } catch (error) {
      renderPlanOnly(`Unable to load coverage plan: ${error.message || error}`);
    }
    const clientIdInput = document.getElementById('admin-eval-client-id');
    clientIdInput?.addEventListener('input', scheduleStatusRefresh);
    clientIdInput?.addEventListener('change', scheduleStatusRefresh);
  }

  ensureHost();
  window.addEventListener('pmk-admin-session-verified', hydrate);
  window.addEventListener('pmk-evaluation-grant-updated', loadStatus);
  window.addEventListener('pmk-api-key-access-selection-changed', scheduleStatusRefresh);
  window.PMK_ADMIN_EVALUATION_COVERAGE = {
    hydrate,
    refresh: loadStatus,
  };
  hydrate();
})();
