(function () {
  const EVALUATION_GRANTS_ENDPOINT = '/settings/admin/evaluation-grants';
  const EVALUATION_TASK_CATALOG_ENDPOINT =
    '/settings/admin/evaluation-grants/task-catalog';
  const EVALUATION_BINDING_CATALOG_ENDPOINT =
    '/settings/admin/evaluation-grants/binding-catalog';
  const RUNTIME_TASK_ENDPOINT = '/evaluation/runtime/task-execute';
  const GRANT_HOST_ID = 'admin-evaluation-grants';
  const EXTERNAL_CATEGORY = 'external_evaluation';
  const STANDARD_QUOTA = 100;
  const INTEGRATION_QUOTA = 200;
  let evaluationTaskCatalog = [];
  let evaluationBindingCatalog = [];

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
        <div class="sh-sub">identity, Maestro Unit limit, canonical tasks, prepared bindings, one-time issue, WhatsApp delivery, and revoke</div>
      </div>
      <div class="admin-note">
        Evaluation grants remain temporary, non-production entitlements. Standard evaluations use 100 Maestro Units; Integration evaluations use 200. Raw API keys are shown only once and are never reprinted from stored metadata.
      </div>
      <div class="grid-3">
        <label>Client ID<input id="admin-eval-client-id" type="text" placeholder="evaluation-client"></label>
        <label>Issued to<input id="admin-eval-issued-to" type="text" placeholder="Company or evaluator"></label>
        <label>Evaluation type
          <select id="admin-eval-type">
            <option value="standard" selected>Standard</option>
            <option value="integration">Integration</option>
          </select>
        </label>
        <label>Duration days<input id="admin-eval-days" type="number" min="1" max="90" value="14"></label>
        <label>Maestro Unit limit<input id="admin-eval-max-requests" type="number" min="1" max="5000" value="100" readonly></label>
        <label style="grid-column:span 2">Purpose<input id="admin-eval-purpose" type="text" value="Governed external product evaluation"></label>
      </div>
      <div style="margin-top:var(--s-3)">
        <strong>API key task content</strong>
        <div class="muted">Choose only the canonical tasks this evaluation key may represent.</div>
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

  function syncEvaluationTypeQuota() {
    const type = text(document.getElementById('admin-eval-type')?.value) || 'standard';
    const quota = document.getElementById('admin-eval-max-requests');
    if (quota) quota.value = type === 'integration' ? String(INTEGRATION_QUOTA) : String(STANDARD_QUOTA);
    dispatchEvaluationSelectionChanged();
    updateEvaluationReadiness();
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
    return values
      .map((endpoint) => ({
        method: text(endpoint?.method).toUpperCase(),
        path: text(endpoint?.path),
      }))
      .filter((endpoint) => endpoint.method && endpoint.path);
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
      target.innerHTML =
        '<div class="admin-note danger">No prepared Evaluation bindings are available. Runtime task execution remains locked.</div>';
      updateEvaluationReadiness();
      return;
    }
    const selectedTasks = new Set(selectedEvaluationTasks());
    target.innerHTML = evaluationBindingCatalog
      .map((item) => {
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
          </label>
        `;
      })
      .join('');
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
    const evaluationType = text(document.getElementById('admin-eval-type')?.value) || 'standard';
    const duration = Number.parseInt(document.getElementById('admin-eval-days')?.value || '0', 10);
    const requestLimit = Number.parseInt(document.getElementById('admin-eval-max-requests')?.value || '0', 10);
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
    const expectedQuota = evaluationType === 'integration' ? INTEGRATION_QUOTA : STANDARD_QUOTA;

    const checks = [
      ['category', category === EXTERNAL_CATEGORY, 'Select External Evaluation Access in Category.'],
      ['administrator', document.body.dataset.adminSession === 'ok', 'Verify an administrator credential.'],
      ['grant_authority', grantAuthority === 'authorized' || grantAuthority === 'loaded', 'Evaluation grant authority must be authorized.'],
      ['operational_profile', Boolean(profile), 'Select an operational profile.'],
      ['eligible_endpoint', endpoints.length > 0, 'Select at least one eligible API endpoint.'],
      ['derived_scope', scopes.length > 0, 'Selected endpoints must derive at least one runtime scope.'],
      ['canonical_task', tasks.length > 0, 'Select at least one canonical task.'],
      ['prepared_binding', !runtimeSelected || bindings.length > 0, 'Runtime task execution requires at least one prepared Evaluation binding.'],
      ['binding_task_envelope', !runtimeSelected || bindingsPrepared, 'Every selected binding must be sandbox-ready and match a selected canonical task.'],
      ['client_id', Boolean(clientId), 'Client ID is required.'],
      ['issued_to', Boolean(issuedTo), 'Issued to is required.'],
      ['purpose', purpose.length >= 10, 'Purpose must contain at least 10 characters.'],
      ['duration', Number.isInteger(duration) && duration >= 1 && duration <= 90, 'Duration must be between 1 and 90 days.'],
      ['quota', requestLimit === expectedQuota, `Maestro Unit limit must be ${expectedQuota} for ${evaluationType}.`],
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
      evaluationType,
      duration,
      requestLimit,
      tasks,
      scopes,
      endpoints,
      bindings,
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
        ? `<strong>READY.</strong> ${escapeHtml(readiness.evaluationType)} evaluation · ${escapeHtml(readiness.requestLimit)} Maestro Units · ${escapeHtml(readiness.duration)} days. Backend validation remains authoritative.`
        : `<strong>LOCKED.</strong> Complete the remaining gates:<br>${readiness.missing
            .map((item) => `• ${escapeHtml(item.message)}`)
            .join('<br>')}`;
    }
    window.PMK_ADMIN_EXTERNAL_EVALUATION_CATEGORY_FLOW?.renderContract?.();
    return readiness;
  }

  function keyListId(grantId) {
    return `admin-eval-keys-${String(grantId).replace(/[^a-zA-Z0-9_-]/g, '-')}`;
  }

  function grantRow(grant) {
    const active = text(grant.status).toLowerCase() === 'active';
    const tasks = Array.isArray(grant.allowed_task_ids) ? grant.allowed_task_ids : [];
    const scopes = Array.isArray(grant.allowed_scopes) ? grant.allowed_scopes : [];
    const bindings = Array.isArray(grant.allowed_binding_ids) ? grant.allowed_binding_ids : [];
    const evaluationType = text(grant.evaluation_type) || 'standard';
    const actions = active
      ? `<button class="btn secondary" data-eval-issue="${escapeHtml(grant.grant_id)}" type="button">Issue API Key</button>
         <button class="btn danger" data-eval-revoke="${escapeHtml(grant.grant_id)}" type="button">Revoke Grant</button>`
      : '';
    return `
      <div class="card flat" style="margin-top:var(--s-2)">
        <div><strong>${escapeHtml(grant.issued_to || grant.client_id)}</strong> · ${escapeHtml(grant.status)} · ${escapeHtml(evaluationType)}</div>
        <div class="muted">${escapeHtml(grant.grant_id)} · client ${escapeHtml(grant.client_id)} · ${escapeHtml(grant.max_requests)} Maestro Units · keys ${escapeHtml(grant.active_key_count || 0)}</div>
        <div class="muted">scopes: ${scopes.length ? scopes.map(escapeHtml).join(', ') : 'backend defaults'}</div>
        <div class="muted">tasks: ${tasks.length ? tasks.map(escapeHtml).join(', ') : 'none'} · authority ${escapeHtml(grant.task_authority_source || 'integration_task_catalog')}</div>
        <div class="muted">bindings: ${bindings.length ? bindings.map(escapeHtml).join(', ') : 'not required'}</div>
        <div class="muted">expires ${escapeHtml(grant.expires_at)} · subscription required: no · production: disabled</div>
        <div style="margin-top:var(--s-2)">${actions}</div>
        <div id="${keyListId(grant.grant_id)}" style="margin-top:var(--s-2)"><span class="muted">Loading issued keys...</span></div>
      </div>
    `;
  }

  function keyRow(grantId, key) {
    const active = text(key.status).toLowerCase() === 'enabled';
    const sent = text(key.delivery_status).toLowerCase() === 'sent';
    const quota = Number(key.quota_limit || key.evaluation_request_limit || 0);
    const used = Number(key.usage_count || 0);
    const remaining = Math.max(0, quota - used);
    const actions = active
      ? `${sent ? '' : `<button class="btn secondary" data-eval-send-key="${escapeHtml(key.key_id)}" data-eval-grant-id="${escapeHtml(grantId)}" type="button">Send</button>`}
         <button class="btn danger" data-eval-revoke-key="${escapeHtml(key.key_id)}" data-eval-grant-id="${escapeHtml(grantId)}" type="button">Revoke</button>`
      : '';
    return `
      <div class="card flat" style="margin-top:var(--s-2)">
        <div><strong>${escapeHtml(key.prefix)}</strong> · ${escapeHtml(key.status)} · ${escapeHtml(key.evaluation_type || 'standard')}</div>
        <div class="muted">Key ID ${escapeHtml(key.key_id)} · ${escapeHtml(remaining)} / ${escapeHtml(quota)} Maestro Units remaining</div>
        <div class="muted">Delivery: ${sent ? 'SENT via WhatsApp' : 'not sent'}${key.delivered_at ? ` · ${escapeHtml(key.delivered_at)}` : ''}</div>
        <div class="muted">Last used: ${escapeHtml(key.last_used_at || 'never')} · expires ${escapeHtml(key.expires_at || '')}</div>
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

  async function refreshEvaluationKeys(grantId) {
    const target = document.getElementById(keyListId(grantId));
    if (!target) return;
    try {
      const payload = await request(
        `${EVALUATION_GRANTS_ENDPOINT}/${encodeURIComponent(grantId)}/keys`,
        'GET'
      );
      const keys = Array.isArray(payload.keys) ? payload.keys : [];
      target.innerHTML = keys.length
        ? `<div class="muted"><strong>Issued keys</strong> — raw secrets are never reprinted.</div>${keys.map((key) => keyRow(grantId, key)).join('')}`
        : '<div class="muted">No API keys issued for this grant.</div>';
      bindKeyActions();
    } catch (error) {
      target.innerHTML = `<div class="admin-note danger">Unable to load issued keys: ${escapeHtml(error.message || error)}</div>`;
    }
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
      grants.forEach((grant) => refreshEvaluationKeys(grant.grant_id));
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
        evaluation_type: readiness.evaluationType,
        allowed_task_ids: readiness.tasks,
        allowed_binding_ids: readiness.bindings,
        allowed_endpoints: readiness.endpoints,
        ...(allowedScopes.length ? { allowed_scopes: allowedScopes } : {}),
        expires_in_days: readiness.duration,
        max_requests: readiness.requestLimit,
      });
      const grant = result.grant || {};
      setGrantResult(
        `Evaluation grant created: <strong>${escapeHtml(grant.grant_id || '')}</strong><br>` +
        `Type: ${escapeHtml(grant.evaluation_type || readiness.evaluationType)}<br>` +
        `Tasks: ${(grant.allowed_task_ids || []).map(escapeHtml).join(', ')}<br>` +
        `Bindings: ${(grant.allowed_binding_ids || []).map(escapeHtml).join(', ') || 'not required'}<br>` +
        `Scopes: ${(grant.allowed_scopes || []).map(escapeHtml).join(', ') || 'backend defaults'}<br>` +
        `Maestro Unit limit: ${escapeHtml(grant.max_requests)} · expires ${escapeHtml(grant.expires_at)} · production disabled`
      );
      await refreshEvaluationGrants();
      dispatchEvaluationSelectionChanged();
    } catch (error) {
      setGrantResult(`Unable to create grant: ${escapeHtml(error.message || error)}`, true);
    }
  }

  async function markEvaluationKeySent(grantId, keyId) {
    try {
      const result = await request(
        `${EVALUATION_GRANTS_ENDPOINT}/${encodeURIComponent(grantId)}/keys/${encodeURIComponent(keyId)}/delivery`,
        'POST',
        { channel: 'whatsapp' }
      );
      const key = result.key || {};
      setGrantResult(
        `Delivery recorded: <strong>${escapeHtml(key.prefix || keyId)}</strong> sent via WhatsApp. Raw key content was not stored or reprinted.`
      );
      await refreshEvaluationKeys(grantId);
    } catch (error) {
      setGrantResult(`Unable to record WhatsApp delivery: ${escapeHtml(error.message || error)}`, true);
    }
  }

  async function revokeEvaluationKey(grantId, keyId) {
    if (!window.confirm('Revoke this evaluation API key? The key will stop working immediately.')) return;
    try {
      const result = await request(
        `${EVALUATION_GRANTS_ENDPOINT}/${encodeURIComponent(grantId)}/keys/${encodeURIComponent(keyId)}`,
        'DELETE'
      );
      const key = result.key || {};
      setGrantResult(`Evaluation API key revoked: <strong>${escapeHtml(key.prefix || keyId)}</strong>.`);
      await refreshEvaluationGrants();
      window.dispatchEvent(new CustomEvent('pmk-evaluation-grant-updated'));
    } catch (error) {
      setGrantResult(`Unable to revoke evaluation key: ${escapeHtml(error.message || error)}`, true);
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
      const bindings = Array.isArray(key.allowed_binding_ids) ? key.allowed_binding_ids : [];
      const usage = result.onboarding_usage || {};
      const header = text(usage.header) || 'X-API-Key';
      const exampleEndpoint = text(usage.example_endpoint) || '/adapters/status';
      setGrantResult(`
        <strong>One-time evaluation API key created.</strong><br>
        Copy it now and send it from the administrator's WhatsApp account. It will not be displayed again after this issue view is replaced.<br>
        <span class="mono-block" style="display:block;margin-top:var(--s-2)">X-API-Key: ${escapeHtml(secret)}</span>
        ${header !== 'X-API-Key' ? `<div class="muted">Backend header: ${escapeHtml(header)}</div>` : ''}
        <div style="margin-top:var(--s-2)">
          <button id="admin-eval-copy-issued-key" class="btn secondary" type="button">Copy API Key</button>
          <button id="admin-eval-send-issued-key" class="btn secondary" type="button">Send</button>
          <button id="admin-eval-revoke-issued-key" class="btn danger" type="button">Revoke</button>
        </div>
        <strong>Key ID</strong>: ${escapeHtml(key.key_id || '')}<br>
        <strong>Grant</strong>: ${escapeHtml(grantId)}<br>
        <strong>Client</strong>: ${escapeHtml(key.client_id || '')}<br>
        <strong>Type</strong>: ${escapeHtml(key.evaluation_type || 'standard')}<br>
        <strong>Scopes</strong>: ${escapeHtml(scopes.join(', ') || 'none')}<br>
        <strong>Task scope IDs</strong>: ${escapeHtml(taskScopes.join(', ') || 'none')}<br>
        <strong>Bound tasks:</strong> ${escapeHtml(tasks.join(', ') || 'none')}<br>
        <strong>Prepared bindings:</strong> ${escapeHtml(bindings.join(', ') || 'not required')}<br>
        <strong>Maestro Unit limit</strong>: ${escapeHtml(key.evaluation_request_limit)}<br>
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
      document.getElementById('admin-eval-send-issued-key')?.addEventListener('click', () =>
        markEvaluationKeySent(grantId, key.key_id)
      );
      document.getElementById('admin-eval-revoke-issued-key')?.addEventListener('click', () =>
        revokeEvaluationKey(grantId, key.key_id)
      );
      await refreshEvaluationGrants();
      window.dispatchEvent(new CustomEvent('pmk-evaluation-grant-updated'));
    } catch (error) {
      setGrantResult(`Unable to issue evaluation key: ${escapeHtml(error.message || error)}`, true);
    }
  }

  async function revokeEvaluationGrant(grantId) {
    if (!window.confirm('Revoke this evaluation grant and all linked keys?')) return;
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
      setGrantResult(`Unable to revoke evaluation grant: ${escapeHtml(error.message || error)}`, true);
    }
  }

  function bindKeyActions() {
    document.querySelectorAll('[data-eval-send-key]').forEach((button) => {
      button.addEventListener('click', () =>
        markEvaluationKeySent(button.dataset.evalGrantId, button.dataset.evalSendKey)
      );
    });
    document.querySelectorAll('[data-eval-revoke-key]').forEach((button) => {
      button.addEventListener('click', () =>
        revokeEvaluationKey(button.dataset.evalGrantId, button.dataset.evalRevokeKey)
      );
    });
  }

  function bindGrantActions() {
    document.querySelectorAll('[data-eval-issue]').forEach((button) => {
      button.addEventListener('click', () => issueEvaluationKey(button.dataset.evalIssue));
    });
    document.querySelectorAll('[data-eval-revoke]').forEach((button) => {
      button.addEventListener('click', () => revokeEvaluationGrant(button.dataset.evalRevoke));
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
    document.getElementById('admin-eval-type')?.addEventListener('change', syncEvaluationTypeQuota);
    document.getElementById('admin-eval-create')?.addEventListener('click', createEvaluationGrant);
    document.getElementById('admin-eval-refresh')?.addEventListener('click', refreshEvaluationGrants);

    window.addEventListener('pmk-admin-session-verified', updateEvaluationReadiness);
    window.addEventListener('pmk-api-key-category-changed', () => {
      renderEvaluationBindingCatalog();
      updateEvaluationReadiness();
    });
    window.addEventListener('pmk-api-key-access-selection-changed', () => {
      renderEvaluationBindingCatalog();
      updateEvaluationReadiness();
    });
    window.addEventListener('pmk-evaluation-selection-changed', updateEvaluationReadiness);

    try {
      await loadEvaluationTaskCatalog();
    } catch (error) {
      evaluationTaskCatalog = [];
      renderEvaluationTaskCatalog();
      setGrantResult(`Unable to load canonical task catalog: ${escapeHtml(error.message || error)}`, true);
    }
    try {
      await loadEvaluationBindingCatalog();
    } catch (error) {
      evaluationBindingCatalog = [];
      renderEvaluationBindingCatalog();
      setGrantResult(`Unable to load prepared Evaluation bindings: ${escapeHtml(error.message || error)}`, true);
    }
    syncEvaluationTypeQuota();
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
