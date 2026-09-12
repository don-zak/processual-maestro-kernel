(function () {
  const BINDING_CATALOG_ENDPOINT = '/settings/admin/evaluation-grants/binding-catalog';
  const RUNTIME_TASK_ENDPOINT = '/evaluation/runtime/task-execute';
  let bindingTaskById = new Map();
  let loading = null;
  let observer = null;

  function text(value) { return String(value ?? '').trim(); }

  function authHeaders(extra = {}) {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') return auth.headers(extra);
    return new Headers(extra);
  }

  function runtimeSelected() {
    const workspace = window.PMK_ADMIN_API_KEY_PROVISIONING_WORKSPACE;
    const endpoints = workspace && typeof workspace.selectedEndpoints === 'function'
      ? workspace.selectedEndpoints()
      : [];
    return Array.isArray(endpoints) && endpoints.some((item) =>
      text(item?.method).toUpperCase() === 'POST' && text(item?.path) === RUNTIME_TASK_ENDPOINT
    );
  }

  function selectedTasks() {
    return [...document.querySelectorAll('[data-eval-task]:checked')]
      .map((input) => text(input.value).toLowerCase())
      .filter(Boolean);
  }

  function selectedBindings() {
    return [...document.querySelectorAll('[data-eval-binding]:checked')]
      .map((input) => text(input.value))
      .filter(Boolean);
  }

  async function loadCatalog() {
    if (loading) return loading;
    loading = (async () => {
      const response = await fetch(BINDING_CATALOG_ENDPOINT, {
        method: 'GET',
        credentials: 'include',
        headers: authHeaders({ Accept: 'application/json' }),
      });
      if (!response.ok) throw new Error(`binding catalog HTTP ${response.status}`);
      const payload = await response.json();
      const items = Array.isArray(payload.bindings) ? payload.bindings : [];
      bindingTaskById = new Map(items.map((item) => [
        text(item.binding_id),
        text(item.task_id).toLowerCase(),
      ]).filter(([bindingId, taskId]) => bindingId && taskId));
    })().finally(() => { loading = null; });
    return loading;
  }

  function coverage() {
    const tasks = new Set(selectedTasks());
    const bindings = selectedBindings();
    const covered = new Set();
    const invalidBindings = [];
    bindings.forEach((bindingId) => {
      const taskId = bindingTaskById.get(bindingId);
      if (!taskId || !tasks.has(taskId)) invalidBindings.push(bindingId);
      else covered.add(taskId);
    });
    const missingTasks = [...tasks].filter((taskId) => !covered.has(taskId)).sort();
    return { missingTasks, invalidBindings };
  }

  function ensureCoverageNote(readiness) {
    if (!readiness) return null;
    let note = readiness.querySelector('[data-eval-binding-coverage-guard]');
    if (!note) {
      note = document.createElement('div');
      note.dataset.evalBindingCoverageGuard = 'true';
      note.style.marginTop = 'var(--s-2)';
      readiness.appendChild(note);
    }
    return note;
  }

  async function apply() {
    const button = document.getElementById('admin-eval-create');
    const readiness = document.getElementById('admin-eval-readiness');
    if (!button || !readiness) return;

    if (!runtimeSelected()) {
      delete button.dataset.bindingCoverageReady;
      const existing = readiness.querySelector('[data-eval-binding-coverage-guard]');
      if (existing) existing.remove();
      return;
    }

    try {
      await loadCatalog();
      const { missingTasks, invalidBindings } = coverage();
      const complete = missingTasks.length === 0 && invalidBindings.length === 0;
      button.dataset.bindingCoverageReady = complete ? 'true' : 'false';
      if (!complete) button.disabled = true;

      const note = ensureCoverageNote(readiness);
      if (!note) return;
      if (complete) {
        note.className = 'muted';
        note.textContent = 'Task ↔ prepared-binding coverage complete for every selected runtime task.';
      } else {
        note.className = 'admin-note danger';
        const parts = [];
        if (missingTasks.length) parts.push(`missing prepared binding coverage: ${missingTasks.join(', ')}`);
        if (invalidBindings.length) parts.push(`selected binding outside selected task envelope: ${invalidBindings.join(', ')}`);
        note.textContent = `Runtime grant remains LOCKED — ${parts.join(' · ')}`;
      }
    } catch (error) {
      button.disabled = true;
      button.dataset.bindingCoverageReady = 'false';
      const note = ensureCoverageNote(readiness);
      if (note) {
        note.className = 'admin-note danger';
        note.textContent = `Runtime grant remains LOCKED — unable to verify task ↔ binding coverage: ${error.message || error}`;
      }
    }
  }

  function schedule() { window.queueMicrotask(() => { apply(); }); }

  function initialize() {
    document.addEventListener('change', (event) => {
      const target = event.target instanceof Element ? event.target : null;
      if (target?.matches?.('[data-eval-task], [data-eval-binding], #admin-api-key-provisioning-mode')) schedule();
    });
    window.addEventListener('pmk-evaluation-selection-changed', schedule);
    window.addEventListener('pmk-api-key-access-selection-changed', schedule);
    window.addEventListener('pmk-api-key-category-changed', schedule);
    const host = document.getElementById('admin-evaluation-grants');
    if (host && !observer) {
      observer = new MutationObserver(schedule);
      observer.observe(host, { childList: true, subtree: true });
    }
    schedule();
    document.body.dataset.adminEvaluationBindingCoverageGuard = 'loaded';
  }

  window.PMK_ADMIN_EVALUATION_BINDING_COVERAGE_GUARD = { apply, initialize };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
})();
