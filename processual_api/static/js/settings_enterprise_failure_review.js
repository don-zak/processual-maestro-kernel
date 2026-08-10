(() => {
  'use strict';

  const ROOT_ID = 'sefr-sandbox-reliability';
  const FAILURES_ENDPOINT = '/settings/enterprise-integration/sandbox-failures';
  const BINDINGS_ENDPOINT = '/settings/enterprise-integration/endpoint-bindings';
  let observer = null;
  let loading = false;

  function el(tag, className, copy) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (copy !== undefined) node.textContent = String(copy);
    return node;
  }

  function stageLabel(value) {
    return String(value || 'execution').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  function timeLabel(value) {
    if (!value) return 'Not recorded';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
  }

  function pill(copy, state) {
    const node = el('span', `sefr-pill sefr-pill-${state || 'neutral'}`, copy);
    return node;
  }

  function metric(label, value, state) {
    const node = el('div', `sefr-metric sefr-metric-${state || 'neutral'}`);
    node.append(el('span', 'sefr-metric-label', label), el('strong', 'sefr-metric-value', value));
    return node;
  }

  function renderEmpty(region) {
    const empty = el('div', 'sefr-empty');
    empty.append(
      el('strong', '', 'No sandbox failures need attention.'),
      el('p', '', 'Successful proof runs remain available in the evidence history. New failures will appear here with a safe reason code and a corrective action.')
    );
    region.appendChild(empty);
  }

  function renderFailure(item) {
    const card = el('article', 'sefr-card');
    card.dataset.status = item.status || 'open';

    const head = el('div', 'sefr-card-head');
    const titleWrap = el('div', 'sefr-card-title-wrap');
    const title = el('strong', 'sefr-card-title', item.binding_id || 'Sandbox binding');
    const task = el('code', 'sefr-code', item.task_id || 'unknown task');
    titleWrap.append(title, task);
    const state = pill(stageLabel(item.status || 'open'), item.status || 'open');
    head.append(titleWrap, state);

    const flow = el('div', 'sefr-flow');
    const stages = ['authorization', 'request_mapping', 'destination', 'credential', 'transport', 'response', 'response_mapping', 'task_injection'];
    const failedIndex = Math.max(0, stages.indexOf(item.stage));
    stages.forEach((stage, index) => {
      const step = el('span', 'sefr-flow-step', stageLabel(stage));
      if (index < failedIndex) step.dataset.state = 'passed';
      else if (index === failedIndex) step.dataset.state = 'failed';
      else step.dataset.state = 'pending';
      flow.appendChild(step);
    });

    const summary = el('div', 'sefr-summary-grid');
    summary.append(
      metric('Stage', stageLabel(item.stage), item.status === 'resolved' ? 'resolved' : 'warning'),
      metric('Failure code', item.failure_code || 'sandbox_execution_failed'),
      metric('Attempt', item.attempt || 1),
      metric('Occurred', timeLabel(item.occurred_at))
    );

    const action = el('div', 'sefr-action');
    action.append(
      el('span', 'sefr-action-label', 'Recommended correction'),
      el('p', 'sefr-action-copy', item.recommended_action || 'Review the sandbox configuration before retrying.')
    );

    const details = document.createElement('details');
    details.className = 'sefr-details';
    const summaryNode = document.createElement('summary');
    summaryNode.textContent = 'Review technical references';
    const detailGrid = el('dl', 'sefr-detail-grid');
    const rows = [
      ['Failure ID', item.failure_id],
      ['Retryable', item.retryable ? 'Yes' : 'No'],
      ['Last reviewed', timeLabel(item.last_reviewed_at)],
      ['Resolution', item.resolution_code || 'Pending'],
      ['Resolved at', timeLabel(item.resolved_at)],
      ['Evidence SHA-256', item.evidence_sha256 || 'Pending successful retest'],
    ];
    rows.forEach(([label, value]) => {
      detailGrid.append(el('dt', '', label), el('dd', '', value));
    });
    details.append(summaryNode, detailGrid);

    card.append(head, flow, summary, action, details);
    return card;
  }

  function render(root, payload) {
    const metrics = root.querySelector('[data-sefr-metrics]');
    metrics.replaceChildren(
      metric('Open', payload.open_count || 0, payload.open_count ? 'warning' : 'resolved'),
      metric('Reviewing', payload.reviewing_count || 0, payload.reviewing_count ? 'active' : 'neutral'),
      metric('Resolved', payload.resolved_count || 0, 'resolved'),
      metric('Total attempts', payload.failure_count || 0)
    );

    const region = root.querySelector('[data-sefr-list]');
    region.replaceChildren();
    const failures = [...(payload.failures || [])].reverse();
    if (!failures.length) {
      renderEmpty(region);
      return;
    }
    failures.forEach(item => region.appendChild(renderFailure(item)));
  }

  function buildRoot() {
    const root = el('section', 'sefr-root');
    root.id = ROOT_ID;
    root.setAttribute('aria-labelledby', 'sefr-title');

    const head = el('div', 'sefr-head');
    const copy = el('div', '');
    const eyebrow = el('span', 'sefr-eyebrow', 'Failure review & recovery');
    const title = el('h4', 'sefr-title', 'Sandbox reliability');
    title.id = 'sefr-title';
    const description = el(
      'p',
      'sefr-copy',
      'Every failed sandbox proof is converted into a reviewable, secret-free correction record. A successful retest closes the related failures and links them to the new evidence digest.'
    );
    copy.append(eyebrow, title, description);
    const guard = el('div', 'sefr-guard');
    guard.append(pill('Sandbox only', 'active'), pill('Raw errors hidden', 'resolved'), pill('Production blocked', 'blocked'));
    head.append(copy, guard);

    const metrics = el('div', 'sefr-metrics');
    metrics.dataset.sefrMetrics = 'true';

    const note = el('div', 'sefr-note');
    note.setAttribute('role', 'note');
    note.append(
      el('strong', '', 'Correction loop'),
      el('span', '', ' Identify the failed stage → apply the recommended change → rerun the live sandbox proof → verify the new SHA-256 evidence.')
    );

    const list = el('div', 'sefr-list');
    list.dataset.sefrList = 'true';
    list.setAttribute('aria-live', 'polite');

    root.append(head, metrics, note, list);
    return root;
  }

  async function refresh(force = false) {
    const endpointWorkspace = document.getElementById('see-endpoint-bindings');
    if (!endpointWorkspace || loading) return;
    let root = document.getElementById(ROOT_ID);
    if (!root) {
      root = buildRoot();
      endpointWorkspace.insertAdjacentElement('afterend', root);
    } else if (!force && root.dataset.loaded === 'true') {
      return;
    }

    loading = true;
    try {
      const payload = await CLIENT.get(FAILURES_ENDPOINT);
      render(root, payload);
      root.dataset.loaded = 'true';
    } catch (error) {
      const region = root.querySelector('[data-sefr-list]');
      region.replaceChildren(el('p', 'sefr-error', 'Failure review history could not be loaded. Existing endpoint configuration remains unchanged.'));
    } finally {
      loading = false;
    }
  }

  function watch() {
    if (observer || !document.body) return;
    observer = new MutationObserver(() => {
      if (document.getElementById('see-endpoint-bindings')) refresh(false);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function init() {
    watch();
    refresh(true);
  }

  window.PMK_SETTINGS_ENTERPRISE_FAILURE_REVIEW = { init, refresh };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
