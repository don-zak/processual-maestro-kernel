(function () {
  const EVALUATION_GRANTS_ENDPOINT = '/settings/admin/evaluation-grants';
  const EVALUATION_TASK_CATALOG_ENDPOINT = '/settings/admin/evaluation-grants/task-catalog';
  const TASK_IDENTITY_STAGE_ID = 'admin-api-key-evaluation-task-identity-stage';
  const PREVIEW_STAGE_ID = 'admin-api-key-evaluation-preview';
  const GRANT_HOST_ID = 'admin-evaluation-grants';
  const TEST_REVOKE_STAGE_ID = 'admin-api-key-evaluation-test-revoke-stage';
  const EXTERNAL_CATEGORY = 'external_evaluation';

  let evaluationTaskCatalog = [];
  let hydrated = false;
  let hydrationPromise = null;
  let oneTimeIssuedKey = '';

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function text(value) { return String(value ?? '').trim(); }

  function authorized() {
    return document.body.dataset.adminSession === 'ok' &&
      document.body.dataset.adminEvaluationGrants === 'authorized';
  }

  function authHeaders(extra = {}) {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') return auth.headers(extra);
    return new Headers(extra);
  }

  async function request(path, method = 'GET', payload) {
    const headers = authHeaders({ Accept: 'application/json' });
    if (payload !== undefined && headers && typeof headers.set === 'function') headers.set('Content-Type', 'application/json');
    const response = await fetch(path, {
      method,
      credentials: 'include',
      headers,
      ...(payload !== undefined ? { body: JSON.stringify(payload) } : {}),
    });
    const raw = await response.text();
    let data = {};
    if (raw) { try { data = JSON.parse(raw); } catch { data = { message: raw }; } }
    if (!response.ok) {
      const detail = data.detail || data.message || `HTTP ${response.status}`;
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function dispatchSelectionChanged() {
    try { window.dispatchEvent(new CustomEvent('pmk-evaluation-selection-changed')); }
    catch { window.dispatchEvent(new Event('pmk-evaluation-selection-changed')); }
  }

  function taskIdentityStage() { return document.getElementById(TASK_IDENTITY_STAGE_ID); }
  function previewStage() { return document.getElementById(PREVIEW_STAGE_ID); }
  function grantHost() { return document.getElementById(GRANT_HOST_ID); }

  function renderLockedShell() {
    const taskStage = taskIdentityStage();
    const preview = previewStage();
    const grant = grantHost();
    const testStage = document.getElementById(TEST_REVOKE_STAGE_ID);
    if (!taskStage || !preview || !grant) return false;

    taskStage.innerHTML = `
      <div class="sec-hdr"><div class="sh-title">Canonical Tasks</div><div class="sh-sub">backend task catalog; visible now, selectable after administrator verification</div></div>
      <div id="admin-eval-task-list" class="admin-note">LOCKED — canonical task choices will load after administrator verification.</div>
      <div class="sec-hdr" style="margin-top:var(--s-3)"><div class="sh-title">Evaluation Identity</div><div class="sh-sub">Client ID · Issued To · Purpose</div></div>
      <div class="grid-3">
        <label>Client ID<input id="admin-eval-client-id" type="text" placeholder="evaluation-client" disabled></label>
        <label>Issued to<input id="admin-eval-issued-to" type="text" placeholder="Supervisor, tester, or prospective customer" disabled></label>
        <label>Purpose<input id="admin-eval-purpose" type="text" value="Governed real-runtime product evaluation" disabled></label>
      </div>
      <div class="sec-hdr" style="margin-top:var(--s-3)"><div class="sh-title">Duration / Quota</div><div class="sh-sub">temporary bounded evaluation runtime</div></div>
      <div class="grid-3">
        <label>Duration days<input id="admin-eval-days" type="number" min="1" max="90" value="14" disabled></label>
        <label>Max requests<input id="admin-eval-max-requests" type="number" min="1" max="10000" value="100" disabled></label>
        <div class="card flat"><strong>Execution mode</strong><div>evaluation_runtime</div></div>
      </div>
      <div class="admin-note" style="margin-top:var(--s-2)">Real runtime execution is allowed only through explicitly selected endpoints, derived scopes, canonical tasks, quota, and expiry. Commercial production entitlement and control-plane access remain disabled.</div>
    `;

    preview.innerHTML = `
      <div class="sec-hdr"><div class="sh-title">Access Preview · Readiness</div><div class="sh-sub">fail-closed lifecycle contract</div></div>
      <div id="admin-eval-effective-preview" class="admin-api-key-metadata-card-grid"></div>
      <div id="admin-eval-readiness" class="admin-note" style="margin-top:var(--s-3)"><strong>LOCKED.</strong> Verify administrator authority before privileged catalogs and grant controls are enabled.</div>
    `;

    grant.innerHTML = `
      <div class="admin-note">Evaluation grants are temporary, quota-bound runtime credentials. Only the Super Administrator can create, issue, or revoke them; administrative scopes and control-plane access remain rejected.</div>
      <div class="admin-actions" style="margin-top:var(--s-3)">
        <button id="admin-eval-create" class="btn primary" type="button" disabled>Create Evaluation Grant</button>
        <button id="admin-eval-refresh" class="btn secondary" type="button" disabled>Refresh Grants</button>
      </div>
      <div id="admin-eval-result" class="admin-note" style="margin-top:var(--s-3)"></div>
      <div id="admin-eval-list" style="margin-top:var(--s-3)"><div class="muted">LOCKED — grant list loads after administrator verification and grant authority.</div></div>
    `;

    if (testStage) {
      testStage.innerHTML = `
        <div class="sec-hdr"><div class="sh-title">Allowed / Denied Endpoint Test · Revoke</div><div class="sh-sub">least-privilege proof after one-time issue</div></div>
        <div id="admin-eval-endpoint-test" class="admin-note">LOCKED — issue an evaluation API key first. The raw key is kept in memory only for this page session and is never persisted.</div>
      `;
    }

    taskStage.addEventListener('input', updateEvaluationReadiness);
    taskStage.addEventListener('change', updateEvaluationReadiness);
    document.getElementById('admin-eval-create')?.addEventListener('click', createEvaluationGrant);
    document.getElementById('admin-eval-refresh')?.addEventListener('click', refreshEvaluationGrants);
    renderEffectivePreview();
    updateEvaluationReadiness();
    return true;
  }

  function selectedEvaluationTasks() {
    return [...document.querySelectorAll('[data-eval-task]:checked')].map((input) => text(input.value)).filter(Boolean);
  }

  function selectedEvaluationScopes() {
    const workspace = window.PMK_ADMIN_API_KEY_PROVISIONING_WORKSPACE;
    if (!workspace || typeof workspace.selectedScopes !== 'function') return [];
    const values = workspace.selectedScopes();
    return Array.isArray(values) ? [...new Set(values.map(text).filter(Boolean))] : [];
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
    const checks = [
      ['category', category === EXTERNAL_CATEGORY, 'Select External Evaluation Access in Category.'],
      ['administrator', document.body.dataset.adminSession === 'ok', 'Verify an administrator credential.'],
      ['grant_authority', document.body.dataset.adminEvaluationGrants === 'authorized', 'Evaluation grant authority must be authorized.'],
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
    return { ready: checks.every(([, ok]) => ok), missing: checks.filter(([, ok]) => !ok).map(([id, , message]) => ({ id, message })), category, profile, clientId, issuedTo, purpose, duration, quota, tasks, scopes, endpoints };
  }

  function renderEffectivePreview() {
    const target = document.getElementById('admin-eval-effective-preview');
    if (!target) return;
    const readiness = evaluationReadiness();
    target.innerHTML = `
      <div class="admin-api-key-metadata-card-row"><strong>category</strong><span>${escapeHtml(readiness.category || 'none')}</span></div>
      <div class="admin-api-key-metadata-card-row"><strong>profile</strong><span>${escapeHtml(readiness.profile || 'none')}</span></div>
      <div class="admin-api-key-metadata-card-row"><strong>execution mode</strong><span>evaluation_runtime</span></div>
      <div class="admin-api-key-metadata-card-row"><strong>real runtime</strong><span>allowed within grant</span></div>
      <div class="admin-api-key-metadata-card-row"><strong>endpoints</strong><span>${readiness.endpoints.length}</span></div>
      <div class="admin-api-key-metadata-card-row"><strong>derived scopes</strong><span>${readiness.scopes.length}</span></div>
      <div class="admin-api-key-metadata-card-row"><strong>canonical tasks</strong><span>${readiness.tasks.length}</span></div>
      <div class="admin-api-key-metadata-card-row"><strong>duration / quota</strong><span>${readiness.duration || 0} days / ${readiness.quota || 0}</span></div>
      <div class="admin-api-key-metadata-card-row"><strong>commercial production</strong><span>disabled</span></div>
    `;
  }

  function updateEvaluationReadiness() {
    const readiness = evaluationReadiness();
    const button = document.getElementById('admin-eval-create');
    const target = document.getElementById('admin-eval-readiness');
    if (button) { button.disabled = !readiness.ready; button.dataset.lifecycleReady = readiness.ready ? 'true' : 'false'; }
    if (target) {
      target.className = readiness.ready ? 'admin-note ok' : 'admin-note';
      target.innerHTML = readiness.ready
        ? '<strong>READY.</strong> Every lifecycle gate is complete. Create Evaluation Grant is enabled; backend validation remains authoritative.'
        : `<strong>LOCKED.</strong> Complete the remaining gates:<br>${readiness.missing.map((item) => `• ${escapeHtml(item.message)}`).join('<br>')}`;
    }
    renderEffectivePreview();
    return readiness;
  }

  function renderEvaluationTaskCatalog() {
    const target = document.getElementById('admin-eval-task-list');
    if (!target) return;
    if (!evaluationTaskCatalog.length) {
      target.innerHTML = '<div class="admin-note danger">Canonical task catalog is unavailable. Grant creation remains disabled.</div>';
      updateEvaluationReadiness();
      return;
    }
    const groups = new Map();
    evaluationTaskCatalog.forEach((task) => {
      const domain = text(task.adapter_contract_id) || 'other';
      if (!groups.has(domain)) groups.set(domain, []);
      groups.get(domain).push(task);
    });
    target.innerHTML = [...groups.entries()].map(([domain, tasks]) => `
      <fieldset class="card flat" style="margin-top:var(--s-2)"><legend><strong>${escapeHtml(domain.replaceAll('_', ' '))}</strong></legend>
        ${tasks.map((task) => `<label style="display:block;margin-top:var(--s-2)"><input type="checkbox" data-eval-task value="${escapeHtml(task.task_id)}"> <code>${escapeHtml(task.task_id)}</code> — ${escapeHtml(task.safe_operation)} <span class="muted"> · ${escapeHtml(task.operation_class)} · ${(task.required_scope_ids || []).map(escapeHtml).join(', ')}</span></label>`).join('')}
      </fieldset>`).join('');
    target.querySelectorAll('[data-eval-task]').forEach((input) => input.addEventListener('change', dispatchSelectionChanged));
    updateEvaluationReadiness();
  }

  async function loadEvaluationTaskCatalog() {
    const payload = await request(EVALUATION_TASK_CATALOG_ENDPOINT, 'GET');
    evaluationTaskCatalog = Array.isArray(payload.tasks) ? payload.tasks : [];
    renderEvaluationTaskCatalog();
  }

  function grantRow(grant) {
    const active = text(grant.status).toLowerCase() === 'active';
    const tasks = Array.isArray(grant.allowed_task_ids) ? grant.allowed_task_ids : [];
    const scopes = Array.isArray(grant.allowed_scopes) ? grant.allowed_scopes : [];
    const endpoints = Array.isArray(grant.allowed_endpoints) ? grant.allowed_endpoints : [];
    return `<div class="card flat" style="margin-top:var(--s-2)">
      <div><strong>${escapeHtml(grant.issued_to || grant.client_id)}</strong> · ${escapeHtml(grant.status)}</div>
      <div class="muted">${escapeHtml(grant.grant_id)} · evaluation_runtime · quota ${escapeHtml(grant.max_requests)} · expires ${escapeHtml(grant.expires_at)}</div>
      <div class="muted">endpoints: ${escapeHtml(endpoints.map((item) => `${item.method} ${item.path}`).join(', ') || 'none')}</div>
      <div class="muted">scopes: ${escapeHtml(scopes.join(', ') || 'none')}</div>
      <div class="muted">tasks: ${escapeHtml(tasks.join(', ') || 'none')} · commercial production disabled</div>
      ${active ? `<div class="admin-actions" style="margin-top:var(--s-2)"><button class="btn secondary" data-eval-issue="${escapeHtml(grant.grant_id)}" type="button">Issue API Key</button><button class="btn danger" data-eval-revoke="${escapeHtml(grant.grant_id)}" type="button">Revoke</button></div>` : ''}
    </div>`;
  }

  function setGrantResult(message, danger = false) {
    const target = document.getElementById('admin-eval-result');
    if (!target) return;
    target.className = danger ? 'admin-note danger' : 'admin-note ok';
    target.innerHTML = message;
  }

  function bindGrantActions() {
    document.querySelectorAll('[data-eval-issue]').forEach((button) => button.addEventListener('click', () => issueEvaluationKey(button.dataset.evalIssue)));
    document.querySelectorAll('[data-eval-revoke]').forEach((button) => button.addEventListener('click', () => revokeEvaluationGrant(button.dataset.evalRevoke)));
  }

  async function refreshEvaluationGrants() {
    const list = document.getElementById('admin-eval-list');
    if (!list || !authorized()) return;
    try {
      const payload = await request(EVALUATION_GRANTS_ENDPOINT, 'GET');
      const grants = Array.isArray(payload.grants) ? payload.grants : [];
      list.innerHTML = grants.length ? grants.map(grantRow).join('') : '<div class="muted">No evaluation grants have been issued.</div>';
      bindGrantActions();
    } catch (error) { list.innerHTML = `<div class="admin-note danger">Unable to load evaluation grants: ${escapeHtml(error.message || error)}</div>`; }
  }

  async function createEvaluationGrant() {
    const readiness = updateEvaluationReadiness();
    if (!readiness.ready) { setGrantResult('Evaluation grant creation blocked by the lifecycle readiness contract.', true); return; }
    try {
      const result = await request(EVALUATION_GRANTS_ENDPOINT, 'POST', {
        client_id: readiness.clientId,
        user_id: readiness.clientId,
        issued_to: readiness.issuedTo,
        purpose: readiness.purpose,
        allowed_task_ids: readiness.tasks,
        allowed_endpoints: readiness.endpoints.map((endpoint) => ({ method: endpoint.method, path: endpoint.path })),
        allowed_scopes: readiness.scopes,
        expires_in_days: readiness.duration,
        max_requests: readiness.quota,
      });
      const grant = result.grant || {};
      setGrantResult(`Evaluation grant created: <strong>${escapeHtml(grant.grant_id || '')}</strong> · evaluation_runtime · ${escapeHtml((grant.allowed_endpoints || []).length)} endpoint(s) · quota ${escapeHtml(grant.max_requests)}`);
      await refreshEvaluationGrants();
      window.dispatchEvent(new CustomEvent('pmk-evaluation-grant-updated'));
    } catch (error) { setGrantResult(`Unable to create grant: ${escapeHtml(error.message || error)}`, true); }
  }

  function renderEndpointTestHint() {
    const target = document.getElementById('admin-eval-endpoint-test');
    if (!target) return;
    target.className = oneTimeIssuedKey ? 'admin-note ok' : 'admin-note';
    target.innerHTML = oneTimeIssuedKey
      ? '<strong>One-time key is available in page memory.</strong> Configure it in the external application, prove a selected endpoint succeeds, prove an unselected runtime endpoint and the control plane are denied, then revoke and confirm the same key stops working.'
      : 'LOCKED — issue an evaluation API key first. The raw key is never persisted.';
  }

  async function issueEvaluationKey(grantId) {
    if (!authorized()) return;
    try {
      const result = await request(`${EVALUATION_GRANTS_ENDPOINT}/${encodeURIComponent(grantId)}/issue-key`, 'POST', { label: 'External evaluation access' });
      const secret = text(result.api_key);
      oneTimeIssuedKey = secret;
      const key = result.key || {};
      setGrantResult(`<strong>One-time evaluation API key created.</strong> Copy it now; it will not be displayed again after this result changes.<br><span class="mono-block" style="display:block;margin-top:var(--s-2)">X-API-Key: ${escapeHtml(secret)}</span><button id="admin-eval-copy-issued-key" class="btn secondary" type="button" style="margin-top:var(--s-2)">Copy API Key</button><br><span class="muted">evaluation_runtime · client ${escapeHtml(key.client_id || '')} · endpoints ${escapeHtml((key.allowed_endpoints || []).length)} · quota ${escapeHtml(key.quota_limit)} · expires ${escapeHtml(key.expires_at)} · commercial production disabled</span>`);
      document.getElementById('admin-eval-copy-issued-key')?.addEventListener('click', async () => { try { await navigator.clipboard.writeText(secret); } catch {} });
      renderEndpointTestHint();
      await refreshEvaluationGrants();
      window.dispatchEvent(new CustomEvent('pmk-evaluation-grant-updated'));
    } catch (error) { setGrantResult(`Unable to issue evaluation key: ${escapeHtml(error.message || error)}`, true); }
  }

  async function revokeEvaluationGrant(grantId) {
    if (!authorized()) return;
    try {
      const result = await request(`${EVALUATION_GRANTS_ENDPOINT}/${encodeURIComponent(grantId)}`, 'DELETE');
      setGrantResult(`Grant revoked. ${escapeHtml(result.revoked_key_count || 0)} linked key(s) revoked.`);
      oneTimeIssuedKey = '';
      renderEndpointTestHint();
      await refreshEvaluationGrants();
      window.dispatchEvent(new CustomEvent('pmk-evaluation-grant-updated'));
    } catch (error) { setGrantResult(`Unable to revoke evaluation grant: ${escapeHtml(error.message || error)}`, true); }
  }

  async function hydrateEvaluationControls() {
    if (!authorized() || hydrated) return;
    if (hydrationPromise) return hydrationPromise;
    const taskStage = taskIdentityStage();
    if (!taskStage) return;
    taskStage.querySelectorAll('input').forEach((input) => { input.disabled = false; });
    const refresh = document.getElementById('admin-eval-refresh');
    if (refresh) refresh.disabled = false;
    const list = document.getElementById('admin-eval-list');
    if (list) list.innerHTML = '<div class="muted">Loading evaluation grants...</div>';
    const taskList = document.getElementById('admin-eval-task-list');
    if (taskList) taskList.innerHTML = '<div class="muted">Loading canonical tasks...</div>';
    hydrationPromise = Promise.all([loadEvaluationTaskCatalog(), refreshEvaluationGrants()])
      .then(() => { hydrated = true; })
      .catch((error) => setGrantResult(`Unable to load evaluation controls: ${escapeHtml(error.message || error)}`, true))
      .finally(() => { hydrationPromise = null; updateEvaluationReadiness(); });
    return hydrationPromise;
  }

  function initializeEvaluationGrants() {
    if (!renderLockedShell()) return;
    window.addEventListener('pmk-admin-session-verified', hydrateEvaluationControls);
    window.addEventListener('pmk-api-key-category-changed', updateEvaluationReadiness);
    window.addEventListener('pmk-api-key-access-selection-changed', updateEvaluationReadiness);
    window.addEventListener('pmk-evaluation-selection-changed', updateEvaluationReadiness);
    hydrateEvaluationControls();
  }

  window.PMK_ADMIN_EVALUATION_GRANTS = { readiness: evaluationReadiness, updateReadiness: updateEvaluationReadiness, hydrate: hydrateEvaluationControls };
  initializeEvaluationGrants();
})();