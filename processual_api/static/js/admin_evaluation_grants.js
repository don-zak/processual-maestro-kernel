(function () {
  const EVALUATION_GRANTS_ENDPOINT = '/settings/admin/evaluation-grants';
  const EVALUATION_TASK_CATALOG_ENDPOINT =
    '/settings/admin/evaluation-grants/task-catalog';
  const GRANT_HOST_ID = 'admin-evaluation-grants';
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
    const page = document.getElementById('page-admin-api-keys');
    if (!page) return null;
    host = document.createElement('div');
    host.className = 'card';
    host.id = GRANT_HOST_ID;
    host.style.marginTop = 'var(--s-5)';
    page.appendChild(host);
    return host;
  }

  function grantForm() {
    return `
      <div class="sec-hdr">
        <div class="sh-title">External Evaluation Access</div>
        <div class="sh-sub">supervisor-governed API access outside paid subscription onboarding</div>
      </div>
      <div class="admin-note">
        Evaluation grants are temporary, quota-bound, non-production entitlements. Select the API key content from the same canonical Maestro task catalog used by the specialization/integration task workspace. Administrative scopes are rejected by the backend.
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
      <div style="margin-top:var(--s-3)">
        <button id="admin-eval-create" class="btn primary" type="button">Create Evaluation Grant</button>
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
    const clientId = text(document.getElementById('admin-eval-client-id')?.value);
    const issuedTo = text(document.getElementById('admin-eval-issued-to')?.value);
    const purpose = text(document.getElementById('admin-eval-purpose')?.value);
    const expiresInDays = Number.parseInt(
      document.getElementById('admin-eval-days')?.value || '14',
      10
    );
    const maxRequests = Number.parseInt(
      document.getElementById('admin-eval-max-requests')?.value || '100',
      10
    );
    const allowedTaskIds = selectedEvaluationTasks();

    if (!clientId || !issuedTo || purpose.length < 10) {
      setGrantResult(
        'Client ID, issued-to, and a descriptive purpose are required.',
        true
      );
      return;
    }
    if (!allowedTaskIds.length) {
      setGrantResult(
        'Select at least one canonical task for the API key content.',
        true
      );
      return;
    }

    try {
      const result = await request(EVALUATION_GRANTS_ENDPOINT, 'POST', {
        client_id: clientId,
        user_id: clientId,
        issued_to: issuedTo,
        purpose,
        allowed_task_ids: allowedTaskIds,
        expires_in_days: expiresInDays,
        max_requests: maxRequests,
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
    document
      .getElementById('admin-eval-create')
      ?.addEventListener('click', createEvaluationGrant);
    document
      .getElementById('admin-eval-refresh')
      ?.addEventListener('click', refreshEvaluationGrants);
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
  }

  initializeEvaluationGrants();
})();