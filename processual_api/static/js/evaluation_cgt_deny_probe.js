(function () {
  const PROBE_ENDPOINT = '/evaluation/runtime/governance-deny-probe';
  const STATUS_ENDPOINT = '/evaluation/runtime/status';
  const BUTTON_ID = 'run-cgt-deny-probe';
  const RESULT_ID = 'cgt-deny-probe-result';

  const text = (value) => String(value ?? '').trim();

  function currentKey() {
    return text(document.getElementById('api-key')?.value);
  }

  function headers(apiKey) {
    return {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    };
  }

  async function fetchJson(path, apiKey, options = {}) {
    const response = await fetch(path, {
      method: options.method || 'GET',
      credentials: 'omit',
      cache: 'no-store',
      headers: headers(apiKey),
      ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}),
    });
    const raw = await response.text();
    let payload = {};
    if (raw) {
      try { payload = JSON.parse(raw); } catch { payload = { detail: raw }; }
    }
    return { response, payload };
  }

  function quotaUsed(payload) {
    return Number(payload?.quota?.used ?? NaN);
  }

  function render(payload, beforeUsed, afterUsed) {
    const target = document.getElementById(RESULT_ID);
    if (!target) return;
    const detail = payload?.detail && typeof payload.detail === 'object' ? payload.detail : payload;
    const passed = Boolean(
      detail?.code === 'evaluation_cgt_governance_denied'
      && detail?.probe_id === 'CGT-DENY-01'
      && detail?.disposition === 'deny'
      && detail?.governance_evidence_persisted === true
      && detail?.quota_consumed === false
      && detail?.network_request_executed === false
      && detail?.production_allowed === false
      && detail?.authority_expansion_allowed === false
      && Number.isFinite(beforeUsed)
      && Number.isFinite(afterUsed)
      && beforeUsed === afterUsed
    );
    target.className = passed ? 'notice ok' : 'notice bad';
    target.textContent = passed
      ? `CGT-DENY-01 PASS · deny before admission · quota +0 (${beforeUsed} → ${afterUsed}) · network not executed · governance evidence persisted · decision ${text(detail.decision_id)}`
      : `CGT-DENY-01 did not satisfy the complete proof contract. ${JSON.stringify(detail)}`;
  }

  async function run() {
    const button = document.getElementById(BUTTON_ID);
    const target = document.getElementById(RESULT_ID);
    const apiKey = currentKey();
    if (!apiKey) {
      if (target) {
        target.className = 'notice bad';
        target.textContent = 'Connect an active Evaluation key before running the governance denial proof.';
      }
      return;
    }
    if (button) button.disabled = true;
    if (target) {
      target.className = 'notice';
      target.textContent = 'Running governance-only deny proof. No executable provider request will be created.';
    }
    try {
      const before = await fetchJson(STATUS_ENDPOINT, apiKey);
      if (!before.response.ok) throw new Error('Unable to read authoritative quota before the proof.');
      const beforeUsed = quotaUsed(before.payload);
      const idempotencyKey = `cgt-deny-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const denied = await fetchJson(PROBE_ENDPOINT, apiKey, {
        method: 'POST',
        body: { probe_id: 'CGT-DENY-01', idempotency_key: idempotencyKey },
      });
      if (denied.response.status !== 403) {
        throw new Error(`Expected governed deny HTTP 403, received HTTP ${denied.response.status}.`);
      }
      const after = await fetchJson(STATUS_ENDPOINT, apiKey);
      if (!after.response.ok) throw new Error('Unable to read authoritative quota after the proof.');
      render(denied.payload, beforeUsed, quotaUsed(after.payload));
    } catch (error) {
      if (target) {
        target.className = 'notice bad';
        target.textContent = `CGT deny proof failed safely: ${error.message || error}`;
      }
    } finally {
      if (button) button.disabled = false;
    }
  }

  function initialize() {
    document.getElementById(BUTTON_ID)?.addEventListener('click', run);
  }

  window.PMK_EVALUATION_CGT_DENY_PROBE = { run };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
})();
