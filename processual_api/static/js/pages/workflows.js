PAGES.workflows = (() => {
  async function refresh() {
    const countEl = document.getElementById('wf-count');
    if (countEl) countEl.textContent = 'Connected to backend';
  }

  function init() {
    document.getElementById('wf-create-btn')?.addEventListener('click', () => {
      document.getElementById('wf-create-form').style.display = 'block';
    });
    document.getElementById('wf-cancel-create')?.addEventListener('click', () => {
      document.getElementById('wf-create-form').style.display = 'none';
    });
    document.getElementById('wf-do-create')?.addEventListener('click', async () => {
      const id = document.getElementById('wf-new-id').value || 'wf_' + Date.now().toString(36);
      const goal = document.getElementById('wf-new-goal').value || 'Untitled workflow';
      const steps = parseInt(document.getElementById('wf-new-steps').value) || 3;
      try {
        const res = await WORKFLOWS_ADAPTER.create({ workflow_id: id, goal, steps: Array.from({ length: steps }, (_, i) => ({ step: i + 1, action: 'process', description: goal + ' step ' + (i + 1) })) });
        APP.showToast('Workflow ' + id + ' created', 'success');
        document.getElementById('wf-create-form').style.display = 'none';
      } catch (e) {
        APP.showToast('Workflow creation failed: ' + (e.detail || e.message), 'error');
      }
    });
  }

  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
  return { refresh };
})();
