(function () {
  const CRM_PRESETS = ['CRM-CONTEXT-01', 'CRM-SUMMARY-01', 'CRM-DRAFT-01'];
  const BUTTON_ID = 'admin-eval-prepare-complete-crm-bundle';
  const RESULT_ID = 'admin-eval-prepare-complete-crm-bundle-result';
  let running = false;

  function text(value) { return String(value ?? '').trim(); }

  function waitForPreset(presetId, timeoutMs = 90000) {
    return new Promise((resolve, reject) => {
      const started = Date.now();
      const poll = () => {
        const result = document.querySelector(`[data-owned-preset-result="${presetId}"]`);
        const value = text(result?.textContent);
        if (value.includes(`${presetId} READY.`)) return resolve(value);
        if (value.includes(`${presetId} remains BLOCKED:`)) return reject(new Error(value));
        if (Date.now() - started >= timeoutMs) return reject(new Error(`${presetId} preparation timed out.`));
        window.setTimeout(poll, 250);
      };
      poll();
    });
  }

  async function run() {
    if (running) return;
    const button = document.getElementById(BUTTON_ID);
    const result = document.getElementById(RESULT_ID);
    running = true;
    if (button) button.disabled = true;
    if (result) {
      result.className = 'admin-note';
      result.textContent = 'Preparing complete CRM bundle: Context → Summary → Draft. Grant creation remains locked until all three live proofs succeed.';
    }
    try {
      for (const presetId of CRM_PRESETS) {
        const presetButton = document.querySelector(`[data-owned-preset-run="${presetId}"]`);
        if (!presetButton) throw new Error(`${presetId} preparation control is unavailable.`);
        presetButton.click();
        await waitForPreset(presetId);
      }
      await window.PMK_ADMIN_EVALUATION_GRANTS?.refreshBindingCatalog?.();
      await window.PMK_ADMIN_EVALUATION_BINDING_COVERAGE_GUARD?.apply?.();
      if (result) {
        result.className = 'admin-note ok';
        result.innerHTML = '<strong>CRM BUNDLE READY.</strong> Context, Summary, and Draft bindings completed live proof. Verify all three canonical tasks and all three prepared bindings are selected before creating the grant.';
      }
    } catch (error) {
      if (result) {
        result.className = 'admin-note danger';
        result.textContent = `CRM bundle remains BLOCKED: ${error.message || error}`;
      }
    } finally {
      running = false;
      if (button) button.disabled = false;
    }
  }

  function render() {
    const cards = document.getElementById('admin-eval-owned-preset-cards');
    if (!cards || document.getElementById(BUTTON_ID)) return Boolean(cards);
    const panel = document.createElement('section');
    panel.className = 'card flat';
    panel.style.marginTop = 'var(--s-2)';
    panel.innerHTML = `
      <div><strong>Complete CRM evaluation bundle</strong></div>
      <div class="sh-sub">Runs all three CRM preparation proofs in order and keeps grant creation fail-closed until task ↔ binding coverage is complete.</div>
      <button id="${BUTTON_ID}" class="btn primary" type="button" style="margin-top:var(--s-2)">Prepare complete CRM bundle</button>
      <div id="${RESULT_ID}" class="admin-note" style="margin-top:var(--s-2)">No bundle proof run yet.</div>
    `;
    cards.parentElement?.insertBefore(panel, cards);
    document.getElementById(BUTTON_ID)?.addEventListener('click', run);
    return true;
  }

  function initialize() {
    if (render()) return;
    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      if (render() || attempts >= 100) window.clearInterval(timer);
    }, 150);
  }

  window.PMK_ADMIN_EVALUATION_CRM_BUNDLE = { initialize, run };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
})();
