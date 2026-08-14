(function () {
  const CARD_ID = 'admin-api-key-lifecycle-card';
  const WORKSPACE_ID = 'admin-api-key-provisioning-workspace';
  const PROFILE_ENDPOINT = '/settings/admin/api-key-operational-profiles';
  const MAX_INIT_ATTEMPTS = 20;
  const INIT_RETRY_MS = 100;

  let operationalProfiles = [];
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
          'External Evaluation mode is preview-only in this phase. Standard key generation is disabled so the evaluation grant authority cannot be bypassed.';
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
        'Standard / Integration mode uses the existing governed /settings/api-keys lifecycle.';
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
      <div class="grid-3" style="margin-top:var(--s-2)">
        <div class="card flat"><strong>Environment</strong><div>${escapeHtml(profile.environment || 'sandbox')}</div></div>
        <div class="card flat"><strong>Read only</strong><div>${profile.read_only ? 'yes' : 'no'}</div></div>
        <div class="card flat"><strong>Write allowed</strong><div>${profile.write_allowed ? 'yes' : 'no'}</div></div>
        <div class="card flat"><strong>Production</strong><div>${profile.production_allowed ? 'allowed' : 'disabled'}</div></div>
        <div class="card flat"><strong>Supervisor for write</strong><div>${profile.requires_supervisor_for_write ? 'required' : 'not required'}</div></div>
        <div class="card flat"><strong>Runtime connector</strong><div>${profile.runtime_connector_approved ? 'approved' : 'not approved'}</div></div>
      </div>
      <div style="margin-top:var(--s-2)"><strong>Allowed operational scopes</strong><div class="mono-block" style="white-space:pre-wrap">${escapeHtml(allowed.join('\n') || 'none')}</div></div>
      <div style="margin-top:var(--s-2)"><strong>Forbidden operational scopes</strong><div class="mono-block" style="white-space:pre-wrap">${escapeHtml(forbidden.join('\n') || 'none')}</div></div>
      <div class="muted" style="margin-top:var(--s-2)">${escapeHtml(profile.next_action || '')}</div>
    `;
  }

  function applySelectedProfileScopes() {
    const profile = selectedProfile();
    const target = document.getElementById('admin-api-key-scopes');
    if (!profile || !target) return;
    const allowed = Array.isArray(profile.allowed_scopes) ? profile.allowed_scopes : [];
    target.value = allowed.join('\n');
    target.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function renderPreview() {
    const target = document.getElementById('admin-api-key-access-preview');
    if (!target) return;
    const profile = selectedProfile();
    const mode = provisioningMode();
    const scopeValues = scopes();
    const productionAllowed = profile ? Boolean(profile.production_allowed) : false;

    target.innerHTML = `
      <div class="sec-hdr" style="margin-top:var(--s-3)">
        <div class="sh-title">Access Preview</div>
        <div class="sh-sub">safe metadata only - backend enforcement remains authoritative</div>
      </div>
      <div class="admin-api-key-metadata-card-grid">
        <div class="admin-api-key-metadata-card-row"><strong>mode</strong><span>${escapeHtml(mode)}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>category</strong><span>${escapeHtml(value('admin-api-key-category'))}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>role</strong><span>${escapeHtml(value('admin-api-key-role'))}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>client_id</strong><span>${escapeHtml(value('admin-api-key-client-id'))}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>issued_to</strong><span>${escapeHtml(value('admin-api-key-issued-to'))}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>operational_profile</strong><span>${escapeHtml(profile?.profile_id || 'none')}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>quota</strong><span>${escapeHtml(value('admin-api-key-quota-limit-override') || 'backend default')}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>expires_at</strong><span>${escapeHtml(value('admin-api-key-expires-at') || 'backend default')}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>production</strong><span>${productionAllowed ? 'allowed' : 'disabled'}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>runtime_connector</strong><span>${profile?.runtime_connector_approved ? 'approved' : 'not approved'}</span></div>
      </div>
      <div style="margin-top:var(--s-2)"><strong>Effective scopes in form</strong><div class="mono-block" style="white-space:pre-wrap">${escapeHtml(scopeValues.join('\n') || 'none')}</div></div>
      ${mode === 'external_evaluation' ? '<div class="admin-note" style="margin-top:var(--s-2)">Evaluation task binding and grant issuance stay under /settings/admin/evaluation-grants. This preview does not issue a key.</div>' : ''}
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
        <div class="sh-sub">key mode, operational profile, and safe access preview</div>
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
      <div class="admin-actions" style="margin-top:var(--s-2)">
        <button id="admin-api-key-apply-profile-scopes" class="btn secondary" type="button">Apply profile scopes to key</button>
      </div>
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
    document.getElementById('admin-api-key-apply-profile-scopes')?.addEventListener('click', () => {
      applySelectedProfileScopes();
      renderPreview();
    });

    fixLocalUsageExamples(card);
    bindPreviewUpdates(card);
    updateGenerateGate();
    renderPreview();
    loadOperationalProfiles();
    document.body.dataset.adminApiKeyProvisioningWorkspace = 'loaded';
  }

  window.PMK_ADMIN_API_KEY_PROVISIONING_WORKSPACE = {
    initialize: initializeWorkspace,
    renderPreview,
  };

  initializeWorkspace();
})();
