PAGES.institution = (() => {
  'use strict';

  const TRACKS = [
    {
      key: 'camara',
      caseType: 'camara_integration_case',
      title: 'CAMARA / GSMA Open Gateway',
      subtitle: 'Capability exposure, consent references, sandbox endpoints, and conformance evidence.',
    },
    {
      key: 'tmforum',
      caseType: 'tmforum_integration_case',
      title: 'TM Forum Open APIs',
      subtitle: 'Open API versions, schemas, CTK evidence, and operator deviations.',
    },
    {
      key: 'operator',
      caseType: 'operator_integration_case',
      title: 'Operator-specific integration',
      subtitle: 'DNS, TLS, OAuth/OIDC, callbacks, allowlists, and sandbox scope.',
    },
  ];

  const state = {
    account: null,
    subscription: null,
    cases: [],
    legacyRequests: [],
    loading: true,
    busy: '',
    message: '',
    error: '',
  };

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[char]);
  }

  function arr(value) { return Array.isArray(value) ? value : []; }
  function pill(text, tone) { return `<span class="iw18-pill ${tone || ''}">${esc(text)}</span>`; }
  function trackDef(key) { return TRACKS.find((track) => track.key === key); }
  function caseForTrack(key) { return state.cases.find((item) => item.integration_track === key) || null; }

  function legacyCount() {
    return state.legacyRequests.filter((request) => String(request.message_preview || '').includes('[STAGE18_INTEGRATION_CASE]')).length;
  }

  async function load() {
    state.loading = true;
    state.error = '';
    render();
    const results = await Promise.allSettled([
      CLIENT.get('/auth/me'),
      CLIENT.get('/settings/subscription'),
      CLIENT.get('/settings/client/integration-cases'),
      CLIENT.get('/settings/client-requests'),
    ]);
    state.account = results[0].status === 'fulfilled' ? results[0].value : null;
    state.subscription = results[1].status === 'fulfilled' ? results[1].value : null;
    state.cases = results[2].status === 'fulfilled' ? arr(results[2].value?.cases) : [];
    state.legacyRequests = results[3].status === 'fulfilled' ? arr(results[3].value?.latest_requests) : [];
    state.error = results.filter((item) => item.status === 'rejected')
      .map((item) => item.reason?.detail || item.reason?.message || 'Unavailable').join(' · ');
    state.loading = false;
    state.busy = '';
    render();
  }

  async function createTrackCase(trackKey) {
    const track = trackDef(trackKey);
    if (!track || state.busy) return;
    state.busy = `create:${trackKey}`;
    state.message = `Creating ${track.title} workspace…`;
    state.error = '';
    render();
    try {
      const result = await CLIENT.post('/settings/client/integration-cases', {
        integration_track: trackKey,
        title: track.title,
      });
      state.message = result.status === 'existing'
        ? `${track.title} already has an active operational case.`
        : `${track.title} operational case created.`;
      await load();
    } catch (error) {
      state.busy = '';
      state.message = '';
      state.error = error?.detail || error?.message || 'Case creation failed.';
      render();
    }
  }

  async function saveTask(caseId, taskId) {
    const reference = document.querySelector(`[data-task-reference="${caseId}:${taskId}"]`)?.value.trim() || '';
    const status = document.querySelector(`[data-task-status="${caseId}:${taskId}"]`)?.value || 'in_progress';
    state.busy = `task:${caseId}:${taskId}`;
    state.message = 'Saving task progress…';
    state.error = '';
    render();
    try {
      await CLIENT.patch(
        `/settings/client/integration-cases/${encodeURIComponent(caseId)}/tasks/${encodeURIComponent(taskId)}`,
        { status, reference, note: '' }
      );
      state.message = 'Task progress saved.';
      await load();
    } catch (error) {
      state.busy = '';
      state.message = '';
      state.error = error?.detail || error?.message || 'Task update failed.';
      render();
    }
  }

  async function validateCase(caseId) {
    state.busy = `validate:${caseId}`;
    state.message = 'Running automated validation…';
    state.error = '';
    render();
    try {
      const result = await CLIENT.post(`/settings/client/integration-cases/${encodeURIComponent(caseId)}/validate`, {});
      state.message = result.status === 'passed'
        ? 'Validation passed. The case is ready for the precise supervisor decision gate.'
        : `Validation blocked: ${(result.blockers || []).join(' · ')}`;
      await load();
    } catch (error) {
      state.busy = '';
      state.message = '';
      state.error = error?.detail || error?.message || 'Validation failed.';
      render();
    }
  }

  function taskStatusTone(status) {
    if (status === 'completed') return 'good';
    if (status === 'blocked') return 'bad';
    return 'warn';
  }

  function taskRows(item) {
    return `<div class="iw18-task-list">${arr(item.tasks).map((task) => {
      const key = `${item.case_id}:${task.task_id}`;
      const busy = state.busy === `task:${key}`;
      const placeholder = task.input_kind === 'url' ? 'https://sandbox.example/reference' : 'Client-safe reference or document ID';
      return `<div class="iw18-task">
        <div class="iw18-task-head"><strong>${esc(task.label)}</strong>${pill(task.status, taskStatusTone(task.status))}</div>
        <div class="iw18-task-grid">
          <input class="iw18-input" data-task-reference="${esc(key)}" value="${esc(task.reference || '')}" placeholder="${esc(placeholder)}" autocomplete="off">
          <select class="iw18-select" data-task-status="${esc(key)}">
            ${['not_started', 'in_progress', 'completed', 'blocked'].map((status) => `<option value="${status}" ${task.status === status ? 'selected' : ''}>${status.replaceAll('_', ' ')}</option>`).join('')}
          </select>
        </div>
        <div class="iw18-task-actions">
          <button class="iw18-button ghost" data-save-task="${esc(key)}" ${busy ? 'disabled' : ''}>${busy ? 'Saving…' : 'Save task'}</button>
          <span class="iw18-validation ${esc(task.validation || '')}">Validation: ${esc(task.validation || 'not checked')}</span>
        </div>
      </div>`;
    }).join('')}</div>`;
  }

  function trackCard(track) {
    const item = caseForTrack(track.key);
    if (!item) {
      return `<section class="iw18-panel" data-integration-track="${track.key}">
        <h2>${esc(track.title)}</h2><small>${esc(track.subtitle)}</small>
        <div class="iw18-empty" style="margin-top:.85rem">No operational case yet. Create one to begin technical intake and automated validation.</div>
        <div class="iw18-toolbar"><button class="iw18-button" data-create-track="${track.key}" ${state.busy ? 'disabled' : ''}>Create operational case</button></div>
      </section>`;
    }

    const validateBusy = state.busy === `validate:${item.case_id}`;
    return `<section class="iw18-panel" data-integration-track="${track.key}">
      <div class="iw18-task-head"><div><h2>${esc(track.title)}</h2><small>${esc(track.subtitle)}</small></div>${pill(item.status, item.status === 'ready_for_review' ? 'good' : 'warn')}</div>
      <div class="iw18-case-meta">${pill(item.phase, 'warn')}${pill(`${item.progress_percent}% complete`, item.progress_percent === 100 ? 'good' : 'warn')}</div>
      <div class="iw18-case-id">Case ID: ${esc(item.case_id)}</div>
      <div class="iw18-progress"><span style="width:${Number(item.progress_percent || 0)}%"></span></div>
      ${taskRows(item)}
      <div class="iw18-toolbar">
        <button class="iw18-button" data-validate-case="${esc(item.case_id)}" ${validateBusy ? 'disabled' : ''}>${validateBusy ? 'Validating…' : 'Run automated validation'}</button>
      </div>
    </section>`;
  }

  function registry() {
    if (!state.cases.length) return '<div class="iw18-empty">No operational integration cases have been created.</div>';
    return `<div class="iw18-timeline">${state.cases.map((item, index) => `
      <div class="iw18-step"><b>${index + 1}</b><div><strong>${esc(item.case_type)}</strong>
      <span>${esc(item.case_id)} · ${esc(item.phase)} · ${esc(item.progress_percent)}%</span></div>
      ${pill(item.status, item.status === 'ready_for_review' ? 'good' : 'warn')}</div>`).join('')}</div>`;
  }

  function summary() {
    const total = state.cases.length;
    const ready = state.cases.filter((item) => item.status === 'ready_for_review').length;
    const blocked = state.cases.filter((item) => String(item.status).includes('blocked')).length;
    const average = total ? Math.round(state.cases.reduce((sum, item) => sum + Number(item.progress_percent || 0), 0) / total) : 0;
    return `<div class="iw18-summary-grid">
      <div class="iw18-summary"><span>Operational cases</span><strong>${total}</strong></div>
      <div class="iw18-summary"><span>Average progress</span><strong>${average}%</strong></div>
      <div class="iw18-summary"><span>Ready for decision</span><strong>${ready}</strong></div>
      <div class="iw18-summary"><span>Blocked</span><strong>${blocked}</strong></div>
    </div>`;
  }

  function render() {
    const root = document.getElementById('institution-workspace-root');
    if (!root) return;
    if (state.loading) {
      root.innerHTML = '<div class="iw18-empty">Loading enterprise integration workspace…</div>';
      return;
    }
    const plan = String(state.subscription?.plan || state.subscription?.plan_id || 'starter');
    const eligible = /enterprise/.test(plan.toLowerCase());
    root.innerHTML = `<div class="iw18-shell">
      <section class="iw18-hero">
        <div class="iw18-eyebrow">Enterprise workspace</div>
        <h1>${esc(state.account?.organization_name || 'Enterprise integration operations')}</h1>
        <p>Complete technical intake, save client-safe references, and run automated validation before any supervisor decision. Routine preparation remains self-service.</p>
        <div class="iw18-status">${pill(eligible ? 'Enterprise eligible' : `Current plan: ${plan}`, eligible ? 'good' : 'warn')}${pill('Operational task tracking', 'good')}${pill('No raw secrets', 'good')}${pill('Production blocked', 'warn')}</div>
        ${summary()}
      </section>

      ${state.message ? `<div class="iw18-empty">${esc(state.message)}</div>` : ''}
      ${state.error ? `<div class="iw18-empty" style="color:#fca5a5">${esc(state.error)}</div>` : ''}

      <section class="iw18-panel">
        <h2>Execution tracks</h2>
        <small>Create only the tracks your institution needs. Each task is persisted and validated independently.</small>
        ${legacyCount() ? `<div class="iw18-empty" style="margin-top:.8rem">${legacyCount()} earlier request-based case(s) remain in history. New work uses the operational case workflow below.</div>` : ''}
      </section>

      <div class="iw18-track-grid">${TRACKS.map(trackCard).join('')}</div>

      <div class="iw18-grid">
        <section class="iw18-panel"><h2>Case registry</h2><small>Formal operational cases and their real progress.</small>${registry()}</section>
        <section class="iw18-panel"><h2>Approval boundary</h2><small>Supervisor involvement begins only after automated validation passes.</small>
          <div class="iw18-action"><strong>Self-service</strong><span>Create case, complete tasks, save references, and run validation.</span></div>
          <div class="iw18-action"><strong>Supervisor decision</strong><span>Write scopes, security exceptions, sandbox approval, and production activation.</span></div>
          <div class="iw18-status">${pill('production_allowed=false', 'warn')}${pill('runtime_connector_approved=false', 'warn')}${pill('raw_secret_visible=false', 'good')}</div>
          <div class="iw18-toolbar"><button class="iw18-button ghost" data-open-settings>Open Settings operations</button></div>
        </section>
      </div>
    </div>`;

    root.querySelectorAll('[data-create-track]').forEach((button) => button.addEventListener('click', () => createTrackCase(button.dataset.createTrack)));
    root.querySelectorAll('[data-save-task]').forEach((button) => {
      const [caseId, taskId] = button.dataset.saveTask.split(':');
      button.addEventListener('click', () => saveTask(caseId, taskId));
    });
    root.querySelectorAll('[data-validate-case]').forEach((button) => button.addEventListener('click', () => validateCase(button.dataset.validateCase)));
    root.querySelectorAll('[data-open-settings]').forEach((button) => button.addEventListener('click', () => document.querySelector('.nav-btn[data-page="settings"]')?.click()));
  }

  return { init: load, refresh: load, createTrackCase, saveTask, validateCase };
})();
