(() => {
  'use strict';

  const ROOT_ID = 'admin-enterprise-failure-review';
  let activeFilter = 'open';
  let currentPayload = null;
  let currentClientId = '';

  function el(tag, className, copy) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (copy !== undefined) node.textContent = String(copy);
    return node;
  }

  function stageLabel(value) {
    return String(value || 'execution').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  function safeHeaders() {
    if (window.PMK_ADMIN_AUTH?.headers) return PMK_ADMIN_AUTH.headers();
    return new Headers({ 'Content-Type': 'application/json' });
  }

  async function jsonRequest(path, options = {}) {
    const response = await fetch(path, {
      credentials: 'include',
      ...options,
      headers: safeHeaders(options.headers),
    });
    let payload = null;
    try { payload = await response.json(); } catch (error) {}
    if (!response.ok) {
      const detail = payload?.detail;
      const message = typeof detail === 'string' ? detail : detail?.message || `HTTP ${response.status}`;
      const failure = new Error(message);
      failure.status = response.status;
      throw failure;
    }
    return payload || {};
  }

  function metric(label, value, state = '') {
    const node = el('div', `aefr-metric ${state ? `aefr-metric-${state}` : ''}`);
    node.append(el('span', '', label), el('strong', '', value));
    return node;
  }

  function setStatus(root, copy, state = 'info') {
    const node = root.querySelector('[data-aefr-status]');
    node.dataset.state = state;
    node.textContent = copy;
  }

  function filteredFailures(payload) {
    const failures = [...(payload?.failures || [])].reverse();
    return activeFilter === 'all'
      ? failures
      : failures.filter(item => item.status === activeFilter);
  }

  function renderFilters(root, payload) {
    const region = root.querySelector('[data-aefr-filters]');
    region.replaceChildren();
    const filters = [
      ['open', `Open ${payload.open_count || 0}`],
      ['reviewing', `Reviewing ${payload.reviewing_count || 0}`],
      ['resolved', `Resolved ${payload.resolved_count || 0}`],
      ['all', `All ${payload.failure_count || 0}`],
    ];
    filters.forEach(([value, label]) => {
      const button = el('button', 'aefr-filter', label);
      button.type = 'button';
      button.dataset.active = String(value === activeFilter);
      button.addEventListener('click', () => {
        activeFilter = value;
        renderFilters(root, currentPayload || payload);
        renderFailures(root, currentPayload || payload);
      });
      region.appendChild(button);
    });
  }

  async function startReview(root, failure) {
    if (!currentClientId) return;
    const diagnostic = window.PMK_ADMIN_AUTH?.diagnostic?.() || {};
    if (!diagnostic.supervisorSessionKeyFound) {
      setStatus(root, 'A validated supervisor session key is required before starting review.', 'error');
      return;
    }
    try {
      setStatus(root, `Starting review for ${failure.failure_id}…`);
      await jsonRequest(
        `/settings/admin/integration-tasks/${encodeURIComponent(currentClientId)}/sandbox-failures/${encodeURIComponent(failure.failure_id)}/review`,
        { method: 'POST', body: '{}' }
      );
      await loadQueue(root, currentClientId, true);
      setStatus(root, 'Failure moved to Reviewing. Correct the customer binding/configuration, then confirm resolution through a successful sandbox retest.', 'success');
    } catch (error) {
      setStatus(root, error?.message || 'Review could not be started.', 'error');
    }
  }

  function failureCard(root, item) {
    const card = el('article', 'aefr-card');
    card.dataset.status = item.status || 'open';
    const head = el('div', 'aefr-card-head');
    const title = el('div', '');
    title.append(el('strong', '', item.binding_id || 'Binding'), el('code', '', item.task_id || 'Task'));
    head.append(title, el('span', `aefr-pill aefr-pill-${item.status || 'open'}`, stageLabel(item.status)));

    const grid = el('div', 'aefr-grid');
    grid.append(
      metric('Stage', stageLabel(item.stage), item.status === 'resolved' ? 'resolved' : 'warning'),
      metric('Failure code', item.failure_code || 'sandbox_execution_failed'),
      metric('Attempt', item.attempt || 1),
      metric('Retryable', item.retryable ? 'Yes' : 'No')
    );

    const action = el('div', 'aefr-action');
    action.append(el('span', '', 'Recommended correction'), el('p', '', item.recommended_action || 'Review the sandbox configuration.'));

    const footer = el('div', 'aefr-footer');
    footer.append(el('code', '', item.failure_id || ''));
    if (item.status === 'open') {
      const review = el('button', 'aefr-button', 'Start review');
      review.type = 'button';
      review.addEventListener('click', () => startReview(root, item));
      footer.appendChild(review);
    } else if (item.status === 'resolved') {
      footer.append(el('code', '', item.evidence_sha256 ? `Evidence ${item.evidence_sha256}` : 'Resolved'));
    }

    const details = document.createElement('details');
    details.className = 'aefr-details';
    const summary = document.createElement('summary');
    summary.textContent = 'Audit detail';
    const body = el('dl', 'aefr-detail-grid');
    [
      ['Occurred', item.occurred_at || '—'],
      ['Last reviewed', item.last_reviewed_at || '—'],
      ['Resolution', item.resolution_code || 'Pending'],
      ['Resolved at', item.resolved_at || '—'],
    ].forEach(([key, value]) => body.append(el('dt', '', key), el('dd', '', value)));
    details.append(summary, body);

    card.append(head, grid, action, footer, details);
    return card;
  }

  function renderFailures(root, payload) {
    const region = root.querySelector('[data-aefr-list]');
    region.replaceChildren();
    const failures = filteredFailures(payload);
    if (!failures.length) {
      region.append(el('div', 'aefr-empty', `No ${activeFilter === 'all' ? '' : activeFilter + ' '}sandbox failures for this client.`));
      return;
    }
    failures.forEach(item => region.appendChild(failureCard(root, item)));
  }

  function renderPayload(root, payload) {
    currentPayload = payload;
    const metrics = root.querySelector('[data-aefr-metrics]');
    metrics.replaceChildren(
      metric('Open', payload.open_count || 0, payload.open_count ? 'warning' : 'resolved'),
      metric('Reviewing', payload.reviewing_count || 0, payload.reviewing_count ? 'active' : ''),
      metric('Resolved', payload.resolved_count || 0, 'resolved'),
      metric('Total', payload.failure_count || 0)
    );
    renderFilters(root, payload);
    renderFailures(root, payload);
  }

  async function loadQueue(root, clientId, preserveStatus = false) {
    const normalized = String(clientId || '').trim();
    if (!normalized) {
      setStatus(root, 'Enter a client ID to review sandbox failures.', 'error');
      return;
    }
    currentClientId = normalized;
    if (!preserveStatus) setStatus(root, 'Loading sandbox failure review queue…');
    try {
      const payload = await jsonRequest(
        `/settings/admin/integration-tasks/${encodeURIComponent(normalized)}/sandbox-failures`
      );
      renderPayload(root, payload);
      if (!preserveStatus) setStatus(root, `Loaded ${payload.failure_count || 0} reviewable sandbox failure records.`, 'success');
    } catch (error) {
      setStatus(root, error?.message || 'Sandbox failure queue could not be loaded.', 'error');
    }
  }

  function buildRoot() {
    const root = el('section', 'aefr-root');
    root.id = ROOT_ID;
    root.setAttribute('aria-labelledby', 'aefr-title');

    const header = el('div', 'aefr-head');
    const copy = el('div', '');
    copy.append(
      el('span', 'aefr-eyebrow', 'Enterprise Integration · Sandbox operations'),
      el('h2', 'aefr-title', 'Failure review queue'),
      el('p', 'aefr-copy', 'Review safe failure classifications, guide corrections, and verify closure only through a successful customer sandbox retest. Raw errors and credentials are never shown here.')
    );
    copy.querySelector('.aefr-title').id = 'aefr-title';
    header.append(copy, el('span', 'aefr-pill aefr-pill-safe', 'Production blocked'));

    const controls = el('div', 'aefr-controls');
    const input = document.createElement('input');
    input.type = 'text';
    input.name = 'client_id';
    input.placeholder = 'Client ID';
    input.autocomplete = 'off';
    input.setAttribute('aria-label', 'Client ID for sandbox failure review');
    const load = el('button', 'aefr-button aefr-button-primary', 'Load review queue');
    load.type = 'button';
    load.addEventListener('click', () => loadQueue(root, input.value));
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        loadQueue(root, input.value);
      }
    });
    controls.append(input, load);

    const statusNode = el('div', 'aefr-status', 'Enter a client ID to inspect sandbox reliability.');
    statusNode.dataset.aefrStatus = 'true';
    statusNode.setAttribute('role', 'status');
    statusNode.setAttribute('aria-live', 'polite');

    const metrics = el('div', 'aefr-metrics');
    metrics.dataset.aefrMetrics = 'true';
    const filters = el('div', 'aefr-filters');
    filters.dataset.aefrFilters = 'true';
    const list = el('div', 'aefr-list');
    list.dataset.aefrList = 'true';

    const safety = el('div', 'aefr-safety');
    safety.setAttribute('role', 'note');
    safety.textContent = 'Start review changes review state only. It does not alter customer bindings, credentials, scopes, or production authority.';

    root.append(header, controls, statusNode, metrics, filters, safety, list);
    return root;
  }

  function mount() {
    const page = document.getElementById('page-admin-clients');
    if (!page || document.getElementById(ROOT_ID)) return;
    const root = buildRoot();
    const first = page.querySelector('.admin-dashboard-grid');
    if (first) first.insertAdjacentElement('afterend', root);
    else page.appendChild(root);
  }

  window.PMK_ADMIN_ENTERPRISE_FAILURE_REVIEW = { mount, loadQueue };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
  else mount();
})();
