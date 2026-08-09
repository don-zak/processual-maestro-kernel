(() => {
  'use strict';

  const ROOT_ID = 'se18-control-plane';
  const ENDPOINT = '/settings/enterprise-integration';
  let initialized = false;
  let loading = false;
  let observer = null;
  let lastRenderedSignature = '';

  function text(value, fallback = '—') {
    if (value === null || value === undefined || value === '') {
      return fallback;
    }
    return String(value);
  }

  function number(value) {
    const parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function element(tag, className, copy) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (copy !== undefined) node.textContent = copy;
    return node;
  }

  function metric(label, value, hint) {
    const item = element('div', 'se18-metric');
    const labelNode = element('span', 'se18-metric-label', label);
    const valueNode = element('strong', 'se18-metric-value', text(value, '0'));
    item.append(labelNode, valueNode);
    if (hint) {
      item.appendChild(element('span', 'se18-metric-hint', hint));
    }
    return item;
  }

  function identityItem(label, value, code = false) {
    const item = element('div', 'se18-identity-item');
    item.appendChild(element('span', 'se18-eyebrow', label));
    const valueNode = element(code ? 'code' : 'strong', code ? 'se18-code' : 'se18-identity-value', text(value));
    item.appendChild(valueNode);
    return item;
  }

  function panelHeader(title, copy) {
    const wrap = element('div', 'se18-panel-header');
    const titleNode = element('h4', 'se18-panel-title', title);
    wrap.appendChild(titleNode);
    if (copy) wrap.appendChild(element('p', 'se18-panel-copy', copy));
    return wrap;
  }

  function statePill(label, state) {
    const pill = element('span', 'se18-state-pill', label);
    pill.dataset.state = state;
    return pill;
  }

  function renderIdentity(root, payload) {
    const section = element('section', 'se18-panel se18-identity');
    section.setAttribute('aria-labelledby', 'se18-identity-title');
    const header = panelHeader(
      'Enterprise identity',
      'Public plan identity stays compatible while the canonical catalog identity drives fulfillment and policy.'
    );
    header.querySelector('.se18-panel-title').id = 'se18-identity-title';
    section.appendChild(header);

    const grid = element('div', 'se18-identity-grid');
    grid.append(
      identityItem('Public plan', payload.plan_id || payload.normalized_plan_id),
      identityItem('Canonical catalog ID', payload.canonical_plan_id || payload.normalized_plan_id, true),
      identityItem('Runtime environment', payload.environment || 'sandbox'),
      identityItem('Operational profiles', number(payload.operational_profile_count))
    );
    section.appendChild(grid);
    root.appendChild(section);
  }

  function renderScopePosture(root, payload) {
    const posture = payload.scope_posture || {};
    const section = element('section', 'se18-panel se18-posture');
    section.setAttribute('aria-labelledby', 'se18-posture-title');
    const header = panelHeader(
      'Catalog scope posture',
      'This describes the integration scope catalog available for review. It is not a grant of client permissions.'
    );
    header.querySelector('.se18-panel-title').id = 'se18-posture-title';
    section.appendChild(header);

    const provenance = element('div', 'se18-provenance');
    provenance.append(
      statePill(posture.source === 'catalog' ? 'Catalog-derived' : 'Source unavailable', posture.source === 'catalog' ? 'verified' : 'warning'),
      element('span', 'se18-provenance-copy', 'Authorization remains server-side and supervised for elevated scopes.')
    );
    section.appendChild(provenance);

    if (payload.enabled !== true) {
      section.appendChild(
        element('p', 'se18-locked-copy', 'Scope review details remain locked until an eligible Enterprise Integration entitlement is active.')
      );
      root.appendChild(section);
      return;
    }

    const metrics = element('div', 'se18-metric-grid');
    metrics.append(
      metric('Catalog scopes', number(posture.total), 'reviewable'),
      metric('Read', number(posture.read), 'least privilege'),
      metric('Write', number(posture.write), 'supervised'),
      metric('Restricted', number(posture.restricted), 'supervised'),
      metric('Read-only pilot', number(posture.read_only_pilot), 'sandbox-safe'),
      metric('Supervisor review', number(posture.supervisor_approval_required), 'required')
    );
    section.appendChild(metrics);

    const invariant = element('div', 'se18-invariant');
    invariant.append(
      element('strong', '', 'Production without approval'),
      statePill(number(posture.production_allowed_without_approval) === 0 ? '0 — blocked' : 'Review required', number(posture.production_allowed_without_approval) === 0 ? 'blocked' : 'warning')
    );
    section.appendChild(invariant);
    root.appendChild(section);
  }

  function renderReadiness(root, payload) {
    const readiness = payload.readiness || {};
    const section = element('section', 'se18-panel se18-readiness');
    section.setAttribute('aria-labelledby', 'se18-readiness-title');
    const header = panelHeader(
      'Qualification readiness',
      'A concise operational view of what is ready for sandbox review and what remains deliberately blocked.'
    );
    header.querySelector('.se18-panel-title').id = 'se18-readiness-title';
    section.appendChild(header);

    const metrics = element('div', 'se18-metric-grid se18-metric-grid-compact');
    metrics.append(
      metric('Readiness checks', number(readiness.total)),
      metric('Sandbox ready', number(readiness.sandbox_ready)),
      metric('Blocked checks', number(readiness.blocked)),
      metric('Active keys', number(payload.key_count))
    );
    section.appendChild(metrics);

    const next = element('div', 'se18-next-action');
    next.append(
      element('span', 'se18-eyebrow', 'Next safe action'),
      element('strong', 'se18-next-copy', text(payload.next_action, 'Review integration readiness.'))
    );
    section.appendChild(next);
    root.appendChild(section);
  }

  function renderProductionGuard(root, payload, degraded = false) {
    const section = element('section', 'se18-production-guard');
    section.setAttribute('aria-labelledby', 'se18-production-title');

    const copy = element('div', 'se18-production-copy');
    const eyebrow = element('span', 'se18-eyebrow', 'Production boundary');
    const title = element('h4', 'se18-production-title', 'Production access remains blocked');
    title.id = 'se18-production-title';
    const detail = element(
      'p',
      '',
      degraded
        ? 'Enterprise state could not be verified. Maestro fails closed: no production connector approval is inferred.'
        : 'Settings can prepare sandbox qualification only. Runtime connector approval requires supervised qualification outside this surface.'
    );
    copy.append(eyebrow, title, detail);

    const status = element('div', 'se18-production-status');
    status.append(
      statePill(payload?.production_allowed === false ? 'Production blocked' : 'Fail-closed', 'blocked'),
      statePill(payload?.runtime_connector_approved === false ? 'Runtime unapproved' : 'Approval unknown', 'blocked')
    );
    section.append(copy, status);
    root.appendChild(section);
  }

  function signature(payload) {
    return JSON.stringify({
      enabled: payload.enabled,
      plan: payload.plan_id,
      canonical: payload.canonical_plan_id,
      keys: payload.key_count,
      profiles: payload.operational_profile_count,
      scope: payload.scope_posture,
      readiness: payload.readiness,
      next: payload.next_action,
      production: payload.production_allowed,
      runtime: payload.runtime_connector_approved,
    });
  }

  function render(payload) {
    const card = document.getElementById('set-enterprise-console-card');
    if (!card || !payload) return;

    const currentSignature = signature(payload);
    if (currentSignature === lastRenderedSignature && document.getElementById(ROOT_ID)) {
      return;
    }
    lastRenderedSignature = currentSignature;

    document.getElementById(ROOT_ID)?.remove();
    const root = element('div', 'se18-control-plane');
    root.id = ROOT_ID;
    root.setAttribute('role', 'region');
    root.setAttribute('aria-label', 'Enterprise integration control plane');
    root.setAttribute('aria-live', 'polite');

    renderIdentity(root, payload);
    renderScopePosture(root, payload);
    renderReadiness(root, payload);
    renderProductionGuard(root, payload, false);

    const safety = document.getElementById('set-enterprise-console-safety');
    if (safety) card.insertBefore(root, safety);
    else card.appendChild(root);
    card.dataset.se18Enhanced = 'true';
    card.setAttribute('aria-busy', 'false');
  }

  function renderFailure() {
    const card = document.getElementById('set-enterprise-console-card');
    if (!card) return;
    document.getElementById(ROOT_ID)?.remove();
    const root = element('div', 'se18-control-plane se18-control-plane-error');
    root.id = ROOT_ID;
    root.setAttribute('role', 'status');
    root.setAttribute('aria-live', 'polite');
    root.appendChild(
      element('p', 'se18-error-copy', 'Enterprise control-plane details are temporarily unavailable. No production access has been inferred or granted.')
    );
    renderProductionGuard(root, null, true);
    card.appendChild(root);
    card.dataset.se18Enhanced = 'error';
    card.setAttribute('aria-busy', 'false');
  }

  async function refresh(force = false) {
    const card = document.getElementById('set-enterprise-console-card');
    if (!card || loading) return;
    const enhancedState = card.dataset.se18Enhanced;
    if (!force && (enhancedState === 'true' || enhancedState === 'error')) return;

    loading = true;
    card.setAttribute('aria-busy', 'true');
    try {
      const payload = await CLIENT.get(ENDPOINT);
      render(payload);
    } catch (error) {
      renderFailure();
    } finally {
      loading = false;
    }
  }

  function watch() {
    if (observer || !document.body) return;
    observer = new MutationObserver(() => {
      if (document.getElementById('set-enterprise-console-card')) {
        refresh(false);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function init() {
    if (!initialized) {
      initialized = true;
      watch();
    }
    refresh(false);
  }

  window.PMK_SETTINGS_ENTERPRISE_CONSOLE_18 = {
    init,
    refresh,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
