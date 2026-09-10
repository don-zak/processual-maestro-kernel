(function () {
  const CARD_ID = 'admin-api-key-lifecycle-card';
  const EXTERNAL_CARD_ID = 'admin-api-key-external-evaluation-card';
  const EXTERNAL_BODY_ID = 'admin-api-key-external-evaluation-body';
  const WORKSPACE_ID = 'admin-api-key-provisioning-workspace';
  const EVALUATION_HOST_ID = 'admin-evaluation-grants';
  const EVALUATION_SLOT_ID = 'admin-api-key-evaluation-lifecycle-slot';
  const MODE_ID = 'admin-api-key-provisioning-mode';
  const PREVIEW_ID = 'admin-api-key-evaluation-preview';
  const KEY_PANEL_ATTRIBUTE = 'data-eval-key-lifecycle-panel';
  const AUDIT_PANEL_ATTRIBUTE = 'data-eval-audit-panel';
  const EVALUATION_GRANTS_ENDPOINT = '/settings/admin/evaluation-grants';
  const MAX_ATTACH_ATTEMPTS = 30;
  const ATTACH_RETRY_MS = 100;

  let attachAttempts = 0;
  let grantObserver = null;

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
    const externalBody = document.getElementById(EXTERNAL_BODY_ID);
    if (!workspace || !externalBody) return null;
    let slot = document.getElementById(EVALUATION_SLOT_ID);
    if (slot) return slot;

    slot = document.createElement('section');
    slot.id = EVALUATION_SLOT_ID;
    slot.className = 'card flat';
    slot.style.marginTop = 'var(--s-4)';
    slot.hidden = true;
    slot.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">Evaluation Access & Key Handoff</div>
        <div class="sh-sub">grant-first CRM/Integration authority, one-time key handoff, customer dashboard, audit evidence, receipt acknowledgement, and revocation</div>
      </div>
      <div class="admin-note">
        External Evaluation is subscription-free. Runtime authority and fixed quota remain grant/PostgreSQL-authoritative. The customer can use <strong>/console/evaluation.html</strong> to view their bounded scope, quota, progress, and safe receipt without Admin access.
      </div>
      <div id="${PREVIEW_ID}" style="margin-top:var(--s-3)"></div>
      <div data-admin-evaluation-host-slot style="margin-top:var(--s-3)"></div>
    `;
    externalBody.appendChild(slot);
    return slot;
  }

  function renderEvaluationPreview() {
    const target = document.getElementById(PREVIEW_ID);
    if (!target) return;
    const tasks = selectedTasks();
    const clientId = value('admin-eval-client-id', 'not set');
    const issuedTo = value('admin-eval-issued-to', 'not set');
    const days = value('admin-eval-days', '14');
    const evaluationType = value('admin-eval-type', 'crm').toLowerCase() === 'integration'
      ? 'integration'
      : 'crm';
    const quota = evaluationType === 'integration' ? 200 : 100;
    const purpose = value('admin-eval-purpose', 'not set');

    target.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">Evaluation Access Preview</div>
        <div class="sh-sub">safe pre-issue grant summary — backend validation remains authoritative</div>
      </div>
      <div class="admin-api-key-metadata-card-grid">
        <div class="admin-api-key-metadata-card-row"><strong>client_id</strong><span>${escapeHtml(clientId)}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>issued_to</strong><span>${escapeHtml(issuedTo)}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>evaluation type</strong><span>${escapeHtml(evaluationType.toUpperCase())}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>duration_days</strong><span>${escapeHtml(days)}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>fixed admitted-execution quota</strong><span>${quota}</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>quota authority</strong><span>derived from grant type; not manually overridable</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>customer portal</strong><span>/console/evaluation.html</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>subscription</strong><span>not required</span></div>
        <div class="admin-api-key-metadata-card-row"><strong>production</strong><span>disabled</span></div>
      </div>
      <div style="margin-top:var(--s-2)"><strong>Purpose</strong><div>${escapeHtml(purpose)}</div></div>
      <div style="margin-top:var(--s-2)"><strong>Bound canonical tasks (${tasks.length})</strong><div class="mono-block" style="white-space:pre-wrap">${escapeHtml(tasks.join('\n') || 'none selected')}</div></div>
    `;
  }

  function keyLifecycleActions(grantId, key) {
    const status = text(key.status).toLowerCase();
    const lifecycle = text(key.lifecycle_status).toLowerCase() || 'issued';
    if (status === 'revoked' || lifecycle === 'revoked') return '';
    const encodedGrant = escapeHtml(grantId);
    const encodedKey = escapeHtml(key.key_id);
    const actions = [];
    if (lifecycle === 'issued') {
      actions.push(`<button class="btn secondary" type="button" data-eval-key-delivered="${encodedKey}" data-eval-key-grant="${encodedGrant}">Confirm Key Sent</button>`);
    }
    if (lifecycle === 'delivery_confirmed') {
      actions.push(`<button class="btn secondary" type="button" data-eval-key-acknowledge="${encodedKey}" data-eval-key-grant="${encodedGrant}">Confirm Receipt</button>`);
    }
    actions.push(`<button class="btn danger" type="button" data-eval-key-revoke="${encodedKey}" data-eval-key-grant="${encodedGrant}">Revoke API Key</button>`);
    return actions.join(' ');
  }

  function renderKeyLifecyclePanel(panel, grantId, keys) {
    if (!keys.length) {
      panel.innerHTML = `
        <div class="sec-hdr"><div class="sh-title">Issued API Keys</div><div class="sh-sub">delivery evidence and individual revocation</div></div>
        <div class="muted">No API keys have been issued for this grant.</div>`;
      return;
    }
    panel.innerHTML = `
      <div class="sec-hdr"><div class="sh-title">Issued API Keys</div><div class="sh-sub">confirm sent → confirm receipt → revoke when necessary</div></div>
      ${keys.map((key) => {
        const lifecycle = text(key.lifecycle_status) || 'issued';
        return `
          <div class="card flat" style="margin-top:var(--s-2)" data-eval-key-id="${escapeHtml(key.key_id)}">
            <div><strong>${escapeHtml(key.prefix || key.key_id)}</strong> · ${escapeHtml(lifecycle)}</div>
            <div class="muted">${escapeHtml(key.key_id)} · status ${escapeHtml(key.status)} · admitted executions used ${escapeHtml(key.usage_count || 0)}</div>
            <div class="muted">sent ${escapeHtml(key.delivered_at || 'not confirmed')} · receipt ${escapeHtml(key.acknowledged_at || 'not confirmed')}</div>
            <div class="muted">expires ${escapeHtml(key.expires_at || 'not set')} · raw secret visible: no · production: disabled</div>
            ${key.revoked_at ? `<div class="muted">revoked ${escapeHtml(key.revoked_at)} · by ${escapeHtml(key.revoked_by || 'administrator')}</div>` : ''}
            <div style="margin-top:var(--s-2)">${keyLifecycleActions(grantId, key)}</div>
          </div>`;
      }).join('')}`;
    bindKeyLifecycleActions(panel);
  }

  function renderFinalSummary(summary) {
    if (!summary || typeof summary !== 'object') return '';
    const quota = summary.quota || {};
    const executions = summary.executions || {};
    const auditOutcome = text(summary.audit_outcome || 'not_evaluated').replaceAll('_', ' ');
    const tasks = Array.isArray(summary.tasks) ? summary.tasks : [];
    const bindings = Array.isArray(summary.bindings) ? summary.bindings : [];
    return `
      <div class="card flat" style="margin-top:var(--s-2)" data-eval-final-summary="true">
        <div class="sec-hdr">
          <div class="sh-title">Final Evaluation Summary</div>
          <div class="sh-sub">aggregate audit status; qualification decision remains operator-controlled</div>
        </div>
        <div class="admin-api-key-metadata-card-grid">
          <div class="admin-api-key-metadata-card-row"><strong>audit outcome</strong><span>${escapeHtml(auditOutcome)}</span></div>
          <div class="admin-api-key-metadata-card-row"><strong>qualification</strong><span>operator required</span></div>
          <div class="admin-api-key-metadata-card-row"><strong>per-key quota limit</strong><span>${escapeHtml(quota.per_key_limit ?? 0)}</span></div>
          <div class="admin-api-key-metadata-card-row"><strong>used across keys</strong><span>${escapeHtml(quota.used_across_keys ?? 0)}</span></div>
          <div class="admin-api-key-metadata-card-row"><strong>quota rejected across keys</strong><span>${escapeHtml(quota.rejected_across_keys ?? 0)}</span></div>
          <div class="admin-api-key-metadata-card-row"><strong>issued keys</strong><span>${escapeHtml(quota.issued_key_count ?? 0)}</span></div>
          <div class="admin-api-key-metadata-card-row"><strong>succeeded</strong><span>${escapeHtml(executions.succeeded ?? 0)}</span></div>
          <div class="admin-api-key-metadata-card-row"><strong>failed</strong><span>${escapeHtml(executions.failed ?? 0)}</span></div>
          <div class="admin-api-key-metadata-card-row"><strong>executing</strong><span>${escapeHtml(executions.executing ?? 0)}</span></div>
          <div class="admin-api-key-metadata-card-row"><strong>evidence persisted</strong><span>${escapeHtml(executions.evidence_persisted ?? 0)}</span></div>
          <div class="admin-api-key-metadata-card-row"><strong>production</strong><span>disabled</span></div>
        </div>
        <div class="muted" style="margin-top:var(--s-2)">tasks ${escapeHtml(tasks.join(', ') || 'none')} · bindings ${escapeHtml(bindings.join(', ') || 'none')}</div>
        <div class="muted">quota semantics: admitted execution per key · raw secret: no · raw task input: no</div>
      </div>`;
  }

  function renderAuditPanel(panel, summary, receipts) {
    panel.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">Execution Audit</div>
        <div class="sh-sub">safe final receipts mirrored from the authoritative execution ledger</div>
      </div>
      ${renderFinalSummary(summary)}
      ${receipts.length ? receipts.slice(0, 10).map((receipt) => {
        const evidence = receipt.evidence || {};
        return `
          <div class="card flat" style="margin-top:var(--s-2)">
            <div><strong>${escapeHtml(receipt.status || 'unknown')}</strong> · ${escapeHtml(receipt.task_id || '')}</div>
            <div class="muted">${escapeHtml(receipt.binding_id || '')} · key ${escapeHtml(receipt.api_key_id || '')}</div>
            <div class="muted">accepted ${escapeHtml(receipt.accepted_at || 'n/a')} · evidence ${escapeHtml(receipt.evidence_persisted_at || 'pending')}</div>
            <div class="muted">HTTP ${escapeHtml(evidence.http_status ?? 'n/a')} · network executed ${evidence.network_request_executed === true ? 'yes' : 'no'} · raw secret: no · raw task input: no</div>
            ${evidence.evidence_sha256 ? `<div class="muted">evidence sha256 ${escapeHtml(evidence.evidence_sha256)}</div>` : ''}
            ${receipt.failure_code ? `<div class="admin-note danger" style="margin-top:var(--s-2)">failure ${escapeHtml(receipt.failure_code)}</div>` : ''}
          </div>`;
      }).join('') : '<div class="muted">No execution audit receipts yet.</div>'}
    `;
  }

  async function loadKeyLifecyclePanel(panel, grantId) {
    panel.dataset.loading = 'true';
    try {
      const payload = await request(`${EVALUATION_GRANTS_ENDPOINT}/${encodeURIComponent(grantId)}/keys`, 'GET');
      renderKeyLifecyclePanel(panel, grantId, Array.isArray(payload.keys) ? payload.keys : []);
      panel.dataset.loaded = 'true';
    } catch (error) {
      panel.innerHTML = `<div class="admin-note danger">Unable to load issued Evaluation API keys: ${escapeHtml(error.message || error)}</div>`;
    } finally {
      panel.dataset.loading = 'false';
    }
  }

  async function loadAuditPanel(panel, grantId) {
    panel.dataset.loading = 'true';
    try {
      const payload = await request(`${EVALUATION_GRANTS_ENDPOINT}/${encodeURIComponent(grantId)}/audit-receipts?limit=100`, 'GET');
      renderAuditPanel(panel, payload.summary || null, Array.isArray(payload.receipts) ? payload.receipts : []);
      panel.dataset.loaded = 'true';
    } catch (error) {
      panel.innerHTML = `<div class="admin-note danger">Unable to load Evaluation audit receipts: ${escapeHtml(error.message || error)}</div>`;
    } finally {
      panel.dataset.loading = 'false';
    }
  }

  async function mutateEvaluationKey(button, action) {
    const grantId = text(button.dataset.evalKeyGrant);
    const keyId = text(button.dataset.evalKeyDelivered || button.dataset.evalKeyAcknowledge || button.dataset.evalKeyRevoke);
    if (!grantId || !keyId) return;
    if (action === 'revoke') {
      const confirmed = window.confirm('Revoke this Evaluation API key now? The key will be rejected immediately by the runtime.');
      if (!confirmed) return;
    }
    button.disabled = true;
    const suffix = action === 'confirm_delivery' ? 'confirm-delivery' : action === 'acknowledge' ? 'acknowledge' : '';
    const path = action === 'revoke'
      ? `${EVALUATION_GRANTS_ENDPOINT}/${encodeURIComponent(grantId)}/keys/${encodeURIComponent(keyId)}`
      : `${EVALUATION_GRANTS_ENDPOINT}/${encodeURIComponent(grantId)}/keys/${encodeURIComponent(keyId)}/${suffix}`;
    try {
      await request(path, action === 'revoke' ? 'DELETE' : 'POST', action === 'revoke' ? { reason: 'administrator_revoked_from_external_evaluation_ui' } : undefined);
      const card = button.closest('.card.flat')?.parentElement?.closest('.card.flat') || button.closest('.card.flat');
      const panel = button.closest(`[${KEY_PANEL_ATTRIBUTE}]`);
      if (panel) await loadKeyLifecyclePanel(panel, grantId);
      const auditPanel = card?.querySelector?.(`[${AUDIT_PANEL_ATTRIBUTE}]`);
      if (auditPanel) await loadAuditPanel(auditPanel, grantId);
      window.dispatchEvent(new CustomEvent('pmk-evaluation-key-lifecycle-updated'));
    } catch (error) {
      button.disabled = false;
      window.alert(`Unable to update Evaluation API key: ${error.message || error}`);
    }
  }

  function bindKeyLifecycleActions(panel) {
    panel.querySelectorAll('[data-eval-key-delivered]').forEach((button) => button.addEventListener('click', () => mutateEvaluationKey(button, 'confirm_delivery')));
    panel.querySelectorAll('[data-eval-key-acknowledge]').forEach((button) => button.addEventListener('click', () => mutateEvaluationKey(button, 'acknowledge')));
    panel.querySelectorAll('[data-eval-key-revoke]').forEach((button) => button.addEventListener('click', () => mutateEvaluationKey(button, 'revoke')));
  }

  function decorateGrantKeyLifecycle() {
    const host = document.getElementById(EVALUATION_HOST_ID);
    if (!host) return;
    host.querySelectorAll('[data-eval-issue]').forEach((issueButton) => {
      const grantId = text(issueButton.dataset.evalIssue);
      const card = issueButton.closest('.card.flat');
      if (!grantId || !card) return;

      let keyPanel = card.querySelector(`[${KEY_PANEL_ATTRIBUTE}]`);
      if (!keyPanel) {
        keyPanel = document.createElement('section');
        keyPanel.setAttribute(KEY_PANEL_ATTRIBUTE, 'true');
        keyPanel.dataset.grantId = grantId;
        keyPanel.className = 'card flat';
        keyPanel.style.marginTop = 'var(--s-3)';
        keyPanel.innerHTML = '<div class="muted">Loading issued Evaluation API keys...</div>';
        card.appendChild(keyPanel);
      }
      if (keyPanel.dataset.loaded !== 'true' && keyPanel.dataset.loading !== 'true') loadKeyLifecyclePanel(keyPanel, grantId);

      let auditPanel = card.querySelector(`[${AUDIT_PANEL_ATTRIBUTE}]`);
      if (!auditPanel) {
        auditPanel = document.createElement('section');
        auditPanel.setAttribute(AUDIT_PANEL_ATTRIBUTE, 'true');
        auditPanel.dataset.grantId = grantId;
        auditPanel.className = 'card flat';
        auditPanel.style.marginTop = 'var(--s-3)';
        auditPanel.innerHTML = '<div class="muted">Loading Evaluation audit receipts...</div>';
        card.appendChild(auditPanel);
      }
      if (auditPanel.dataset.loaded !== 'true' && auditPanel.dataset.loading !== 'true') loadAuditPanel(auditPanel, grantId);
    });
  }

  function observeGrantKeyLifecycle() {
    const host = document.getElementById(EVALUATION_HOST_ID);
    if (!host || grantObserver) return;
    grantObserver = new MutationObserver(() => decorateGrantKeyLifecycle());
    grantObserver.observe(host, { childList: true, subtree: true });
    decorateGrantKeyLifecycle();
  }

  function updateModeVisibility() {
    const card = document.getElementById(CARD_ID);
    const externalCard = document.getElementById(EXTERNAL_CARD_ID);
    const externalBody = document.getElementById(EXTERNAL_BODY_ID);
    const slot = ensureSlot();
    if (!card || !externalCard || !externalBody || !slot) return;
    const evaluationMode = mode() === 'external_evaluation';
    slot.hidden = !evaluationMode;
    if (evaluationMode) {
      externalCard.dataset.activated = 'true';
      externalBody.hidden = false;
    }
    const standardGrid = directStandardGrid(card);
    const scopesLabel = standardScopesLabel();
    const actions = standardActions();
    if (standardGrid) standardGrid.hidden = evaluationMode;
    if (scopesLabel) scopesLabel.hidden = evaluationMode;
    if (actions) actions.hidden = evaluationMode;
    const status = document.getElementById('admin-api-key-provisioning-mode-status');
    if (status && evaluationMode) {
      status.className = 'admin-note ok';
      status.textContent = 'External Evaluation mode is active. CRM/Integration grant authority, fixed quota, one-time key + safe handoff, customer dashboard, delivery/receipt evidence, Admin audit summary, and revocation are embedded below.';
    }
    renderEvaluationPreview();
    decorateGrantKeyLifecycle();
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
      if (attachAttempts < MAX_ATTACH_ATTEMPTS) window.setTimeout(attachEvaluationHost, ATTACH_RETRY_MS);
      else document.body.dataset.adminApiKeyEvaluationLifecycle = 'attach-timeout';
      return;
    }
    const hostSlot = slot.querySelector('[data-admin-evaluation-host-slot]');
    if (hostSlot && host.parentElement !== hostSlot) hostSlot.appendChild(host);
    host.classList.add('flat');
    host.style.marginTop = '0';
    host.dataset.lifecycleEmbedded = 'true';
    bindEvaluationChanges(host);
    observeGrantKeyLifecycle();
    updateModeVisibility();
    document.body.dataset.adminApiKeyEvaluationLifecycle = 'loaded';
  }

  function initialize() {
    const workspace = document.getElementById(WORKSPACE_ID);
    const modeSelect = document.getElementById(MODE_ID);
    const externalBody = document.getElementById(EXTERNAL_BODY_ID);
    if (!workspace || !modeSelect || !externalBody) {
      attachAttempts += 1;
      if (attachAttempts < MAX_ATTACH_ATTEMPTS) window.setTimeout(initialize, ATTACH_RETRY_MS);
      return;
    }
    ensureSlot();
    if (modeSelect.dataset.evaluationLifecycleBound !== 'true') {
      modeSelect.dataset.evaluationLifecycleBound = 'true';
      modeSelect.addEventListener('change', updateModeVisibility);
    }
    window.addEventListener('pmk-evaluation-selection-changed', renderEvaluationPreview);
    window.addEventListener('pmk-evaluation-grant-updated', () => {
      renderEvaluationPreview();
      decorateGrantKeyLifecycle();
    });
    window.addEventListener('pmk-evaluation-execution-updated', decorateGrantKeyLifecycle);
    updateModeVisibility();
    attachEvaluationHost();
  }

  window.PMK_ADMIN_API_KEY_EVALUATION_LIFECYCLE = {
    initialize,
    attachEvaluationHost,
    renderEvaluationPreview,
    decorateGrantKeyLifecycle,
  };

  initialize();
})();
