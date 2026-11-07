(function () {
  const EVALUATION_GRANTS_ENDPOINT = '/settings/admin/evaluation-grants';
  const EVALUATION_TASK_CATALOG_ENDPOINT =
    '/settings/admin/evaluation-grants/task-catalog';
  const EVALUATION_BINDING_CATALOG_ENDPOINT =
    '/settings/admin/evaluation-grants/binding-catalog';
  const RUNTIME_TASK_ENDPOINT = '/evaluation/runtime/task-execute';
  const GRANT_HOST_ID = 'admin-evaluation-grants';
  const EXTERNAL_CATEGORY = 'external_evaluation';
  const CRM_QUOTA = 100;
  const INTEGRATION_QUOTA = 200;

  let evaluationTaskCatalog = [];
  let evaluationBindingCatalog = [];
  const evaluationGrantsById = new Map();

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
    if (auth && typeof auth.headers === 'function') return auth.headers(extra);
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
      try { data = JSON.parse(rawText); } catch { data = { message: rawText }; }
    }
    if (!response.ok) {
      const detail = data && typeof data === 'object'
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

  function selectedEvaluationType() {
    const value = text(document.getElementById('admin-eval-type')?.value).toLowerCase();
    return value === 'integration' ? 'integration' : 'crm';
  }

  function evaluationQuota(type = selectedEvaluationType()) {
    return type === 'integration' ? INTEGRATION_QUOTA : CRM_QUOTA;
  }

  function renderDerivedQuota() {
    const target = document.getElementById('admin-eval-derived-quota');
    if (!target) return;
    const type = selectedEvaluationType();
    target.textContent = `${evaluationQuota(type)} admitted executions (${type.toUpperCase()} fixed evaluation policy)`;
  }

  function grantForm() {
    return `
      <div class="sec-hdr">
        <div class="sh-title">Evaluation Grant Preparation</div>
        <div class="sh-sub">identity, evaluation type, canonical tasks, prepared bindings, one-time key handoff, execution audit, and revocation</div>
      </div>
      <div class="admin-note">
        External Evaluation is subscription-free and grant-first. The grant is the authority for CRM/Integration type, fixed admitted-execution quota, tasks, bindings, endpoints, expiry, and non-production boundary. The API key cannot expand that authority.
      </div>
      <div class="grid-3">
        <label>Client ID<input id="admin-eval-client-id" type="text" placeholder="evaluation-client"></label>
        <label>Issued to<input id="admin-eval-issued-to" type="text" placeholder="Company or evaluator"></label>
        <label>Duration days<input id="admin-eval-days" type="number" min="1" max="90" value="14"></label>
        <label>Evaluation type
          <select id="admin-eval-type">
            <option value="crm">CRM — 100 admitted executions</option>
            <option value="integration">Integration — 200 admitted executions</option>
          </select>
        </label>
        <div class="card flat">
          <strong>Derived evaluation quota</strong>
          <div id="admin-eval-derived-quota" class="muted" style="margin-top:var(--s-1)">100 admitted executions (CRM fixed evaluation policy)</div>
          <div class="muted">Not a commercial plan and not manually overridable.</div>
        </div>
        <label>Purpose<input id="admin-eval-purpose" type="text" value="Governed external product evaluation"></label>
      </div>
      <div style="margin-top:var(--s-3)">
        <strong>API key task content</strong>
        <div class="muted">Choose only the canonical tasks the Evaluation Grant may authorize.</div>
        <div id="admin-eval-task-list" style="margin-top:var(--s-2)">Loading canonical tasks...</div>
      </div>
      <div style="margin-top:var(--s-3)">
        <strong>Prepared Evaluation Bindings</strong>
        <div class="muted">Required only when <code>POST ${RUNTIME_TASK_ENDPOINT}</code> is selected. Only sandbox-ready bindings with an active short-lived sandbox grant are selectable.</div>
        <div id="admin-eval-binding-list" style="margin-top:var(--s-2)">Loading prepared bindings...</div>
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
      target.innerHTML = '<div class="admin-note danger">Canonical task catalog is unavailable. Grant creation is disabled.</div>';
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
      <fieldset class="card flat" style="margin-top:var(--s-2)">
        <legend><strong>${escapeHtml(domain.replaceAll('_', ' '))}</strong></legend>
        ${tasks.map((task) => `
          <label style="display:block;margin-top:var(--s-2)">
            <input type="checkbox" data-eval-task value="${escapeHtml(task.task_id)}">
            <code>${escapeHtml(task.task_id)}</code> — ${escapeHtml(task.safe_operation)}
            <span class="muted"> · ${escapeHtml(task.operation_class)} · ${(task.required_scope_ids || []).map(escapeHtml).join(', ')}</span>
          </label>
        `).join('')}
      </fieldset>
    `).join('');
    target.querySelectorAll('[data-eval-task]').forEach((input) => {
      input.addEventListener('change', () => {
        renderEvaluationBindingCatalog();
        dispatchEvaluationSelectionChanged();
      });
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
    if (!Array.isArray(values)) return [];
    return values.map((endpoint) => ({
      method: text(endpoint?.method).toUpperCase(),
      path: text(endpoint?.path),
    })).filter((endpoint) => endpoint.method && endpoint.path);
  }

  function runtimeTaskEndpointSelected(endpoints = selectedEvaluationEndpoints()) {
    return endpoints.some(
      (endpoint) => endpoint.method === 'POST' && endpoint.path === RUNTIME_TASK_ENDPOINT
    );
  }

  function selectedEvaluationBindings() {
    return [...document.querySelectorAll('[data-eval-binding]:checked')]
      .map((input) => text(input.value))
      .filter(Boolean);
  }

  function renderEvaluationBindingCatalog() {
    const target = document.getElementById('admin-eval-binding-list');
    if (!target) return;
    const runtimeSelected = runtimeTaskEndpointSelected();
    if (!runtimeSelected) {
      target.innerHTML = '<div class="muted">No binding is required for the selected endpoint envelope.</div>';
      updateEvaluationReadiness();
      return;
    }
    if (!evaluationBindingCatalog.length) {
      target.innerHTML = '<div class="admin-note danger">No prepared Evaluation bindings are available. Runtime task execution remains locked.</div>';
      updateEvaluationReadiness();
      return;
    }
    const selectedTasks = new Set(selectedEvaluationTasks());
    target.innerHTML = evaluationBindingCatalog.map((item) => {
      const taskAllowed = selectedTasks.has(text(item.task_id));
      const selectable = item.selectable === true && taskAllowed;
      const blockers = Array.isArray(item.sandbox_readiness?.blocker_codes)
        ? item.sandbox_readiness.blocker_codes
        : [];
      const status = text(item.sandbox_readiness?.status) || 'not_configured';
      return `
        <label class="card flat" style="display:block;margin-top:var(--s-2)">
          <input type="checkbox" data-eval-binding value="${escapeHtml(item.binding_id)}" ${selectable ? '' : 'disabled'}>
          <code>${escapeHtml(item.binding_id)}</code> — ${escapeHtml(item.display_name || item.task_id)}
          <span class="muted"> · task ${escapeHtml(item.task_id)} · ${escapeHtml(status)} · ${selectable ? 'selectable' : 'locked'}</span>
          ${blockers.length ? `<div class="muted">blockers: ${blockers.map(escapeHtml).join(', ')}</div>` : ''}
          ${!taskAllowed ? '<div class="muted">Select the matching canonical task before using this binding.</div>' : ''}
        </label>`;
    }).join('');
    target.querySelectorAll('[data-eval-binding]').forEach((input) => {
      input.addEventListener('change', dispatchEvaluationSelectionChanged);
    });
    updateEvaluationReadiness();
  }

  async function loadEvaluationBindingCatalog() {
    const payload = await request(EVALUATION_BINDING_CATALOG_ENDPOINT, 'GET');
    evaluationBindingCatalog = Array.isArray(payload.bindings) ? payload.bindings : [];
    renderEvaluationBindingCatalog();
  }

  function evaluationReadiness() {
    const category = text(document.getElementById('admin-api-key-category')?.value);
    const profile = text(document.getElementById('admin-api-key-operational-profile')?.value);
    const clientId = text(document.getElementById('admin-eval-client-id')?.value);
    const issuedTo = text(document.getElementById('admin-eval-issued-to')?.value);
    const purpose = text(document.getElementById('admin-eval-purpose')?.value);
    const duration = Number.parseInt(document.getElementById('admin-eval-days')?.value || '0', 10);
    const evaluationType = selectedEvaluationType();
    const derivedQuota = evaluationQuota(evaluationType);
    const tasks = selectedEvaluationTasks();
    const scopes = selectedEvaluationScopes();
    const endpoints = selectedEvaluationEndpoints();
    const bindings = selectedEvaluationBindings();
    const runtimeSelected = runtimeTaskEndpointSelected(endpoints);
    const bindingById = new Map(evaluationBindingCatalog.map((item) => [text(item.binding_id), item]));
    const bindingsPrepared = bindings.every((bindingId) => {
      const item = bindingById.get(bindingId);
      return item?.selectable === true && tasks.includes(text(item.task_id));
    });
    const grantAuthority = document.body.dataset.adminEvaluationGrants;

    const checks = [
      ['category', category === EXTERNAL_CATEGORY, 'Select External Evaluation Access in Category.'],
      ['administrator', document.body.dataset.adminSession === 'ok', 'Verify an administrator credential.'],
      ['grant_authority', grantAuthority === 'authorized' || grantAuthority === 'loaded', 'Evaluation grant authority must be authorized.'],
      ['operational_profile', Boolean(profile), 'Select an operational profile.'],
      ['evaluation_type', ['crm', 'integration'].includes(evaluationType), 'Select CRM or Integration evaluation type.'],
      ['eligible_endpoint', endpoints.length > 0, 'Select at least one eligible API endpoint.'],
      ['derived_scope', scopes.length > 0, 'Selected endpoints must derive at least one runtime scope.'],
      ['canonical_task', tasks.length > 0, 'Select at least one canonical task.'],
      ['prepared_binding', !runtimeSelected || bindings.length > 0, 'Runtime task execution requires at least one prepared Evaluation binding.'],
      ['binding_task_envelope', !runtimeSelected || bindingsPrepared, 'Every selected binding must be sandbox-ready and match a selected canonical task.'],
      ['client_id', Boolean(clientId), 'Client ID is required.'],
      ['issued_to', Boolean(issuedTo), 'Issued to is required.'],
      ['purpose', purpose.length >= 10, 'Purpose must contain at least 10 characters.'],
      ['duration', Number.isInteger(duration) && duration >= 1 && duration <= 90, 'Duration must be between 1 and 90 days.'],
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
      evaluationType,
      derivedQuota,
      tasks,
      scopes,
      endpoints,
      bindings,
    };
  }

  function updateEvaluationReadiness() {
    renderDerivedQuota();
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
        ? `<strong>READY.</strong> ${escapeHtml(readiness.evaluationType.toUpperCase())} grant · ${readiness.derivedQuota} admitted executions · subscription not required · production disabled.`
        : `<strong>LOCKED.</strong> Complete the remaining gates:<br>${readiness.missing.map((item) => `• ${escapeHtml(item.message)}`).join('<br>')}`;
    }
    window.PMK_ADMIN_EXTERNAL_EVALUATION_CATEGORY_FLOW?.renderContract?.();
    return readiness;
  }

  function inferredGrantType(grant) {
    const stored = text(grant?.evaluation_type).toLowerCase();
    if (stored === 'crm' || stored === 'integration') return stored;
    return Number(grant?.max_requests || 0) === INTEGRATION_QUOTA ? 'integration' : 'crm';
  }

  function grantRow(grant) {
    const active = text(grant.status).toLowerCase() === 'active';
    const tasks = Array.isArray(grant.allowed_task_ids) ? grant.allowed_task_ids : [];
    const scopes = Array.isArray(grant.allowed_scopes) ? grant.allowed_scopes : [];
    const bindings = Array.isArray(grant.allowed_binding_ids) ? grant.allowed_binding_ids : [];
    const type = inferredGrantType(grant);
    const grantId = text(grant.grant_id);
    const actions = active
      ? `<button class="btn primary" data-eval-issue="${escapeHtml(grantId)}" type="button">Issue API Key</button>
         <button class="btn danger" data-eval-revoke="${escapeHtml(grantId)}" type="button">Revoke Grant</button>`
      : '';
    return `
      <div class="card flat" data-eval-grant-card="true" data-eval-grant-id="${escapeHtml(grantId)}" style="margin-top:var(--s-2)">
        <div><strong>${escapeHtml(grant.issued_to || grant.client_id)}</strong> · ${escapeHtml(grant.status)} · ${escapeHtml(type.toUpperCase())}</div>
        <div class="muted">${escapeHtml(grantId)} · client ${escapeHtml(grant.client_id)} · admitted-execution quota ${escapeHtml(grant.max_requests)} · active keys ${escapeHtml(grant.active_key_count || 0)}</div>
        <div class="muted">scopes: ${scopes.length ? scopes.map(escapeHtml).join(', ') : 'backend defaults'}</div>
        <div class="muted">tasks: ${tasks.length ? tasks.map(escapeHtml).join(', ') : 'none'} · authority ${escapeHtml(grant.task_authority_source || 'integration_task_catalog')}</div>
        <div class="muted">bindings: ${bindings.length ? bindings.map(escapeHtml).join(', ') : 'not required'}</div>
        <div class="muted">expires ${escapeHtml(grant.expires_at)} · subscription required: no · production: disabled</div>
        <div style="margin-top:var(--s-2)">${actions}</div>
      </div>`;
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
      evaluationGrantsById.clear();
      grants.forEach((grant) => evaluationGrantsById.set(text(grant.grant_id), grant));
      list.innerHTML = grants.length
        ? grants.map(grantRow).join('')
        : '<div class="muted">No evaluation grants have been issued.</div>';
      window.dispatchEvent(new CustomEvent('pmk-evaluation-grants-rendered'));
    } catch (error) {
      list.innerHTML = `<div class="admin-note danger">Unable to load evaluation grants: ${escapeHtml(error.message || error)}</div>`;
    }
  }

  async function createEvaluationGrant() {
    const readiness = updateEvaluationReadiness();
    if (!readiness.ready) {
      setGrantResult('Evaluation grant creation blocked by the lifecycle readiness contract. Complete every LOCKED gate before retrying.', true);
      return;
    }
    try {
      const result = await request(EVALUATION_GRANTS_ENDPOINT, 'POST', {
        client_id: readiness.clientId,
        user_id: readiness.clientId,
        issued_to: readiness.issuedTo,
        purpose: readiness.purpose,
        evaluation_type: readiness.evaluationType,
        allowed_task_ids: readiness.tasks,
        allowed_binding_ids: readiness.bindings,
        allowed_endpoints: readiness.endpoints,
        ...(readiness.scopes.length ? { allowed_scopes: readiness.scopes } : {}),
        expires_in_days: readiness.duration,
        max_requests: readiness.derivedQuota,
      });
      const grant = result.grant || {};
      evaluationGrantsById.set(text(grant.grant_id), grant);
      setGrantResult(
        `Evaluation grant created: <strong>${escapeHtml(grant.grant_id || '')}</strong><br>` +
        `Type: <strong>${escapeHtml(text(grant.evaluation_type || readiness.evaluationType).toUpperCase())}</strong> · ` +
        `fixed admitted-execution quota: <strong>${escapeHtml(grant.max_requests ?? readiness.derivedQuota)}</strong><br>` +
        `Tasks: ${(grant.allowed_task_ids || []).map(escapeHtml).join(', ')}<br>` +
        `Bindings: ${(grant.allowed_binding_ids || []).map(escapeHtml).join(', ') || 'not required'}<br>` +
        `Scopes: ${(grant.allowed_scopes || []).map(escapeHtml).join(', ') || 'backend defaults'}<br>` +
        `Expires ${escapeHtml(grant.expires_at)} · subscription not required · production disabled`
      );
      await refreshEvaluationGrants();
      dispatchEvaluationSelectionChanged();
    } catch (error) {
      setGrantResult(`Unable to create grant: ${escapeHtml(error.message || error)}`, true);
    }
  }

  function handoffText({ grantId, key, grant, usage }) {
    const tasks = Array.isArray(key.allowed_task_ids) ? key.allowed_task_ids : [];
    const bindings = Array.isArray(key.allowed_binding_ids) ? key.allowed_binding_ids : [];
    const endpoints = Array.isArray(key.allowed_endpoints) ? key.allowed_endpoints : [];
    const type = text(key.evaluation_type || grant?.evaluation_type || inferredGrantType(grant)).toLowerCase() || 'crm';
    const quota = Number(key.evaluation_request_limit || grant?.max_requests || evaluationQuota(type));
    const portalUrl = `${window.location.origin}/console/evaluation.html`;
    const endpointText = endpoints.length
      ? endpoints.map((item) => `${text(item.method).toUpperCase()} ${text(item.path)}`).join(', ')
      : text(usage.example_endpoint || '/evaluation/runtime/status');
    return [
      'Processual Maestro — External Evaluation Access',
      `Portal: ${portalUrl}`,
      'Authentication header: X-API-Key',
      `Evaluation Grant ID: ${grantId}`,
      `API Key ID: ${text(key.key_id || 'see issued metadata')}`,
      `API Key prefix: ${text(key.prefix || 'see issued metadata')}`,
      `Evaluation type: ${type.toUpperCase()}`,
      `Admitted-execution quota: ${quota}`,
      `Expires: ${text(key.expires_at || grant?.expires_at || 'see grant')}`,
      `Allowed canonical tasks: ${tasks.join(', ') || 'none'}`,
      `Prepared bindings: ${bindings.join(', ') || 'not required'}`,
      `Allowed endpoints: ${endpointText}`,
      'Idempotency: reuse the same idempotency key only for the same logical retry; durable replay consumes +0 quota.',
      'Execution stages: admitted -> executing -> succeeded/failed -> evidence persisted.',
      'Status/dashboard reads consume +0 quota.',
      'Subscription/registration/commercial quota: not required.',
      'Production execution: disabled.',
      'Use only synthetic/non-production data and the scope sealed into this grant.',
      'The customer receipt is available in the Evaluation dashboard; final qualification remains operator-controlled.',
    ].join('\n');
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
      const grant = evaluationGrantsById.get(text(grantId)) || {};
      const usage = result.onboarding_usage || {};
      const tasks = Array.isArray(key.allowed_task_ids) ? key.allowed_task_ids : [];
      const scopes = Array.isArray(key.scopes) ? key.scopes : [];
      const bindings = Array.isArray(key.allowed_binding_ids) ? key.allowed_binding_ids : [];
      const type = text(key.evaluation_type || grant.evaluation_type || inferredGrantType(grant)).toLowerCase() || 'crm';
      const safeHandoff = handoffText({ grantId, key, grant, usage });
      setGrantResult(`
        <strong>One-time Evaluation API key created.</strong><br>
        Copy the secret now; it will not be displayed again. Send it through the approved secret-delivery channel separately from the safe handoff text.<br>
        <span class="mono-block" style="display:block;margin-top:var(--s-2)">X-API-Key: ${escapeHtml(secret)}</span>
        <button id="admin-eval-copy-issued-key" class="btn secondary" type="button" style="margin-top:var(--s-2)">Copy one-time API key</button>
        <div class="card flat" style="margin-top:var(--s-3)">
          <strong>Safe customer handoff</strong>
          <div class="muted">Technical/operational context only; no second secret is included.</div>
          <pre id="admin-eval-customer-handoff" class="mono-block" style="white-space:pre-wrap">${escapeHtml(safeHandoff)}</pre>
          <button id="admin-eval-copy-handoff" class="btn secondary" type="button">Copy customer handoff</button>
        </div>
        <div class="admin-note" style="margin-top:var(--s-2)">
          Grant ${escapeHtml(grantId)} · ${escapeHtml(type.toUpperCase())} · quota ${escapeHtml(key.evaluation_request_limit || evaluationQuota(type))} · expires ${escapeHtml(key.expires_at || '')}<br>
          Tasks: ${escapeHtml(tasks.join(', ') || 'none')}<br>
          Bindings: ${escapeHtml(bindings.join(', ') || 'not required')}<br>
          Scopes: ${escapeHtml(scopes.join(', ') || 'none')}<br>
          Subscription required: no · Production: disabled
        </div>
      `);
      document.getElementById('admin-eval-copy-issued-key')?.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(secret); } catch {}
      });
      document.getElementById('admin-eval-copy-handoff')?.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(safeHandoff); } catch {}
      });
      await refreshEvaluationGrants();
      window.dispatchEvent(new CustomEvent('pmk-evaluation-grant-updated'));
    } catch (error) {
      setGrantResult(`Unable to issue evaluation key: ${escapeHtml(error.message || error)}`, true);
    }
  }

  async function revokeEvaluationGrant(grantId) {
    try {
      const result = await request(`${EVALUATION_GRANTS_ENDPOINT}/${encodeURIComponent(grantId)}`, 'DELETE');
      setGrantResult(`Grant revoked. ${escapeHtml(result.revoked_key_count || 0)} linked key(s) revoked.`);
      await refreshEvaluationGrants();
      window.dispatchEvent(new CustomEvent('pmk-evaluation-grant-updated'));
    } catch (error) {
      setGrantResult(`Unable to revoke grant: ${escapeHtml(error.message || error)}`, true);
    }
  }

  function bindGrantActionDelegation(host) {
    if (!host || host.dataset.evaluationGrantActionsBound === 'true') return;
    host.dataset.evaluationGrantActionsBound = 'true';
    host.addEventListener('click', (event) => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target) return;
      const issueButton = target.closest('[data-eval-issue]');
      if (issueButton && host.contains(issueButton)) {
        event.preventDefault();
        event.stopPropagation();
        issueEvaluationKey(issueButton.dataset.evalIssue);
        return;
      }
      const revokeButton = target.closest('[data-eval-revoke]');
      if (revokeButton && host.contains(revokeButton)) {
        event.preventDefault();
        event.stopPropagation();
        revokeEvaluationGrant(revokeButton.dataset.evalRevoke);
      }
    });
  }

  async function initialize() {
    const host = ensureGrantHost();
    if (!host) return;
    if (!host.dataset.evaluationGrantUiInitialized) {
      host.dataset.evaluationGrantUiInitialized = 'true';
      host.innerHTML = grantForm();
      bindGrantActionDelegation(host);
      document.getElementById('admin-eval-create')?.addEventListener('click', createEvaluationGrant);
      document.getElementById('admin-eval-refresh')?.addEventListener('click', refreshEvaluationGrants);
      document.getElementById('admin-eval-type')?.addEventListener('change', updateEvaluationReadiness);
      ['admin-eval-client-id', 'admin-eval-issued-to', 'admin-eval-purpose', 'admin-eval-days'].forEach((id) => {
        document.getElementById(id)?.addEventListener('input', updateEvaluationReadiness);
      });
      window.addEventListener('pmk-evaluation-selection-changed', updateEvaluationReadiness);
    }
    try {
      await Promise.all([
        loadEvaluationTaskCatalog(),
        loadEvaluationBindingCatalog(),
        refreshEvaluationGrants(),
      ]);
      document.body.dataset.adminEvaluationGrants = 'loaded';
      updateEvaluationReadiness();
    } catch (error) {
      document.body.dataset.adminEvaluationGrants = 'error';
      host.innerHTML = `<div class="admin-note danger">External Evaluation management unavailable: ${escapeHtml(error.message || error)}</div>`;
    }
  }

  window.PMK_ADMIN_EVALUATION_GRANTS = {
    initialize,
    issueKey: issueEvaluationKey,
    refresh: refreshEvaluationGrants,
    refreshBindingCatalog: loadEvaluationBindingCatalog,
  };

  initialize();
})();