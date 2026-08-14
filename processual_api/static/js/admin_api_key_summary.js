(function () {
  const API_KEYS_ENDPOINT = '/settings/api-keys';
  const SUPERVISOR_KEYS_ENDPOINT = '/settings/admin/supervisor-session-keys';
  const HOST_ID = 'admin-api-key-lifecycle-summary';

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
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') {
      return auth.headers(extra);
    }

    return new Headers(extra);
  }

  async function requestJson(path) {
    const response = await fetch(path, {
      method: 'GET',
      credentials: 'include',
      headers: authHeaders({ Accept: 'application/json' }),
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
      throw new Error(detail);
    }

    return data;
  }

  function extractList(payload, keys) {
    if (Array.isArray(payload)) return payload;
    if (!payload || typeof payload !== 'object') return [];

    for (const key of keys) {
      if (Array.isArray(payload[key])) return payload[key];
    }

    if (payload.data && Array.isArray(payload.data)) return payload.data;

    for (const key of keys) {
      if (payload.data && Array.isArray(payload.data[key])) {
        return payload.data[key];
      }
    }

    return [];
  }

  function isRevoked(item) {
    const status = text(item.status || item.lifecycle_status).toLowerCase();
    return Boolean(item.revoked || item.revoked_at || status === 'revoked');
  }

  function isExpired(item) {
    const status = text(item.status || item.lifecycle_status).toLowerCase();
    if (item.expired || status === 'expired') return true;

    const expiresAt = text(item.expires_at || item.expiry || item.expires);
    if (!expiresAt) return false;

    const parsed = Date.parse(expiresAt);
    return Number.isFinite(parsed) && parsed < Date.now();
  }

  function summarizeKeys(items) {
    const summary = {
      total: 0,
      active: 0,
      revoked: 0,
      expired: 0,
    };

    items.forEach((item) => {
      summary.total += 1;

      if (isRevoked(item)) {
        summary.revoked += 1;
      } else if (isExpired(item)) {
        summary.expired += 1;
      } else {
        summary.active += 1;
      }
    });

    return summary;
  }

  function statTile(label, value) {
    return `
      <div class="card flat">
        <div class="muted" style="font-size:10px">${escapeHtml(label)}</div>
        <div class="font-data" style="font-size:18px">${escapeHtml(value)}</div>
      </div>
    `;
  }

  function ensureHost() {
    let host = document.getElementById(HOST_ID);
    if (host) return host;

    const page = document.getElementById('page-admin-api-keys');
    if (!page) return null;

    const card = document.createElement('div');
    card.className = 'card';
    card.id = HOST_ID;
    card.style.marginTop = 'var(--s-5)';
    card.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">API Key Lifecycle Summary</div>
        <div class="sh-sub">standard API keys and supervisor session keys - visibility only</div>
      </div>
      <div class="mono-block" style="font-size:11px;white-space:pre-wrap">Loading API key lifecycle summary...</div>
    `;

    const target = page.firstElementChild || page;
    target.appendChild(card);
    return card;
  }

  function renderSummary(apiSummary, supervisorSummary) {
    const host = ensureHost();
    if (!host) return;

    host.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">API Key Lifecycle Summary</div>
        <div class="sh-sub">standard API keys and supervisor session keys - visibility only</div>
      </div>
      <div class="grid-3">
        ${statTile('standard API keys total', apiSummary.total)}
        ${statTile('standard active', apiSummary.active)}
        ${statTile('standard revoked', apiSummary.revoked)}
        ${statTile('standard expired', apiSummary.expired)}
        ${statTile('supervisor session keys total', supervisorSummary.total)}
        ${statTile('supervisor active', supervisorSummary.active)}
        ${statTile('supervisor revoked', supervisorSummary.revoked)}
        ${statTile('supervisor expired', supervisorSummary.expired)}
      </div>
      <div class="muted" style="margin-top:var(--s-3)">
        Backend enforcement remains authoritative. Do not display raw supervisor session keys.
      </div>
    `;
  }

  function renderError(error) {
    const host = ensureHost();
    if (!host) return;

    host.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">API Key Lifecycle Summary</div>
        <div class="sh-sub">standard API keys and supervisor session keys - visibility only</div>
      </div>
      <div class="admin-note danger">Unable to load API key lifecycle summary: ${escapeHtml(
        error.message || error
      )}</div>
      <div class="muted">Backend enforcement remains authoritative.</div>
    `;
  }

  async function refreshApiKeyLifecycleSummary() {
    const host = ensureHost();
    if (!host) return;

    try {
      const apiPayload = await requestJson(API_KEYS_ENDPOINT);
      const supervisorPayload = await requestJson(SUPERVISOR_KEYS_ENDPOINT);

      const apiKeys = extractList(apiPayload, ['api_keys', 'keys', 'items', 'results']);
      const supervisorKeys = extractList(supervisorPayload, [
        'supervisor_session_keys',
        'keys',
        'items',
        'results',
      ]);

      renderSummary(summarizeKeys(apiKeys), summarizeKeys(supervisorKeys));
    } catch (error) {
      renderError(error);
    }
  }

  refreshApiKeyLifecycleSummary();

  window.addEventListener('pmk-supervisor-session-key-updated', () => {
    refreshApiKeyLifecycleSummary();
  });
  window.addEventListener('pmk-evaluation-grant-updated', () => {
    refreshApiKeyLifecycleSummary();
  });
})();

(function () {
  const CATEGORY_ID = 'admin-api-key-category';
  const LIFECYCLE_CARD_ID = 'admin-api-key-lifecycle-card';
  const EVALUATION_CARD_ID = 'admin-api-key-external-evaluation-card';
  const EVALUATION_BODY_ID = 'admin-api-key-external-evaluation-body';
  const EVALUATION_ACTIVATE_ID = 'admin-api-key-external-evaluation-activate';
  const EVALUATION_HOST_ID = 'admin-evaluation-grants';
  const CATEGORY_AUTHORITY_ID = 'admin-api-key-category-authority';
  const CONTRACT_ID = 'admin-external-evaluation-plan-contract';
  const EXTERNAL_CATEGORY = 'external_evaluation';
  const MAX_RECONCILE_ATTEMPTS = 40;
  const RECONCILE_DELAY_MS = 100;
  let reconcileAttempts = 0;

  function categorySelect() {
    return document.getElementById(CATEGORY_ID);
  }

  function externalSelected() {
    return categorySelect()?.value === EXTERNAL_CATEGORY;
  }

  function ensureExternalCategoryOption() {
    const select = categorySelect();
    if (!select) return false;
    if (!select.querySelector(`option[value="${EXTERNAL_CATEGORY}"]`)) {
      const option = document.createElement('option');
      option.value = EXTERNAL_CATEGORY;
      option.textContent = 'External Evaluation Access - governed sandbox evaluation';
      select.appendChild(option);
    }
    return true;
  }

  function ensureCategoryAuthorityBar() {
    const select = categorySelect();
    const lifecycle = document.getElementById(LIFECYCLE_CARD_ID);
    if (!select || !lifecycle) return null;

    let bar = document.getElementById(CATEGORY_AUTHORITY_ID);
    if (!bar) {
      bar = document.createElement('section');
      bar.id = CATEGORY_AUTHORITY_ID;
      bar.className = 'card flat';
      bar.style.marginTop = 'var(--s-4)';
      bar.innerHTML = `
        <div class="sec-hdr">
          <div class="sh-title">API Key Category</div>
          <div class="sh-sub">single lifecycle authority - selecting a category changes the active preparation flow</div>
        </div>
        <div data-api-key-category-slot></div>
        <div class="muted" style="margin-top:var(--s-2)">
          External Evaluation uses the evaluation-grant authority and can never fall through to standard key generation.
        </div>
      `;
      const firstGrid = [...lifecycle.children].find((child) => child.classList?.contains('admin-grid'));
      if (firstGrid) lifecycle.insertBefore(bar, firstGrid);
      else lifecycle.prepend(bar);
    }

    const label = select.closest('label');
    const slot = bar.querySelector('[data-api-key-category-slot]');
    if (label && slot && label.parentElement !== slot) {
      slot.appendChild(label);
    }
    return bar;
  }

  function standardSurfaces() {
    const lifecycle = document.getElementById(LIFECYCLE_CARD_ID);
    if (!lifecycle) return [];
    const category = categorySelect();
    const categoryBar = document.getElementById(CATEGORY_AUTHORITY_ID);
    const evaluationCard = document.getElementById(EVALUATION_CARD_ID);
    const supervisorPanel = document.getElementById('admin-supervisor-session-key-panel');
    const nodes = [];
    [...lifecycle.children].forEach((child) => {
      if (child === categoryBar || child === evaluationCard || child === supervisorPanel) return;
      if (category && child.contains(category)) return;
      if (child.id === 'admin-api-key-provisioning-workspace') return;
      nodes.push(child);
    });
    return nodes;
  }

  function setStandardVisibility(visible) {
    standardSurfaces().forEach((node) => {
      if (node.dataset.externalEvaluationPreviousHidden === undefined) {
        node.dataset.externalEvaluationPreviousHidden = node.hidden ? 'true' : 'false';
      }
      node.hidden = visible
        ? node.dataset.externalEvaluationPreviousHidden === 'true'
        : true;
    });
  }

  function ensureContract(body) {
    if (!body) return null;
    let contract = document.getElementById(CONTRACT_ID);
    if (!contract) {
      contract = document.createElement('section');
      contract.id = CONTRACT_ID;
      contract.className = 'card flat';
      contract.style.marginBottom = 'var(--s-3)';
      const host = document.getElementById(EVALUATION_HOST_ID);
      body.insertBefore(contract, host || body.firstChild);
    }
    return contract;
  }

  function selectedEndpointCount() {
    return document.querySelectorAll('[data-api-key-access-endpoint]:checked').length;
  }

  function selectedScopeCount() {
    const workspace = window.PMK_ADMIN_API_KEY_PROVISIONING_WORKSPACE;
    if (!workspace || typeof workspace.selectedScopes !== 'function') return 0;
    const scopes = workspace.selectedScopes();
    return Array.isArray(scopes) ? scopes.length : 0;
  }

  function selectedTaskCount() {
    return document.querySelectorAll('[data-eval-task]:checked').length;
  }

  function fieldReady(id, minLength = 1) {
    return String(document.getElementById(id)?.value || '').trim().length >= minLength;
  }

  function renderContract() {
    const body = document.getElementById(EVALUATION_BODY_ID);
    const contract = ensureContract(body);
    if (!contract) return;
    const checks = [
      ['Category', externalSelected(), 'External Evaluation Access selected'],
      ['Administrator', document.body.dataset.adminSession === 'ok', 'verified administrator session'],
      ['Provisioning', Boolean(document.getElementById('admin-api-key-provisioning-workspace')), 'provisioning workspace loaded'],
      ['Operational profile', fieldReady('admin-api-key-operational-profile'), 'backend-governed profile selected'],
      ['Eligible endpoints', selectedEndpointCount() > 0, 'at least one grantable endpoint selected'],
      ['Derived scopes', selectedScopeCount() > 0, 'endpoint selection produced non-admin runtime scopes'],
      ['Canonical tasks', selectedTaskCount() > 0, 'at least one canonical evaluation task selected'],
      ['Identity', fieldReady('admin-eval-client-id') && fieldReady('admin-eval-issued-to'), 'client and issued-to completed'],
      ['Purpose', fieldReady('admin-eval-purpose', 10), 'descriptive purpose completed'],
    ];
    const complete = checks.every(([, ok]) => ok);
    contract.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">External Evaluation Readiness Contract</div>
        <div class="sh-sub">grant creation is blocked until every planned lifecycle gate is satisfied</div>
      </div>
      <div class="admin-api-key-metadata-card-grid">
        ${checks.map(([label, ok, detail]) => `
          <div class="admin-api-key-metadata-card-row">
            <strong>${ok ? 'READY' : 'LOCKED'} · ${label}</strong>
            <span>${detail}</span>
          </div>
        `).join('')}
      </div>
      <div class="admin-note ${complete ? 'ok' : ''}" style="margin-top:var(--s-2)">
        ${complete
          ? 'Plan contract complete. Evaluation grant creation may proceed; backend validation remains authoritative.'
          : 'Plan contract incomplete. Create Evaluation Grant must remain disabled until all gates are READY.'}
      </div>
    `;
  }

  function prepareEvaluationCard() {
    const card = document.getElementById(EVALUATION_CARD_ID);
    const body = document.getElementById(EVALUATION_BODY_ID);
    const button = document.getElementById(EVALUATION_ACTIVATE_ID);
    if (!card || !body) return false;
    card.classList.remove('admin-api-key-lifecycle-option-card');
    card.dataset.categoryOwned = 'true';
    if (button) button.hidden = true;
    const title = card.querySelector('.sh-title');
    const subtitle = card.querySelector('.sh-sub');
    const note = card.querySelector('.admin-note');
    if (title) title.textContent = 'External Evaluation Lifecycle';
    if (subtitle) subtitle.textContent = 'verify → provision → bind tasks → create grant → issue once → test → revoke';
    if (note) {
      note.textContent =
        'This lifecycle is selected from Category. Standard key generation is disabled while External Evaluation is active. Production access remains disabled.';
    }
    ensureContract(body);
    return true;
  }

  function setMode(value) {
    const mode = document.getElementById('admin-api-key-provisioning-mode');
    if (!mode || mode.value === value) return;
    mode.value = value;
    mode.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function applyCategoryState() {
    const card = document.getElementById(EVALUATION_CARD_ID);
    const body = document.getElementById(EVALUATION_BODY_ID);
    const hiddenActivate = document.getElementById(EVALUATION_ACTIVATE_ID);
    if (!card || !body) return false;

    const external = externalSelected();
    card.hidden = !external;
    body.hidden = !external;
    card.dataset.activated = external ? 'true' : 'false';
    setStandardVisibility(!external);

    if (external) {
      setMode('external_evaluation');
      if (hiddenActivate && !hiddenActivate.disabled) hiddenActivate.click();
    } else {
      setMode('standard');
    }

    renderContract();
    try {
      window.dispatchEvent(
        new CustomEvent('pmk-api-key-category-changed', {
          detail: { category: categorySelect()?.value || '' },
        })
      );
    } catch {
      window.dispatchEvent(new Event('pmk-api-key-category-changed'));
    }
    return true;
  }

  function bindCategory() {
    const select = categorySelect();
    if (!select) return false;
    if (select.dataset.externalEvaluationCategoryBound !== 'true') {
      select.dataset.externalEvaluationCategoryBound = 'true';
      select.addEventListener('change', applyCategoryState);
    }
    return true;
  }

  function reconcile() {
    const ready =
      ensureExternalCategoryOption() &&
      Boolean(ensureCategoryAuthorityBar()) &&
      prepareEvaluationCard() &&
      bindCategory();
    if (!ready) {
      reconcileAttempts += 1;
      if (reconcileAttempts < MAX_RECONCILE_ATTEMPTS) {
        window.setTimeout(reconcile, RECONCILE_DELAY_MS);
      }
      return;
    }
    reconcileAttempts = 0;
    applyCategoryState();
  }

  window.PMK_ADMIN_EXTERNAL_EVALUATION_CATEGORY_FLOW = {
    reconcile,
    renderContract,
    selected: externalSelected,
  };

  window.addEventListener('pmk-admin-session-verified', () => {
    window.setTimeout(reconcile, 0);
  });
  window.addEventListener('pmk-api-key-access-selection-changed', renderContract);
  window.addEventListener('pmk-evaluation-selection-changed', renderContract);
  window.addEventListener('pmk-evaluation-grant-updated', renderContract);
  document.addEventListener('input', (event) => {
    if (event.target.closest(`#${LIFECYCLE_CARD_ID}`)) renderContract();
  });
  document.addEventListener('change', (event) => {
    if (event.target.closest(`#${LIFECYCLE_CARD_ID}`)) renderContract();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', reconcile);
  } else {
    reconcile();
  }
})();