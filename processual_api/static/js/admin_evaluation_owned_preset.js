(function () {
  const PRESET_ENDPOINT = '/settings/admin/evaluation-grants/bindings/presets/crm-context-owned';
  const DEFAULT_BASE_URL = 'https://processual-maestro-evaluation-sandbox.zaksam2030.workers.dev';
  const HOST_ID = 'admin-evaluation-owned-crm-preset';
  const EXTERNAL_CATEGORY = 'external_evaluation';

  const selectedBindingIds = new Set();
  let bindingObserver = null;
  let observedBindingList = null;
  let restoringBindingSelection = false;

  function text(value) {
    return String(value ?? '').trim();
  }

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
    if (headers && typeof headers.set === 'function') {
      headers.set('Content-Type', 'application/json');
    } else if (headers && typeof headers === 'object') {
      headers['Content-Type'] = 'application/json';
    }
    return headers;
  }

  function externalEvaluationSelected() {
    return text(document.getElementById('admin-api-key-category')?.value) === EXTERNAL_CATEGORY;
  }

  function captureBindingSelection(event) {
    const target = event.target instanceof Element
      ? event.target.closest('[data-eval-binding]')
      : null;
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

      if (input.disabled) {
        selectedBindingIds.delete(bindingId);
        return;
      }

      if (selectedBindingIds.has(bindingId) && !input.checked) {
        input.checked = true;
        readinessChanged = true;
      }
    });

    [...selectedBindingIds].forEach((bindingId) => {
      if (!currentIds.has(bindingId)) selectedBindingIds.delete(bindingId);
    });

    restoringBindingSelection = false;
    if (readinessChanged) {
      window.PMK_ADMIN_EVALUATION_GRANTS?.updateReadiness?.();
    }
  }

  function ensureBindingSelectionPersistence() {
    const list = document.getElementById('admin-eval-binding-list');
    if (!list) return false;

    if (observedBindingList === list && bindingObserver) {
      restoreBindingSelection();
      return true;
    }

    if (bindingObserver) bindingObserver.disconnect();
    observedBindingList = list;
    list.addEventListener('change', captureBindingSelection);
    bindingObserver = new MutationObserver(() => {
      window.queueMicrotask(restoreBindingSelection);
    });
    bindingObserver.observe(list, { childList: true });
    restoreBindingSelection();
    return true;
  }

  async function prepareOwnedCrmPreset() {
    const button = document.getElementById('admin-eval-owned-preset-run');
    const result = document.getElementById('admin-eval-owned-preset-result');
    const baseUrl = text(document.getElementById('admin-eval-owned-preset-url')?.value);
    const bindingId = text(document.getElementById('admin-eval-owned-preset-binding')?.value)
      || 'evaluation.crm.customer_context.owned';
    const ttlMinutes = Number.parseInt(
      document.getElementById('admin-eval-owned-preset-ttl')?.value || '30',
      10
    );

    if (!baseUrl.startsWith('https://')) {
      if (result) {
        result.className = 'admin-note danger';
        result.textContent = 'A public HTTPS project-owned sandbox URL is required.';
      }
      return;
    }

    if (button) button.disabled = true;
    if (result) {
      result.className = 'admin-note';
      result.textContent = 'Provisioning binding, issuing short-lived sandbox grant, running hardened live proof, and rechecking readiness…';
    }

    try {
      const response = await fetch(PRESET_ENDPOINT, {
        method: 'POST',
        credentials: 'include',
        headers: authHeaders(),
        body: JSON.stringify({
          base_url: baseUrl,
          binding_id: bindingId,
          ttl_minutes: Number.isInteger(ttlMinutes) ? ttlMinutes : 30,
        }),
      });
      const raw = await response.text();
      let payload = {};
      if (raw) {
        try { payload = JSON.parse(raw); } catch { payload = { detail: raw }; }
      }
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
        && proof.ready_for_task_consumption === true;
      if (!safe) {
        throw new Error('Owned CRM preset returned without a complete selectable live-proof state.');
      }

      if (result) {
        result.className = 'admin-note ok';
        result.innerHTML = [
          '<strong>CRM-CONTEXT-01 READY.</strong>',
          `Binding <code>${escapeHtml(payload.binding_id)}</code> is sandbox-ready and selectable.`,
          `Readiness: ${escapeHtml(readiness.status || 'sandbox_ready')}.`,
          'Content owner: project · credential reference: project-scoped anonymous/public · raw secret: no · production: disabled.',
          'Reloading the authoritative binding catalog…',
        ].join('<br>');
      }
      window.setTimeout(() => window.location.reload(), 900);
    } catch (error) {
      if (result) {
        result.className = 'admin-note danger';
        result.textContent = `Owned CRM proof preset failed: ${error.message || error}`;
      }
      if (button) button.disabled = false;
    }
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
      host.innerHTML = `
        <div class="sec-hdr">
          <div class="sh-title">Owned CRM proof preset</div>
          <div class="sh-sub">one-step preparation for CRM-CONTEXT-01 before creating the Evaluation Grant</div>
        </div>
        <div class="admin-note">
          Uses the project-owned read-only sandbox only. This action provisions a CRM read binding, project-owned synthetic content references, a project-scoped anonymous/public credential reference, a short-lived sandbox grant, and a hardened outbound live proof. It does not create an Evaluation Grant or API key.
        </div>
        <div class="grid-3" style="margin-top:var(--s-2)">
          <label>Owned sandbox URL<input id="admin-eval-owned-preset-url" type="url" value="${DEFAULT_BASE_URL}"></label>
          <label>Binding ID<input id="admin-eval-owned-preset-binding" type="text" value="evaluation.crm.customer_context.owned"></label>
          <label>Sandbox grant TTL minutes<input id="admin-eval-owned-preset-ttl" type="number" min="5" max="120" value="30"></label>
        </div>
        <button id="admin-eval-owned-preset-run" class="btn secondary" type="button" style="margin-top:var(--s-2)">Prepare & prove CRM-CONTEXT-01</button>
        <div id="admin-eval-owned-preset-result" class="admin-note" style="margin-top:var(--s-2)">No proof run yet.</div>
      `;
      const bindingSection = document.getElementById('admin-eval-binding-list')?.parentElement;
      if (bindingSection && bindingSection.parentElement === grants) {
        grants.insertBefore(host, bindingSection);
      } else {
        grants.prepend(host);
      }
      document.getElementById('admin-eval-owned-preset-run')?.addEventListener('click', prepareOwnedCrmPreset);
    }
    host.hidden = !externalEvaluationSelected();
    ensureBindingSelectionPersistence();
    return true;
  }

  function scheduleRender() {
    if (render()) return;
    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      if (render() || attempts >= 30) window.clearInterval(timer);
    }, 150);
  }

  window.addEventListener('pmk-api-key-category-changed', () => {
    render();
    ensureBindingSelectionPersistence();
  });
  window.addEventListener('pmk-api-key-access-selection-changed', () => {
    window.queueMicrotask(restoreBindingSelection);
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleRender);
  } else {
    scheduleRender();
  }
})();
