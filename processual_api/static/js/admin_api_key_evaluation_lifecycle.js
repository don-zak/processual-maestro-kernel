(function () {
  const CARD_ID = 'admin-api-key-lifecycle-card';
  const WORKSPACE_ID = 'admin-api-key-provisioning-workspace';
  const EVALUATION_HOST_ID = 'admin-evaluation-grants';
  const EVALUATION_SLOT_ID = 'admin-api-key-evaluation-lifecycle-slot';
  const MODE_ID = 'admin-api-key-provisioning-mode';
  const PREVIEW_ID = 'admin-api-key-evaluation-preview';
  const MAX_ATTACH_ATTEMPTS = 30;
  const ATTACH_RETRY_MS = 100;

  let attachAttempts = 0;

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

  function value(id, fallback = '') {
    return text(document.getElementById(id)?.value || fallback);
  }

  function mode() {
    return value(MODE_ID, 'standard');
  }

  function selectedTasks() {
    return [...document.querySelectorAll('[data-eval-task]:checked')]
      .map((input) => text(input.value))
      .filter(Boolean);
  }

  function directStandardGrid(card) {
    return [...card.children].find((child) => child.classList?.contains('admin-grid')) || null;
  }

  function standardScopesLabel() {
    return document.getElementById('admin-api-key-scopes')?.closest('label') || null;
  }

  function standardActions() {
    return document.getElementById('admin-api-key-generate-btn')?.closest('.admin-actions') || null;
  }

  function ensureSlot() {
    const workspace = document.getElementById(WORKSPACE_ID);
    if (!workspace) return null;
    let slot = document.getElementById(EVALUATION_SLOT_ID);
    if (slot) return slot;

    slot = document.createElement('section');
    slot.id = EVALUATION_SLOT_ID;
    slot.className = 'card flat';
    slot.style.marginTop = 'var(--s-4)';
    slot.hidden = true;
    slot.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">External Evaluation Lifecycle</div>
        <div class="sh-sub">canonical tasks, grant creation, one-time key issue, and revocation</div>
      </div>
      <div class="admin-note">
        This area reuses the existing evaluation grant authority. Standard /settings/api-keys generation remains disabled in External Evaluation mode.
      </div>
      <div id="${PREVIEW_ID}" style="margin-top:var(--s-3)"></div>
      <div data-admin-evaluation-host-slot style="margin-top:var(--s-3)"></div>
    `;
    workspace.appendChild(slot);
    return slot;
  }

  function renderEvaluationPreview() {
    const target = document.getElementById(PREVIEW_ID);
    if (!target) return;
    const tasks = selectedTasks();
    const clientId = value('admin-eval-client-id', 'not set');
    const issuedTo = value('admin-eval-issued-to', 'not set');
    const days = value('admin-eval-days', '14');
    const quota = value('admin-eval-max-requests', '100');
    const purpose = value('admin-eval-purpose', 'not set');

    target.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">Evaluation Access Preview</div>
        <div class="sh-sub">safe pre-issue summary - backend validation remains authoritative</div>
      </div>
      <div class="admin-api-key-metadata-card-grid">
        <div class="admin-api-key-metadata-card-row"><strong>client_id</strong><span>${escapeHtml(clientId)}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>issued_to</strong><span>${escapeHtml(issuedTo)}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>duration_days</strong><span>${escapeHtml(days)}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>quota</strong><span>${escapeHtml(quota)}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>subscription</strong><span>not required</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>production</strong><span>disabled</span></div>
      </div>
      <div style="margin-top:var(--s-2)"><strong>Purpose</strong><div>${escapeHtml(purpose)}</div></div>
      <div style="margin-top:var(--s-2)"><strong>Bound canonical tasks (${tasks.length})</strong><div class="mono-block" style="white-space:pre-wrap">${escapeHtml(tasks.join('\n') || 'none selected')}</div></div>
    `;
  }

  function updateModeVisibility() {
    const card = document.getElementById(CARD_ID);
    const slot = ensureSlot();
    if (!card || !slot) return;
    const evaluationMode = mode() === 'external_evaluation';

    slot.hidden = !evaluationMode;
    const standardGrid = directStandardGrid(card);
    const scopesLabel = standardScopesLabel();
    const actions = standardActions();
    if (standardGrid) standardGrid.hidden = evaluationMode;
    if (scopesLabel) scopesLabel.hidden = evaluationMode;
    if (actions) actions.hidden = evaluationMode;

    const status = document.getElementById('admin-api-key-provisioning-mode-status');
    if (status && evaluationMode) {
      status.className = 'admin-note ok';
      status.textContent =
        'External Evaluation mode is active. Grant creation, task binding, one-time key issue, and revoke are embedded below under the evaluation grant authority.';
    }
    renderEvaluationPreview();
  }

  function bindEvaluationChanges(host) {
    if (host.dataset.apiKeyEvaluationLifecycleBound === 'true') return;
    host.dataset.apiKeyEvaluationLifecycleBound = 'true';
    host.addEventListener('input', renderEvaluationPreview);
    host.addEventListener('change', renderEvaluationPreview);
  }

  function attachEvaluationHost() {
    const slot = ensureSlot();
    const host = document.getElementById(EVALUATION_HOST_ID);
    if (!slot || !host) {
      attachAttempts += 1;
      if (attachAttempts < MAX_ATTACH_ATTEMPTS) {
        window.setTimeout(attachEvaluationHost, ATTACH_RETRY_MS);
      } else {
        document.body.dataset.adminApiKeyEvaluationLifecycle = 'attach-timeout';
      }
      return;
    }

    const hostSlot = slot.querySelector('[data-admin-evaluation-host-slot]');
    if (hostSlot && host.parentElement !== hostSlot) {
      hostSlot.appendChild(host);
    }
    host.classList.add('flat');
    host.style.marginTop = '0';
    host.dataset.lifecycleEmbedded = 'true';
    bindEvaluationChanges(host);
    updateModeVisibility();
    document.body.dataset.adminApiKeyEvaluationLifecycle = 'loaded';
  }

  function initialize() {
    const workspace = document.getElementById(WORKSPACE_ID);
    const modeSelect = document.getElementById(MODE_ID);
    if (!workspace || !modeSelect) {
      attachAttempts += 1;
      if (attachAttempts < MAX_ATTACH_ATTEMPTS) {
        window.setTimeout(initialize, ATTACH_RETRY_MS);
      }
      return;
    }

    ensureSlot();
    if (modeSelect.dataset.evaluationLifecycleBound !== 'true') {
      modeSelect.dataset.evaluationLifecycleBound = 'true';
      modeSelect.addEventListener('change', updateModeVisibility);
    }
    window.addEventListener('pmk-evaluation-selection-changed', renderEvaluationPreview);
    window.addEventListener('pmk-evaluation-grant-updated', renderEvaluationPreview);
    updateModeVisibility();
    attachEvaluationHost();
  }

  window.PMK_ADMIN_API_KEY_EVALUATION_LIFECYCLE = {
    initialize,
    attachEvaluationHost,
    renderEvaluationPreview,
  };

  initialize();
})();
