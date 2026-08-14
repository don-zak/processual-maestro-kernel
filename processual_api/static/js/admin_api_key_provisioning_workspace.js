(function () {
  const CARD_ID = 'admin-api-key-lifecycle-card';
  const WORKSPACE_ID = 'admin-api-key-provisioning-workspace';
  const PROFILE_ENDPOINT = '/settings/admin/api-key-operational-profiles';
  const ACCESS_CATALOG_ENDPOINT = '/settings/admin/api-key-access-catalog';
  const MAX_INIT_ATTEMPTS = 20;
  const INIT_RETRY_MS = 100;

  let operationalProfiles = [];
  let accessCatalog = [];
  let initAttempts = 0;

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
    let headers = new Headers();
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') {
      const current = auth.headers();
      headers = current instanceof Headers ? new Headers(current) : new Headers(current || {});
    }
    Object.entries(extra).forEach(([key, value]) => headers.set(key, value));
    return headers;
  }

  async function requestJson(path) {
    const response = await fetch(path, {
      method: 'GET',
      credentials: 'include',
      headers: authHeaders({ Accept: 'application/json' }),
    });
    const raw = await response.text();
    let data = {};
    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch {
        data = { message: raw };
      }
    }
    if (!response.ok) {
      const detail = data.detail || data.message || `HTTP ${response.status}`;
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function value(id) {
    return text(document.getElementById(id)?.value);
  }

  function scopes() {
    return value('admin-api-key-scopes')
      .split(/[\n,]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function selectedProfile() {
    const profileId = value('admin-api-key-operational-profile');
    return operationalProfiles.find((profile) => profile.profile_id === profileId) || null;
  }

  function provisioningMode() {
    return value('admin-api-key-provisioning-mode') || 'standard';
  }

  function selectedEndpointRows() {
    const selectedKeys = new Set(
      [...document.querySelectorAll('[data-api-key-access-endpoint]:checked')]
        .map((input) => text(input.value))
        .filter(Boolean)
    );
    return accessCatalog.filter((endpoint) =>
      selectedKeys.has(`${endpoint.method} ${endpoint.path}`)
    );
  }

  function selectedEndpointScopes() {
    return [...new Set(
      selectedEndpointRows().flatMap((endpoint) =>
        Array.isArray(endpoint.required_scopes) ? endpoint.required_scopes : []
      )
    )].sort();
  }

  function selectedEndpoints() {
    return selectedEndpointRows().map((endpoint) => ({
      method: endpoint.method,
      path: endpoint.path,
      capability: endpoint.capability,
      required_scopes: Array.isArray(endpoint.required_scopes)
        ? [...endpoint.required_scopes]
        : [],
    }));
  }

  function syncScopesFromEndpointSelection() {
    const derivedScopes = selectedEndpointScopes();
    const target = document.getElementById('admin-api-key-scopes');
    const status = document.getElementById('admin-api-key-access-selection-status');
    if (target && derivedScopes.length) {
      target.value = derivedScopes.join('\n');
      target.dispatchEvent(new Event('input', { bubbles: true }));
    }
    if (status) {
      const endpointCount = selectedEndpointRows().length;
      status.textContent = endpointCount
        ? `${endpointCount} endpoint(s) selected · ${derivedScopes.length} derived scope(s). Backend scope enforcement remains authoritative.`
        : 'No endpoint selected. Existing category/profile scopes remain unchanged.';
    }
    renderPreview();
    try {
      window.dispatchEvent(new CustomEvent('pmk-api-key-access-selection-changed'));
    } catch {
      window.dispatchEvent(new Event('pmk-api-key-access-selection-changed'));
    }
  }

  function updateGenerateGate() {
    const button = document.getElementById('admin-api-key-generate-btn');
    const status = document.getElementById('admin-api-key-provisioning-mode-status');
    if (!button) return;

    if (provisioningMode() === 'external_evaluation') {
      button.disabled = true;
      button.dataset.evaluationModeDisabled = 'true';
      button.title = 'External Evaluation keys must be created through the evaluation grant authority.';
      if (status) {
        status.className = 'admin-note';
        status.textContent =
          'External Evaluation mode uses the evaluation grant authority. Endpoint selection below supplies explicit non-admin runtime scopes; task binding and issuance remain governed by /settings/admin/evaluation-grants.';
      }
      return;
    }

    if (button.dataset.evaluationModeDisabled === 'true') {
      button.disabled = false;
      delete button.dataset.evaluationModeDisabled;
      button.removeAttribute('title');
    }
    if (status) {
      status.className = 'admin-note';
      status.textContent =
        'Standard / Integration mode uses the existing governed /settings/api-keys lifecycle. Selecting endpoints derives the scope set shown in the key form.';
    }
  }

  function renderProfileDetails() {
    const target = document.getElementById('admin-api-key-operational-profile-details');
    if (!target) return;
    const profile = selectedProfile();
    if (!profile) {
      target.innerHTML = '<div class="muted">Select an operational profile to inspect its governed capabilities.</div>';
      return;
    }

    const allowed = Array.isArray(profile.allowed_scopes) ? profile.allowed_scopes : [];
    const forbidden = Array.isArray(profile.forbidden_scopes) ? profile.forbidden_scopes : [];
    target.innerHTML = `
      <div class="admin-note" style="margin-top:var(--s-2)">
        Selected operational intent only. Runtime endpoint selection and backend scope enforcement remain authoritative.
      </div>
      <div class="grid-3" style="margin-top:var(--s-2)">
        <div class="card flat"><strong>Environment</strong><div>${escapeHtml(profile.environment || 'sandbox')}</div></div>
        <div class="card flat"><strong>Read only</strong><div>${profile.read_only ? 'yes' : 'no'}</div></div>
        <div class="card flat"><strong>Write allowed</strong><div>${profile.write_allowed ? 'yes' : 'no'}</div></div>
        <div class="card flat"><strong>Production</strong><div>${profile.production_allowed ? 'allowed' : 'disabled'}</div></div>
        <div class="card flat"><strong>Supervisor for write</strong><div>${profile.requires_supervisor_for_write ? 'required' : 'not required'}</div></div>
        <div class="card flat"><strong>Runtime connector</strong><div>${profile.runtime_connector_approved ? 'approved' : 'not approved'}</div></div>
      </div>
      <div style="margin-top:var(--s-2)"><strong>Allowed operational intent</strong><div class="mono-block" style="white-space:pre-wrap">${escapeHtml(allowed.join('\n') || 'none')}</div></div>
      <div style="margin-top:var(--s-2)"><strong>Forbidden operational intent</strong><div class="mono-block" style="white-space:pre-wrap">${escapeHtml(forbidden.join('\n') || 'none')}</div></div>
      <div class="muted" style="margin-top:var(--s-2)">${escapeHtml(profile.next_action || '')}</div>
    `;
  }

  function renderAccessCatalog() {
    const grantableTarget = document.getElementById('admin-api-key-grantable-endpoints');
    const allTarget = document.getElementById('admin-api-key-all-endpoints');
    const status = document.getElementById('admin-api-key-access-catalog-status');
    if (!grantableTarget || !allTarget) return;

    const grantable = accessCatalog.filter((endpoint) => endpoint.grantable);
    grantableTarget.innerHTML = grantable.length
      ? grantable.map((endpoint) => {
          const key = `${endpoint.method} ${endpoint.path}`;
          const scopes = Array.isArray(endpoint.required_scopes) ? endpoint.required_scopes : [];
          return `
            <label class="card flat" style="display:block;margin-top:var(--s-2)">
              <input type="checkbox" data-api-key-access-endpoint value="${escapeHtml(key)}">
              <strong>${escapeHtml(endpoint.method)}</strong> <code>${escapeHtml(endpoint.path)}</code>
              <div>${escapeHtml(endpoint.capability || endpoint.name || endpoint.path)}</div>
              <div class="muted">scopes: ${escapeHtml(scopes.join(', ') || 'none')} · production disabled</div>
            </label>
          `;
        }).join('')
      : '<div class="admin-note danger">No grantable runtime endpoints are available.</div>';

    allTarget.innerHTML = accessCatalog.length
      ? `
        <details>
          <summary>${accessCatalog.length} registered backend route/method entries · visibility only for non-grantable routes</summary>
          <div style="max-height:28rem;overflow:auto;margin-top:var(--s-2)">
            ${accessCatalog.map((endpoint) => `
              <div class="admin-api-key-metadata-card-row">
                <strong>${escapeHtml(endpoint.method)} ${escapeHtml(endpoint.path)}</strong>
                <span>${endpoint.grantable ? 'grantable' : 'locked'} · ${escapeHtml(endpoint.capability || endpoint.name || '')}</span>
              </div>
            `).join('')}
          </div>
        </details>
      `
      : '<div class="muted">Backend route catalog unavailable.</div>';

    grantableTarget.querySelectorAll('[data-api-key-access-endpoint]').forEach((input) => {
      input.addEventListener('change', syncScopesFromEndpointSelection);
    });

    if (status) {
      status.textContent = `${grantable.length} grantable endpoint(s) from ${accessCatalog.length} registered route/method entries.`;
    }
    syncScopesFromEndpointSelection();
  }

  function renderPreview() {
    const target = document.getElementById('admin-api-key-access-preview');
    if (!target) return;
    const profile = selectedProfile();
    const mode = provisioningMode();
    const scopeValues = scopes();
    const profileScopes = Array.isArray(profile?.allowed_scopes) ? profile.allowed_scopes : [];
    const endpointRows = selectedEndpointRows();
    const productionAllowed = profile ? Boolean(profile.production_allowed) : false;

    target.innerHTML = `
      <div class="sec-hdr" style="margin-top:var(--s-3)">
        <div class="sh-title">Access Preview</div>
        <div class="sh-sub">endpoint → scope → key/grant preview; backend enforcement remains authoritative</div>
      </div>
      <div class="admin-api-key-metadata-card-grid">
        <div class="admin-api-key-metadata-card-row"><strong>mode</strong><span>${escapeHtml(mode)}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>category</strong><span>${escapeHtml(value('admin-api-key-category'))}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>role</strong><span>${escapeHtml(value('admin-api-key-role'))}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>client_id</strong><span>${escapeHtml(value('admin-api-key-client-id'))}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>issued_to</strong><span>${escapeHtml(value('admin-api-key-issued-to'))}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>operational_profile</strong><span>${escapeHtml(profile?.profile_id || 'none')}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>endpoints</strong><span>${endpointRows.length}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>quota</strong><span>${escapeHtml(value('admin-api-key-quota-limit-override') || 'backend default')}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>expires_at</strong><span>${escapeHtml(value('admin-api-key-expires-at') || 'backend default')}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>production</strong><span>${productionAllowed ? 'allowed' : 'disabled'}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>runtime_connector</strong><span>${profile?.runtime_connector_approved ? 'approved' : 'not approved'}</span></div>
      </div>
      <div style="margin-top:var(--s-2)"><strong>Selected endpoints</strong><div class="mono-block" style="white-space:pre-wrap">${escapeHtml(endpointRows.map((endpoint) => `${endpoint.method} ${endpoint.path}`).join('\n') || 'none')}</div></div>
      <div style="margin-top:var(--s-2)"><strong>Key scopes currently configured</strong><div class="mono-block" style="white-space:pre-wrap">${escapeHtml(scopeValues.join('\n') || 'none')}</div></div>
      <div style="margin-top:var(--s-2)"><strong>Selected operational intent</strong><div class="mono-block" style="white-space:pre-wrap">${escapeHtml(profileScopes.join('\n') || 'none')}</div></div>
      ${mode === 'external_evaluation' ? '<div class="admin-note" style="margin-top:var(--s-2)">Evaluation task binding and grant issuance stay under /settings/admin/evaluation-grants. Selected endpoint scopes are passed explicitly to the grant request.</div>' : ''}
    `;
  }

  async function loadOperationalProfiles() {
    const select = document.getElementById('admin-api-key-operational-profile');
    const status = document.getElementById('admin-api-key-operational-profile-status');
    if (!select) return;

    try {
      const payload = await requestJson(PROFILE_ENDPOINT);
      operationalProfiles = Array.isArray(payload.profiles) ? payload.profiles : [];
      select.innerHTML = '<option value="">Select operational profile</option>' + operationalProfiles
        .map((profile) => `<option value="${escapeHtml(profile.profile_id)}">${escapeHtml(profile.display_name || profile.profile_id)}</option>`)
        .join('');
      select.disabled = false;
      if (status) {
        status.textContent = `${operationalProfiles.length} backend-governed operational profiles available.`;
      }
      renderProfileDetails();
      renderPreview();
    } catch (error) {
      select.innerHTML = '<option value="">Operational profiles unavailable</option>';
      select.disabled = true;
      if (status) {
        status.className = 'admin-note danger';
        status.textContent = `Unable to load operational profiles: ${error.message || error}`;
      }
    }
  }

  async function loadAccessCatalog() {
    const status = document.getElementById('admin-api-key-access-catalog-status');
    try {
      const payload = await requestJson(ACCESS_CATALOG_ENDPOINT);
      accessCatalog = Array.isArray(payload.endpoints) ? payload.endpoints : [];
      renderAccessCatalog();
    } catch (error) {
      accessCatalog = [];
      renderAccessCatalog();
      if (status) {
        status.className = 'admin-note danger';
        status.textContent = `Unable to load backend access catalog: ${error.message || error}`;
      }
    }
  }

  function fixLocalUsageExamples(card) {
    card.querySelectorAll('.mono-block').forEach((block) => {
      const current = block.textContent || '';
      if (current.includes('127.0.0.1:8000')) {
        block.textContent = current.replaceAll('127.0.0.1:8000', '127.0.0.1:18080');
      }
    });
  }

  function bindPreviewUpdates(card) {
    card.querySelectorAll('input, textarea, select').forEach((control) => {
      if (control.dataset.apiKeyWorkspaceBound === 'true') return;
      control.dataset.apiKeyWorkspaceBound = 'true';
      control.addEventListener('input', renderPreview);
      control.addEventListener('change', renderPreview);
    });
  }

  function initializeWorkspace() {
    const card = document.getElementById(CARD_ID);
    if (!card) {
      initAttempts += 1;
      if (initAttempts < MAX_INIT_ATTEMPTS) {
        window.setTimeout(initializeWorkspace, INIT_RETRY_MS);
      }
      return;
    }
    if (document.getElementById(WORKSPACE_ID)) return;

    const workspace = document.createElement('section');
    workspace.id = WORKSPACE_ID;
    workspace.className = 'card flat';
    workspace.style.marginTop = 'var(--s-4)';
    workspace.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">Provisioning Workspace</div>
        <div class="sh-sub">key mode, operational intent, endpoints, scopes, and safe access preview</div>
      </div>
      <div class="admin-grid">
        <label>Provisioning mode
          <select id="admin-api-key-provisioning-mode">
            <option value="standard">Standard / Integration Key</option>
            <option value="external_evaluation">External Evaluation</option>
          </select>
        </label>
        <label>Operational profile
          <select id="admin-api-key-operational-profile" disabled>
            <option value="">Loading backend catalog...</option>
          </select>
        </label>
      </div>
      <div id="admin-api-key-provisioning-mode-status" class="admin-note"></div>
      <div id="admin-api-key-operational-profile-status" class="muted" style="margin-top:var(--s-2)"></div>
      <div id="admin-api-key-operational-profile-details"></div>
      <div class="sec-hdr" style="margin-top:var(--s-3)">
        <div class="sh-title">Eligible API Endpoints</div>
        <div class="sh-sub">registered backend routes with an explicit API-key grant policy</div>
      </div>
      <div id="admin-api-key-access-catalog-status" class="muted"></div>
      <div id="admin-api-key-grantable-endpoints"></div>
      <div id="admin-api-key-access-selection-status" class="admin-note" style="margin-top:var(--s-2)"></div>
      <div class="sec-hdr" style="margin-top:var(--s-3)">
        <div class="sh-title">Backend Route Inventory</div>
        <div class="sh-sub">full registered route visibility; locked routes are not grantable from this workspace</div>
      </div>
      <div id="admin-api-key-all-endpoints"></div>
      <div id="admin-api-key-access-preview"></div>
    `;

    const formGrid = card.querySelector('.admin-grid');
    if (formGrid) formGrid.before(workspace);
    else card.prepend(workspace);

    document.getElementById('admin-api-key-provisioning-mode')?.addEventListener('change', () => {
      updateGenerateGate();
      renderPreview();
    });
    document.getElementById('admin-api-key-operational-profile')?.addEventListener('change', () => {
      renderProfileDetails();
      renderPreview();
    });

    fixLocalUsageExamples(card);
    bindPreviewUpdates(card);
    updateGenerateGate();
    renderPreview();
    loadOperationalProfiles();
    loadAccessCatalog();
    document.body.dataset.adminApiKeyProvisioningWorkspace = 'loaded';
  }

  window.PMK_ADMIN_API_KEY_PROVISIONING_WORKSPACE = {
    initialize: initializeWorkspace,
    renderPreview,
    selectedScopes: selectedEndpointScopes,
    selectedEndpoints,
  };

  initializeWorkspace();
})();
