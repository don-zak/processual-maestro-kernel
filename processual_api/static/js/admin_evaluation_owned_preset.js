(function () {
  const DEFAULT_BASE_URL = 'https://processual-maestro-evaluation-sandbox.zaksam2030.workers.dev';
  const HOST_ID = 'admin-evaluation-owned-crm-preset';
  const EXTERNAL_CATEGORY = 'external_evaluation';
  const PRESETS = [
    {
      id: 'CRM-CONTEXT-01',
      title: 'CRM Customer Context',
      endpoint: '/settings/admin/evaluation-grants/bindings/presets/crm-context-owned',
      bindingId: 'evaluation.crm.customer_context.owned',
      evaluationType: 'crm',
      quota: 100,
      note: 'Qualified foundation safe-read scenario.',
    },
    {
      id: 'CRM-SUMMARY-01',
      title: 'CRM Customer State Summary',
      endpoint: '/settings/admin/evaluation-grants/bindings/presets/crm-summary-owned',
      bindingId: 'evaluation.crm.customer_state_summary.owned',
      evaluationType: 'crm',
      quota: 100,
      note: 'Requires the updated owned Worker and live binding proof.',
    },
    {
      id: 'CRM-DRAFT-01',
      title: 'CRM Update Draft',
      endpoint: '/settings/admin/evaluation-grants/bindings/presets/crm-update-draft-owned',
      bindingId: 'evaluation.crm.customer_update_draft.owned',
      evaluationType: 'crm',
      quota: 100,
      note: 'Sandbox draft only; production mutation remains disabled.',
    },
    {
      id: 'INT-BILLING-01',
      title: 'Integration Billing Account Context',
      endpoint: '/settings/admin/evaluation-grants/bindings/presets/integration-billing-owned',
      bindingId: 'evaluation.integration.billing_account_context.owned',
      evaluationType: 'integration',
      quota: 200,
      note: 'Integration safe-read proof; requires the updated owned Worker.',
    },
  ];

  const selectedBindingIds = new Set();
  const issuingGrantIds = new Set();
  let bindingObserver = null;
  let observedBindingList = null;
  let restoringBindingSelection = false;

  function text(value) { return String(value ?? '').trim(); }
  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }
  function authHeaders() {
    const auth = window.PMK_ADMIN_AUTH;
    const headers = auth && typeof auth.headers === 'function'
      ? auth.headers({ Accept: 'application/json' })
      : new Headers({ Accept: 'application/json' });
    if (headers && typeof headers.set === 'function') headers.set('Content-Type', 'application/json');
    else if (headers && typeof headers === 'object') headers['Content-Type'] = 'application/json';
    return headers;
  }
  function externalEvaluationSelected() {
    return text(document.getElementById('admin-api-key-category')?.value) === EXTERNAL_CATEGORY;
  }

  function bindIssueKeyCaptureGuard() {
    if (document.documentElement.dataset.evaluationIssueKeyCaptureBound === 'true') return;
    document.documentElement.dataset.evaluationIssueKeyCaptureBound = 'true';
    document.addEventListener('click', async (event) => {
      const target = event.target instanceof Element ? event.target : null;
      const button = target?.closest?.('[data-eval-issue]');
      if (!button) return;
      const grantId = text(button.dataset.evalIssue);
      const issueKey = window.PMK_ADMIN_EVALUATION_GRANTS?.issueKey;
      if (!grantId || typeof issueKey !== 'function') return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (issuingGrantIds.has(grantId)) return;
      issuingGrantIds.add(grantId);
      const originalLabel = button.textContent || 'Issue API Key';
      button.disabled = true;
      button.textContent = 'Issuing API Key…';
      try { await issueKey(grantId); }
      finally {
        issuingGrantIds.delete(grantId);
        if (button.isConnected) { button.disabled = false; button.textContent = originalLabel; }
      }
    }, true);
  }

  function captureBindingSelection(event) {
    const target = event.target instanceof Element ? event.target.closest('[data-eval-binding]') : null;
    if (!target || target.disabled) return;
    const bindingId = text(target.value);
    if (!bindingId) return;
    if (target.checked) selectedBindingIds.add(bindingId);
    else selectedBindingIds.delete(bindingId);
  }

  function restoreBindingSelection() {
    if (restoringBindingSelection) return;
    const list = document.getElementById('admin-eval-binding-list');
    if (!list) return;
    restoringBindingSelection = true;
    let readinessChanged = false;
    const currentIds = new Set();
    list.querySelectorAll('[data-eval-binding]').forEach((input) => {
      const bindingId = text(input.value);
      if (!bindingId) return;
      currentIds.add(bindingId);
      if (input.disabled) { selectedBindingIds.delete(bindingId); return; }
      if (selectedBindingIds.has(bindingId) && !input.checked) {
        input.checked = true;
        readinessChanged = true;
      }
    });
    [...selectedBindingIds].forEach((bindingId) => {
      if (!currentIds.has(bindingId)) selectedBindingIds.delete(bindingId);
    });
    restoringBindingSelection = false;
    if (readinessChanged) window.PMK_ADMIN_EVALUATION_GRANTS?.updateReadiness?.();
  }

  function ensureBindingSelectionPersistence() {
    const list = document.getElementById('admin-eval-binding-list');
    if (!list) return false;
    if (observedBindingList === list && bindingObserver) { restoreBindingSelection(); return true; }
    if (bindingObserver) bindingObserver.disconnect();
    observedBindingList = list;
    list.addEventListener('change', captureBindingSelection);
    bindingObserver = new MutationObserver(() => window.queueMicrotask(restoreBindingSelection));
    bindingObserver.observe(list, { childList: true });
    restoreBindingSelection();
    return true;
  }

  function presetById(presetId) { return PRESETS.find((item) => item.id === presetId); }
  async function preparePreset(presetId) {
    const preset = presetById(presetId);
    if (!preset) return;
    const button = document.querySelector(`[data-owned-preset-run="${preset.id}"]`);
    const result = document.querySelector(`[data-owned-preset-result="${preset.id}"]`);
    const baseUrl = text(document.getElementById('admin-eval-owned-preset-url')?.value);
    const ttlMinutes = Number.parseInt(document.getElementById('admin-eval-owned-preset-ttl')?.value || '30', 10);
    if (!baseUrl.startsWith('https://')) {
      if (result) { result.className = 'admin-note danger'; result.textContent = 'A public HTTPS project-owned sandbox URL is required.'; }
      return;
    }
    if (button) button.disabled = true;
    if (result) {
      result.className = 'admin-note';
      result.textContent = 'Running backend-governed provisioning and live sandbox proof. This fails closed if the Worker route or binding readiness is unavailable…';
    }
    try {
      const response = await fetch(preset.endpoint, {
        method: 'POST', credentials: 'include', headers: authHeaders(),
        body: JSON.stringify({ base_url: baseUrl, binding_id: preset.bindingId, ttl_minutes: Number.isInteger(ttlMinutes) ? ttlMinutes : 30 }),
      });
      const raw = await response.text();
      let payload = {};
      if (raw) { try { payload = JSON.parse(raw); } catch { payload = { detail: raw }; } }
      if (!response.ok) {
        const detail = payload.detail || payload.message || `HTTP ${response.status}`;
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      }
      const proof = payload.proof || {};
      const readiness = payload.sandbox_readiness || {};
      const safe = payload.binding_selectable === true
        && proof.operational_proof === true
        && proof.peer_address_verified === true
        && proof.network_request_executed === true
        && proof.mapping_valid === true
        && proof.ready_for_task_consumption === true
        && payload.production_allowed === false;
      if (!safe) throw new Error(`${preset.id} returned without complete selectable live-proof state.`);
      if (preset.id === 'CRM-DRAFT-01') {
        const draft = payload.draft_contract || {};
        if (draft.applied !== false || draft.production_mutation_performed !== false || draft.production_allowed !== false) {
          throw new Error('CRM-DRAFT-01 safety contract was not preserved.');
        }
      }
      const refreshBindingCatalog = window.PMK_ADMIN_EVALUATION_GRANTS?.refreshBindingCatalog;
      if (typeof refreshBindingCatalog !== 'function') throw new Error('Evaluation binding catalog refresh is unavailable.');
      selectedBindingIds.add(preset.bindingId);
      await refreshBindingCatalog();
      restoreBindingSelection();
      if (result) {
        result.className = 'admin-note ok';
        result.innerHTML = [
          `<strong>${escapeHtml(preset.id)} READY.</strong>`,
          `Binding <code>${escapeHtml(payload.binding_id)}</code> is sandbox-ready and selectable.`,
          `Task: <code>${escapeHtml(payload.task_id)}</code> · readiness: ${escapeHtml(readiness.status || 'sandbox_ready')}.`,
          `Evaluation type: ${escapeHtml(preset.evaluationType)} · recommended quota: ${preset.quota} admitted executions.`,
          'Live proof persisted · raw secret: no · raw payload: no · production: disabled.',
        ].join('<br>');
      }
    } catch (error) {
      if (result) {
        result.className = 'admin-note danger';
        result.textContent = `${preset.id} remains BLOCKED: ${error.message || error}`;
      }
    } finally {
      if (button) button.disabled = false;
    }
  }

  function presetCard(preset) {
    return `<div class="card flat" style="margin-top:var(--s-2);padding:var(--s-2)">
      <div><strong>${escapeHtml(preset.id)} · ${escapeHtml(preset.title)}</strong></div>
      <div class="sh-sub">${escapeHtml(preset.note)}</div>
      <div class="sh-sub">Binding: <code>${escapeHtml(preset.bindingId)}</code> · ${escapeHtml(preset.evaluationType)} quota ${preset.quota}</div>
      <button data-owned-preset-run="${escapeHtml(preset.id)}" class="btn secondary" type="button" style="margin-top:var(--s-2)">Prepare & prove ${escapeHtml(preset.id)}</button>
      <div data-owned-preset-result="${escapeHtml(preset.id)}" class="admin-note" style="margin-top:var(--s-2)">No proof run yet. A successful result requires live backend proof; UI presence alone grants no authority.</div>
    </div>`;
  }

  function render() {
    const grants = document.getElementById('admin-evaluation-grants');
    if (!grants) return false;
    let host = document.getElementById(HOST_ID);
    if (!host) {
      host = document.createElement('section');
      host.id = HOST_ID;
      host.className = 'card flat';
      host.style.marginTop = 'var(--s-3)';
      host.innerHTML = `<div class="sec-hdr"><div class="sh-title">Owned External Evaluation scenario preparation</div><div class="sh-sub">Backend-proven preparation only; failed or unavailable Worker routes stay blocked.</div></div>
        <div class="admin-note">These controls never create authority by themselves. Each action must provision a sandbox binding, execute hardened outbound proof, and return a selectable binding before it can enter an Evaluation Grant.</div>
        <div class="grid-2" style="margin-top:var(--s-2)">
          <label>Owned sandbox URL<input id="admin-eval-owned-preset-url" type="url" value="${DEFAULT_BASE_URL}"></label>
          <label>Sandbox proof TTL minutes<input id="admin-eval-owned-preset-ttl" type="number" min="5" max="120" value="30"></label>
        </div>
        <div id="admin-eval-owned-preset-cards">${PRESETS.map(presetCard).join('')}</div>`;
      const bindingSection = document.getElementById('admin-eval-binding-list')?.parentElement;
      if (bindingSection && bindingSection.parentElement === grants) grants.insertBefore(host, bindingSection);
      else grants.prepend(host);
      host.querySelectorAll('[data-owned-preset-run]').forEach((button) => {
        button.addEventListener('click', () => preparePreset(text(button.dataset.ownedPresetRun)));
      });
    }
    host.hidden = !externalEvaluationSelected();
    ensureBindingSelectionPersistence();
    return true;
  }

  function scheduleRender() {
    bindIssueKeyCaptureGuard();
    if (render()) return;
    let attempts = 0;
    const timer = window.setInterval(() => { attempts += 1; if (render() || attempts >= 30) window.clearInterval(timer); }, 150);
  }

  window.addEventListener('pmk-api-key-category-changed', () => { render(); ensureBindingSelectionPersistence(); });
  window.addEventListener('pmk-api-key-access-selection-changed', () => window.queueMicrotask(restoreBindingSelection));
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', scheduleRender);
  else scheduleRender();
})();