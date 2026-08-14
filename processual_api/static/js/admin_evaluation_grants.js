(function () {
  const EVALUATION_GRANTS_ENDPOINT = '/settings/admin/evaluation-grants';
  const EVALUATION_TASK_CATALOG_ENDPOINT =
    '/settings/admin/evaluation-grants/task-catalog';
  const GRANT_HOST_ID = 'admin-evaluation-grants';
  const EXTERNAL_CATEGORY = 'external_evaluation';
  let evaluationTaskCatalog = [];

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

  function dispatchEvaluationSelectionChanged() {
    try {
      window.dispatchEvent(new CustomEvent('pmk-evaluation-selection-changed'));
    } catch {
      window.dispatchEvent(new Event('pmk-evaluation-selection-changed'));
    }
  }

  function authHeaders(extra = {}) {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') {
      return auth.headers(extra);
    }
    return new Headers(extra);
  }

  async function request(path, method = 'GET', payload) {
    const headers = authHeaders({ Accept: 'application/json' });
    if (payload !== undefined && headers && typeof headers.set === 'function') {
      headers.set('Content-Type', 'application/json');
    } else if (payload !== undefined && headers && typeof headers === 'object') {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(path, {
      method,
      credentials: 'include',
      headers,
      ...(payload !== undefined ? { body: JSON.stringify(payload) } : {}),
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
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function ensureGrantHost() {
    let host = document.getElementById(GRANT_HOST_ID);
    if (host) return host;
    const body = document.getElementById('admin-api-key-external-evaluation-body');
    if (!body) return null;
    host = document.createElement('div');
    host.id = GRANT_HOST_ID;
    host.className = 'card flat';
    host.dataset.evaluationGrantPlaceholder = 'true';
    body.appendChild(host);
    return host;
  }

  function grantForm() {
    return `
      <div class="sec-hdr">
        <div class="sh-title">Evaluation Grant Preparation</div>
        <div class="sh-sub">identity, limits, canonical tasks, grant creation, one-time issue, and revoke</div>
      </div>
      <div class="admin-note">
        Evaluation grants are temporary, quota-bound, non-production entitlements. Administrative scopes are rejected by the backend. Complete every readiness gate before grant creation is enabled.
      </div>
      <div class="grid-3">
        <label>Client ID<input id="admin-eval-client-id" type="text" placeholder="evaluation-client"></label>
        <label>Issued to<input id="admin-eval-issued-to" type="text" placeholder="Company or evaluator"></label>
        <label>Duration days<input id="admin-eval-days" type="number" min="1" max="90" value="14"></label>
        <label>Max requests<input id="admin-eval-max-requests" type="number" min="1" max="10000" value="100"></label>
        <label style="grid-column:span 2">Purpose<input id="admin-eval-purpose" type="text" value="Governed external product evaluation"></label>
      </div>
      <div style="margin-top:var(--s-3)">
        <strong>API key task content</strong>
        <div class="muted">Choose only the canonical tasks this evaluation key may represent.</div>
        <div id="admin-eval-task-list" style="margin-top:var(--s-2)">Loading canonical tasks...</div>
      </div>
      <div id="admin-eval-readiness" class="admin-note" style="margin-top:var(--s-3)">
        Evaluation grant creation is locked until the lifecycle readiness contract is complete.
      </div>
      <div style="margin-top:var(--s-3)">
        <button id="admin-eval-create" class="btn primary" type="button" disabled>Create Evaluation Grant</button>
        <button id="admin-eval-refresh" class="btn secondary" type="button">Refresh Grants</button>
      </div>
      <div id="admin-eval-result" class="admin-note" style="margin-top:var(--s-3)"></div>
      <div id="admin-eval-list" style="margin-top:var(--s-3)">Loading evaluation grants...</div>
    `;
  }

  function renderEvaluationTaskCatalog() {
    const target = document.getElementById('admin-eval-task-list');
    if (!target) return;
    if (!evaluationTaskCatalog.length) {
      target.innerHTML =
        '<div class="admin-note danger">Canonical task catalog is unavailable. Grant creation is disabled.</div>';
      updateEvaluationReadiness();
      return;
    }
    const groups = new Map();
    evaluationTaskCatalog.forEach((task) => {
      const domain = text(task.adapter_contract_id) || 'other';
      if (!groups.has(domain)) groups.set(domain, []);
      groups.get(domain).push(task);
    });
    target.innerHTML = [...groups.entries()]
      .map(([domain, tasks]) => `
        <fieldset class="card flat" style="margin-top:var(--s-2)">
          <legend><strong>${escapeHtml(domain.replaceAll('_', ' '))}</strong></legend>
          ${tasks
            .map((task) => `
              <label style="display:block;margin-top:var(--s-2)">
                <input type="checkbox" data-eval-task value="${escapeHtml(task.task_id)}">
                <code>${escapeHtml(task.task_id)}</code> — ${escapeHtml(task.safe_operation)}
                <span class="muted"> · ${escapeHtml(task.operation_class)} · ${(task.required_scope_ids || []).map(escapeHtml).join(', ')}</span>
              </label>
            `)
            .join('')}
        </fieldset>
      `)
      .join('');
    target.querySelectorAll('[data-eval-task]').forEach((input) => {
      input.addEventListener('change', dispatchEvaluationSelectionChanged);
    });
    dispatchEvaluationSelectionChanged();
    updateEvaluationReadiness();
  }

  async function loadEvaluationTaskCatalog() {
    const payload = await request(EVALUATION_TASK_CATALOG_ENDPOINT, 'GET');
    evaluationTaskCatalog = Array.isArray(payload.tasks) ? payload.tasks : [];
    renderEvaluationTaskCatalog();
  }

  function selectedEvaluationTasks() {
    return [...document.querySelectorAll('[data-eval-task]:checked')]
      .map((input) => text(input.value))
      .filter(Boolean);
  }

  function selectedEvaluationScopes() {
    const workspace = window.PMK_ADMIN_API_KEY_PROVISIONING_WORKSPACE;
    if (!workspace || typeof workspace.selectedScopes !== 'function') return [];
    const values = workspace.selectedScopes();
    return Array.isArray(values)
      ? [...new Set(values.map((scope) => text(scope)).filter(Boolean))]
      : [];
  }

  function selectedEvaluationEndpoints() {
    const workspace = window.PMK_ADMIN_API_KEY_PROVISIONING_WORKSPACE;
    if (!workspace || typeof workspace.selectedEndpoints !== 'function') return [];
    const values = workspace.selectedEndpoints();
    return Array.isArray(values) ? values : [];
  }

  function evaluationReadiness() {
    const category = text(document.getElementById('admin-api-key-category')?.value);
    const profile = text(document.getElementById('admin-api-key-operational-profile')?.value);
    const clientId = text(document.getElementById('admin-eval-client-id')?.value);
    const issuedTo = text(document.getElementById('admin-eval-issued-to')?.value);
    const purpose = text(document.getElementById('admin-eval-purpose')?.value);
    const duration = Number.parseInt(document.getElementById('admin-eval-days')?.value || '0', 10);
    const quota = Number.parseInt(document.getElementById('admin-eval-max-requests')?.value || '0', 10);
    const tasks = selectedEvaluationTasks();
    const scopes = selectedEvaluationScopes();
    const endpoints = selectedEvaluationEndpoints();
    const grantAuthority = document.body.dataset.adminEvaluationGrants;

    const checks = [
      ['category', category === EXTERNAL_CATEGORY, 'Select External Evaluation Access in Category.'],
      ['administrator', document.body.dataset.adminSession === 'ok', 'Verify an administrator credential.'],
      ['grant_authority', grantAuthority === 'authorized' || grantAuthority === 'loaded', 'Evaluation grant authority must be authorized.'],
      ['operational_profile', Boolean(profile), 'Select an operational profile.'],
      ['eligible_endpoint', endpoints.length > 0, 'Select at least one eligible API endpoint.'],
      ['derived_scope', scopes.length > 0, 'Selected endpoints must derive at least one runtime scope.'],
      ['canonical_task', tasks.length > 0, 'Select at least one canonical task.'],
      ['client_id', Boolean(clientId), 'Client ID is required.'],
      ['issued_to', Boolean(issuedTo), 'Issued to is required.'],
      ['purpose', purpose.length >= 10, 'Purpose must contain at least 10 characters.'],
      ['duration', Number.isInteger(duration) && duration >= 1 && duration <= 90, 'Duration must be between 1 and 90 days.'],
      ['quota', Number.isInteger(quota) && quota >= 1 && quota <= 10000, 'Max requests must be between 1 and 10000.'],
    ];
    const missing = checks.filter(([, ok]) => !ok).map(([id, , message]) => ({ id, message }));
    return {
      ready: missing.length === 0,
      missing,
      category,
      profile,
      clientId,
      issuedTo,
      purpose,
      duration,
      quota,
      tasks,
      scopes,
      endpoints,
    };
  }

  function updateEvaluationReadiness() {
    const readiness = evaluationReadiness();
    const button = document.getElementById('admin-eval-create');
    const target = document.getElementById('admin-eval-readiness');
    if (button) {
      button.disabled = !readiness.ready;
      button.dataset.lifecycleReady = readiness.ready ? 'true' : 'false';
    }
    if (target) {
      target.className = readiness.ready ? 'admin-note ok' : 'admin-note';
      target.innerHTML = readiness.ready
        ? '<strong>READY.</strong> All planned lifecycle gates are complete. Create Evaluation Grant is enabled; backend validation remains authoritative.'
        : `<strong>LOCKED.</strong> Complete the remaining gates:<br>${readiness.missing
            .map((item) => `• ${escapeHtml(item.message)}`)
            .join('<br>')}`;
    }
    window.PMK_ADMIN_EXTERNAL_EVALUATION_CATEGORY_FLOW?.renderContract?.();
    return readiness;
  }

  function grantRow(grant) {
    const active = text(grant.status).toLowerCase() === 'active';
    const tasks = Array.isArray(grant.allowed_task_ids) ? grant.allowed_task_ids : [];
    const scopes = Array.isArray(grant.allowed_scopes) ? grant.allowed_scopes : [];
    const actions = active
      ? `<button class="btn secondary" data-eval-issue="${escapeHtml(grant.grant_id)}" type="button">Issue API Key</button>
         <button class="btn danger" data-eval-revoke="${escapeHtml(grant.grant_id)}" type="button">Revoke</button>`
      : '';
    return `
      <div class="card flat" style="margin-top:var(--s-2)">
        <div><strong>${escapeHtml(grant.issued_to || grant.client_id)}</strong> · ${escapeHtml(grant.status)}</div>
        <div class="muted">${escapeHtml(grant.grant_id)} · client ${escapeHtml(grant.client_id)} · quota ${escapeHtml(grant.max_requests)} · keys ${escapeHtml(grant.active_key_count || 0)}</div>
        <div class="muted">scopes: ${scopes.length ? scopes.map(escapeHtml).join(', ') : 'backend defaults'}</div>
        <div class="muted">tasks: ${tasks.length ? tasks.map(escapeHtml).join(', ') : 'none'} · authority ${escapeHtml(grant.task_authority_source || 'integration_task_catalog')}</div>
        <div class="muted">expires ${escapeHtml(grant.expires_at)} · subscription required: no · production: disabled</div>
        <div style="margin-top:var(--s-2)">${actions}</div>
      </div>
    `;
  }

  function setGrantResult(message, danger = false) {
    const target = document.getElementById('admin-eval-result');
    if (!target) return;
    target.className = danger ? 'admin-note danger' : 'admin-note ok';
    target.innerHTML = message;
  }

  async function refreshEvaluationGrants() {
    const list = document.getElementById('admin-eval-list');
    if (!list) return;
    try {
      const payload = await request(EVALUATION_GRANTS_ENDPOINT, 'GET');
      const grants = Array.isArray(payload.grants) ? payload.grants : [];
      list.innerHTML = grants.length
        ? grants.map(grantRow).join('')
        : '<div class="muted">No evaluation grants have been issued.</div>';
      bindGrantActions();
    } catch (error) {
      list.innerHTML = `<div class="admin-note danger">Unable to load evaluation grants: ${escapeHtml(error.message || error)}</div>`;
    }
  }

  async function createEvaluationGrant() {
    const readiness = updateEvaluationReadiness();
    if (!readiness.ready) {
      setGrantResult(
        'Evaluation grant creation blocked by the lifecycle readiness contract. Complete every LOCKED gate before retrying.',
        true
      );
      return;
    }

    const allowedScopes = readiness.scopes;

    try {
      const result = await request(EVALUATION_GRANTS_ENDPOINT, 'POST', {
        client_id: readiness.clientId,
        user_id: readiness.clientId,
        issued_to: readiness.issuedTo,
        purpose: readiness.purpose,
        allowed_task_ids: readiness.tasks,
        ...(allowedScopes.length ? { allowed_scopes: allowedScopes } : {}),
        expires_in_days: readiness.duration,
        max_requests: readiness.quota,
      });
      const grant = result.grant || {};
      setGrantResult(
        `Evaluation grant created: <strong>${escapeHtml(grant.grant_id || '')}</strong><br>` +
        `Tasks: ${(grant.allowed_task_ids || []).map(escapeHtml).join(', ')}<br>` +
        `Scopes: ${(grant.allowed_scopes || []).map(escapeHtml).join(', ') || 'backend defaults'}<br>` +
        `Quota: ${escapeHtml(grant.max_requests)} · expires ${escapeHtml(grant.expires_at)} · production disabled`
      );
      await refreshEvaluationGrants();
      dispatchEvaluationSelectionChanged();
    } catch (error) {
      setGrantResult(
        `Unable to create grant: ${escapeHtml(error.message || error)}`,
        true
      );
    }
  }

  async function issueEvaluationKey(grantId) {
    try {
      const result = await request(
        `${EVALUATION_GRANTS_ENDPOINT}/${encodeURIComponent(grantId)}/issue-key`,
        'POST',
        { label: 'External evaluation access' }
      );
      const secret = text(result.api_key);
      const key = result.key || {};
      const tasks = Array.isArray(key.allowed_task_ids) ? key.allowed_task_ids : [];
      const scopes = Array.isArray(key.scopes) ? key.scopes : [];
      const taskScopes = Array.isArray(key.task_scope_ids) ? key.task_scope_ids : [];
      const usage = result.onboarding_usage || {};
      const header = text(usage.header) || 'X-API-Key';
      const exampleEndpoint = text(usage.example_endpoint) || '/adapters/status';
      setGrantResult(`
        <strong>One-time evaluation API key created.</strong><br>
        Copy it now; it will not be displayed again.<br>
        <span class="mono-block" style="display:block;margin-top:var(--s-2)">X-API-Key: ${escapeHtml(secret)}</span>
        ${header !== 'X-API-Key' ? `<div class="muted">Backend header: ${escapeHtml(header)}</div>` : ''}
        <button id="admin-eval-copy-issued-key" class="btn secondary" type="button" style="margin-top:var(--s-2)">Copy API Key</button><br>
        <strong>Grant</strong>: ${escapeHtml(grantId)}<br>
        <strong>Client</strong>: ${escapeHtml(key.client_id || '')}<br>
        <strong>Scopes</strong>: ${escapeHtml(scopes.join(', ') || 'none')}<br>
        <strong>Task scope IDs</strong>: ${escapeHtml(taskScopes.join(', ') || 'none')}<br>
        <strong>Bound tasks:</strong> ${escapeHtml(tasks.join(', ') || 'none')}<br>
        <strong>Quota</strong>: ${escapeHtml(key.quota_limit)}<br>
        <strong>Expires</strong>: ${escapeHtml(key.expires_at)}<br>
        <strong>Example endpoint</strong>: ${escapeHtml(exampleEndpoint)}<br>
        <strong>Subscription required</strong>: no · <strong>Production</strong>: disabled
      `);
      document.getElementById('admin-eval-copy-issued-key')?.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(secret);
        } catch {
          // Clipboard may be unavailable in restricted browser contexts.
        }
      });
      await refreshEvaluationGrants();
      window.dispatchEvent(new CustomEvent('pmk-evaluation-grant-updated'));
    } catch (error) {
      setGrantResult(
        `Unable to issue evaluation key: ${escapeHtml(error.message || error)}`,
        true
      );
    }
  }

  async function revokeEvaluationGrant(grantId) {
    try {
      const result = await request(
        `${EVALUATION_GRANTS_ENDPOINT}/${encodeURIComponent(grantId)}`,
        'DELETE'
      );
      setGrantResult(
        `Grant revoked. ${escapeHtml(result.revoked_key_count || 0)} linked key(s) revoked.`
      );
      await refreshEvaluationGrants();
      window.dispatchEvent(new CustomEvent('pmk-evaluation-grant-updated'));
    } catch (error) {
      setGrantResult(
        `Unable to revoke evaluation grant: ${escapeHtml(error.message || error)}`,
        true
      );
    }
  }

  function bindGrantActions() {
    document.querySelectorAll('[data-eval-issue]').forEach((button) => {
      button.addEventListener('click', () =>
        issueEvaluationKey(button.dataset.evalIssue)
      );
    });
    document.querySelectorAll('[data-eval-revoke]').forEach((button) => {
      button.addEventListener('click', () =>
        revokeEvaluationGrant(button.dataset.evalRevoke)
      );
    });
  }

  async function initializeEvaluationGrants() {
    const host = ensureGrantHost();
    if (!host) return;
    host.innerHTML = grantForm();
    host.addEventListener('input', dispatchEvaluationSelectionChanged);
    host.addEventListener('change', dispatchEvaluationSelectionChanged);
    host.addEventListener('input', updateEvaluationReadiness);
    host.addEventListener('change', updateEvaluationReadiness);
    document
      .getElementById('admin-eval-create')
      ?.addEventListener('click', createEvaluationGrant);
    document
      .getElementById('admin-eval-refresh')
      ?.addEventListener('click', refreshEvaluationGrants);

    window.addEventListener('pmk-admin-session-verified', updateEvaluationReadiness);
    window.addEventListener('pmk-api-key-category-changed', updateEvaluationReadiness);
    window.addEventListener('pmk-api-key-access-selection-changed', updateEvaluationReadiness);
    window.addEventListener('pmk-evaluation-selection-changed', updateEvaluationReadiness);

    try {
      await loadEvaluationTaskCatalog();
    } catch (error) {
      evaluationTaskCatalog = [];
      renderEvaluationTaskCatalog();
      setGrantResult(
        `Unable to load canonical task catalog: ${escapeHtml(error.message || error)}`,
        true
      );
    }
    refreshEvaluationGrants();
    dispatchEvaluationSelectionChanged();
    updateEvaluationReadiness();
  }

  window.PMK_ADMIN_EVALUATION_GRANTS = {
    readiness: evaluationReadiness,
    updateReadiness: updateEvaluationReadiness,
  };

  initializeEvaluationGrants();
})();