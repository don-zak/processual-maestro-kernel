(function () {
  const CATALOG_ENDPOINT = '/settings/admin/evaluation-grants/binding-catalog';
  let catalog = [];
  let loading = null;
  let applying = false;

  function text(value) { return String(value ?? '').trim(); }

  function authHeaders(extra = {}) {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') return auth.headers(extra);
    return new Headers(extra);
  }

  function selectedTasks() {
    return [...document.querySelectorAll('[data-eval-task]:checked')]
      .map((input) => text(input.value).toLowerCase())
      .filter(Boolean);
  }

  async function loadCatalog(force = false) {
    if (loading) return loading;
    if (catalog.length && !force) return catalog;
    loading = (async () => {
      const response = await fetch(CATALOG_ENDPOINT, {
        method: 'GET',
        credentials: 'include',
        headers: authHeaders({ Accept: 'application/json' }),
      });
      if (!response.ok) throw new Error(`binding catalog HTTP ${response.status}`);
      const payload = await response.json();
      catalog = Array.isArray(payload.bindings) ? payload.bindings : [];
      return catalog;
    })().finally(() => { loading = null; });
    return loading;
  }

  async function apply({ forceCatalog = false } = {}) {
    if (applying) return;
    applying = true;
    try {
      await loadCatalog(forceCatalog);
      const tasks = new Set(selectedTasks());
      if (!tasks.size) return;

      const selectableByTask = new Map();
      catalog.forEach((item) => {
        const taskId = text(item?.task_id).toLowerCase();
        const bindingId = text(item?.binding_id);
        if (!tasks.has(taskId) || !bindingId || item?.selectable !== true) return;
        const values = selectableByTask.get(taskId) || [];
        values.push(bindingId);
        selectableByTask.set(taskId, values);
      });

      let changed = false;
      tasks.forEach((taskId) => {
        const candidates = selectableByTask.get(taskId) || [];
        // Never guess between multiple prepared bindings. Auto-select only when
        // the sealed selected task has exactly one safe, selectable candidate.
        if (candidates.length !== 1) return;
        const bindingId = candidates[0];
        const input = [...document.querySelectorAll('[data-eval-binding]')]
          .find((node) => text(node.value) === bindingId);
        if (!input || input.disabled || input.checked) return;
        input.checked = true;
        changed = true;
      });

      if (changed) {
        window.dispatchEvent(new CustomEvent('pmk-evaluation-selection-changed'));
      }
    } catch {
      // Main readiness remains fail-closed and shows the authoritative blocker.
    } finally {
      applying = false;
    }
  }

  function schedule(options) {
    window.queueMicrotask(() => { apply(options); });
  }

  function initialize() {
    document.addEventListener('change', (event) => {
      const target = event.target instanceof Element ? event.target : null;
      if (target?.matches?.('[data-eval-task]')) schedule();
    });
    window.addEventListener('pmk-evaluation-selection-changed', () => schedule());
    window.addEventListener('pmk-evaluation-grant-updated', () => schedule({ forceCatalog: true }));
    window.addEventListener('pmk-evaluation-bindings-refreshed', () => schedule({ forceCatalog: true }));
    schedule({ forceCatalog: true });
    document.body.dataset.adminEvaluationBindingAutoselect = 'loaded';
  }

  window.PMK_ADMIN_EVALUATION_BINDING_AUTOSELECT = {
    apply,
    refresh: () => apply({ forceCatalog: true }),
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
})();
