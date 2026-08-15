(function () {
  const WORKSPACE_ID = 'admin-api-key-external-provisioning-slot';
  const PROFILE_ENDPOINT = '/settings/admin/api-key-operational-profiles';
  const ACCESS_CATALOG_ENDPOINT = '/settings/admin/api-key-access-catalog';
  const MAX_INIT_ATTEMPTS = 30;
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

  function selectedProfile() {
    const profileId = value('admin-api-key-operational-profile');
    return operationalProfiles.find((profile) => profile.profile_id === profileId) || null;
  }

  function selectedEndpointRows() {
    const selectedKeys = new Set(
      [...document.querySelectorAll('[data-api-key-access-endpoint]:checked')]
        .map((input) => text(input.value))
        .filter(Boolean)
    );
    return accessCatalog.filter((endpoint) => selectedKeys.has(`${endpoint.method} ${endpoint.path}`));
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

  function dispatchSelectionChanged() {
    try {
      window.dispatchEvent(new CustomEvent('pmk-api-key-access-selection-changed'));
    } catch {
      window.dispatchEvent(new Event('pmk-api-key-access-selection-changed'));
    }
  }

  function syncScopesFromEndpointSelection() {
    const derivedScopes = selectedEndpointScopes();
    const status = document.getElementById('admin-api-key-access-selection-status');
    const scopePreview = document.getElementById('admin-api-key-derived-scopes');
    const endpointCount = selectedEndpointRows().length;

    if (status) {
      status.textContent = endpointCount
        ? `${endpointCount} endpoint(s) selected · ${derivedScopes.length} derived runtime scope(s).`
        : 'No endpoint selected. Select explicit grantable endpoints to derive runtime scopes.';
    }
    if (scopePreview) {
      scopePreview.textContent = derivedScopes.join('\n') || 'none';
    }
    renderPreview();
    dispatchSelectionChanged();
  }

  function renderProfileDetails() {
    const target = document.getElementById('admin-api-key-operational-profile-details');
    if (!target) return;
    const profile = selectedProfile();
    if (!profile) {
      target.innerHTML = '<div class="muted">Select an operational profile to inspect governed operational intent.</div>';
      return;
    }

    const allowed = Array.isArray(profile.allowed_scopes) ? profile.allowed_scopes : [];
    const forbidden = Array.isArray(profile.forbidden_scopes) ? profile.forbidden_scopes : [];
    target.innerHTML = `
      <div class="admin-note" style="margin-top:var(--s-2)">
        Selected operational intent only. Choosing a profile does not mutate runtime scopes; endpoint selection remains the scope authority.
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
    const endpointRows = selectedEndpointRows();
    const derivedScopes = selectedEndpointScopes();
    target.innerHTML = `
      <div class="sec-hdr" style="margin-top:var(--s-3)">
        <div class="sh-title">Access Preview</div>
        <div class="sh-sub">endpoint → derived scope → evaluation grant; backend enforcement remains authoritative</div>
      </div>
      <div class="admin-api-key-metadata-card-grid">
        <div class="admin-api-key-metadata-card-row"><strong>category</strong><span>external_evaluation</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>operational_profile</strong><span>${escapeHtml(profile?.profile_id || 'none')}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>endpoints</strong><span>${endpointRows.length}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>derived_scopes</strong><span>${derivedScopes.length}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>production</strong><span>disabled</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>runtime_connector</strong><span>${profile?.runtime_connector_approved ? 'approved' : 'not approved'}</span></div>
      </div>
      <div style="margin-top:var(--s-2)"><strong>Selected endpoints</strong><div class="mono-block" style="white-space:pre-wrap">${escapeHtml(endpointRows.map((endpoint) => `${endpoint.method} ${endpoint.path}`).join('\n') || 'none')}</div></div>
      <div style="margin-top:var(--s-2)"><strong>Derived runtime scopes</strong><div class="mono-block" style="white-space:pre-wrap">${escapeHtml(derivedScopes.join('\n') || 'none')}</div></div>
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
      if (status) status.textContent = `${operationalProfiles.length} backend-governed operational profiles available.`;
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

  function initializeWorkspace() {
    const workspace = document.getElementById(WORKSPACE_ID);
    if (!workspace) {
      initAttempts += 1;
      if (initAttempts < MAX_INIT_ATTEMPTS) {
        window.setTimeout(initializeWorkspace, INIT_RETRY_MS);
      }
      return;
    }

    if (workspace.dataset.workspaceInitialized === 'true') return;
    workspace.dataset.workspaceInitialized = 'true';
    workspace.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">Operational Profile</div>
        <div class="sh-sub">intent only; it never grants scopes by itself</div>
      </div>
      <label>Operational profile
        <select id="admin-api-key-operational-profile" disabled>
          <option value="">Loading backend catalog...</option>
        </select>
      </label>
      <div id="admin-api-key-operational-profile-status" class="muted" style="margin-top:var(--s-2)"></div>
      <div id="admin-api-key-operational-profile-details"></div>

      <div class="sec-hdr" style="margin-top:var(--s-3)">
        <div class="sh-title">Eligible Endpoints</div>
        <div class="sh-sub">only routes explicitly declared grantable by backend policy</div>
      </div>
      <div id="admin-api-key-access-catalog-status" class="muted"></div>
      <div id="admin-api-key-grantable-endpoints"></div>
      <div id="admin-api-key-access-selection-status" class="admin-note" style="margin-top:var(--s-2)"></div>

      <div class="sec-hdr" style="margin-top:var(--s-3)">
        <div class="sh-title">Derived Runtime Scopes</div>
        <div class="sh-sub">computed only from selected eligible endpoints</div>
      </div>
      <div id="admin-api-key-derived-scopes" class="mono-block" style="white-space:pre-wrap">none</div>

      <div class="sec-hdr" style="margin-top:var(--s-3)">
        <div class="sh-title">Backend Route Inventory</div>
        <div class="sh-sub">registered route visibility does not imply grantability</div>
      </div>
      <div id="admin-api-key-all-endpoints"></div>
      <div id="admin-api-key-access-preview"></div>
    `;

    document.getElementById('admin-api-key-operational-profile')?.addEventListener('change', () => {
      renderProfileDetails();
      renderPreview();
      dispatchSelectionChanged();
    });

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
