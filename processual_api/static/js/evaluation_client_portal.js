(function () {
  let apiKey = '';
  let pollTimer = null;
  let runtimeState = {
    credentialStatus: 'disconnected',
    quotaRemaining: 0,
    executing: false,
    lastQuotaUsed: null,
  };

  const $ = (id) => document.getElementById(id);
  const text = (value) => String(value ?? '');

  function authHeaders() {
    return {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    };
  }

  function setMessage(message, kind = '') {
    const target = $('message');
    target.textContent = message;
    target.className = `notice ${kind}`.trim();
  }

  function statusClass(status) {
    const value = text(status).toLowerCase();
    if (['active', 'succeeded', 'persisted'].includes(value)) return 'value ok';
    if (['executing', 'low', 'pending'].includes(value)) return 'value warn';
    if (['failed', 'revoked', 'expired', 'quota_exhausted', 'exhausted'].includes(value)) return 'value bad';
    return 'value';
  }

  function canExecute() {
    return Boolean(
      apiKey
      && runtimeState.credentialStatus === 'active'
      && Number(runtimeState.quotaRemaining) > 0
      && !runtimeState.executing
    );
  }

  function syncExecuteButton() {
    $('execute').disabled = !canExecute();
  }

  async function request(path, options = {}) {
    if (!apiKey) throw new Error('Evaluation API key is required.');
    const response = await fetch(path, {
      ...options,
      headers: { ...authHeaders(), ...(options.headers || {}) },
      credentials: 'omit',
      cache: 'no-store',
    });
    const raw = await response.text();
    let data = {};
    if (raw) {
      try { data = JSON.parse(raw); } catch { data = { detail: raw }; }
    }
    if (!response.ok) {
      throw new Error(text(data.detail || data.message || `HTTP ${response.status}`));
    }
    return data;
  }

  function renderChips(id, values, emptyText) {
    const target = $(id);
    const safeValues = Array.isArray(values) ? values.filter(Boolean) : [];
    target.innerHTML = '';
    if (!safeValues.length) {
      const chip = document.createElement('span');
      chip.className = 'scope-chip';
      chip.textContent = emptyText;
      target.appendChild(chip);
      return;
    }
    safeValues.forEach((value) => {
      const chip = document.createElement('span');
      chip.className = 'scope-chip';
      chip.textContent = text(value);
      target.appendChild(chip);
    });
  }

  function resetStages() {
    ['stage-admitted', 'stage-executing', 'stage-outcome', 'stage-evidence'].forEach((id) => {
      $(id).className = 'stage';
    });
  }

  function renderStages(latest) {
    resetStages();
    if (!latest) return;
    $('stage-admitted').className = 'stage done';
    if (latest.status === 'executing') {
      $('stage-executing').className = 'stage current';
      return;
    }
    $('stage-executing').className = 'stage done';
    if (latest.status === 'succeeded' || latest.status === 'failed') {
      $('stage-outcome').className = latest.status === 'failed' ? 'stage current' : 'stage done';
    }
    if (latest.evidence_persisted) {
      $('stage-evidence').className = 'stage done';
    } else if (latest.status === 'succeeded') {
      $('stage-evidence').className = 'stage current';
    }
  }

  function buildCustomerReport(payload) {
    const quota = payload.quota || {};
    const latest = payload.latest_execution || null;
    return {
      report_type: 'external_evaluation_customer_receipt',
      credential_status: payload.credential_status || 'unknown',
      evaluation_type: payload.evaluation_type || null,
      grant_id: payload.grant_id || null,
      api_key_id: payload.api_key_id || null,
      api_key_prefix: payload.api_key_prefix || null,
      expires_at: payload.expires_at || null,
      quota: {
        semantics: 'admitted_execution',
        limit: quota.limit ?? 0,
        used: quota.used ?? 0,
        remaining: quota.remaining ?? 0,
        status_reads_consume: 0,
        idempotent_replays_consume: 0,
      },
      allowed_task_ids: Array.isArray(payload.allowed_task_ids) ? payload.allowed_task_ids : [],
      allowed_binding_ids: Array.isArray(payload.allowed_binding_ids) ? payload.allowed_binding_ids : [],
      latest_execution: latest,
      subscription_required: false,
      production_allowed: false,
      raw_api_key_included: false,
      raw_task_input_included: false,
      qualification_decision: 'operator_controlled',
    };
  }

  function renderStatus(payload) {
    const quota = payload.quota || {};
    const latest = payload.latest_execution || null;
    runtimeState.credentialStatus = text(payload.credential_status || 'unknown');
    runtimeState.quotaRemaining = Number(quota.remaining ?? 0);

    $('credential').textContent = text(payload.credential_status || 'unknown');
    $('credential').className = statusClass(payload.credential_status);
    $('type').textContent = text(payload.evaluation_type || '—').toUpperCase();
    $('quota-used').textContent = `${text(quota.used ?? 0)} / ${text(quota.limit ?? 0)}`;
    $('quota-remaining').textContent = text(quota.remaining ?? 0);
    $('quota-remaining').className = statusClass(quota.warning);
    $('grant-id').textContent = text(payload.grant_id || '—');
    $('key-id').textContent = [payload.api_key_id, payload.api_key_prefix].filter(Boolean).join(' · ') || '—';
    $('expires-at').textContent = text(payload.expires_at || '—');

    renderChips('allowed-tasks', payload.allowed_task_ids, 'No canonical tasks exposed by this grant.');
    renderChips('allowed-bindings', payload.allowed_binding_ids, 'No prepared binding required by this grant.');

    const limit = Number(quota.limit || 0);
    const used = Number(quota.used || 0);
    const pct = limit > 0 ? Math.min(100, Math.max(0, (used / limit) * 100)) : 0;
    $('quota-bar').style.width = `${pct}%`;
    $('quota-caption').textContent = `${used} of ${limit} admitted executions used · ${quota.remaining ?? 0} remaining · status checks and idempotent replays consume 0 units.`;

    renderStages(latest);
    if (latest) {
      $('execution-state').textContent = text(latest.status || 'unknown');
      $('execution-state').className = statusClass(latest.status);
      $('execution-meta').textContent = `${text(latest.task_id || '')} · ${text(latest.binding_id || '')} · ${text(latest.execution_id || latest.record_id || '')} · accepted ${text(latest.accepted_at || 'n/a')}`;
      const evidenceState = latest.evidence_persisted ? 'persisted' : latest.status === 'failed' ? 'failed' : 'pending';
      $('evidence-state').textContent = evidenceState;
      $('evidence-state').className = statusClass(evidenceState);
      $('evidence-meta').textContent = latest.evidence_sha256 ? `sha256 ${latest.evidence_sha256}` : text(latest.failure_code || 'Awaiting durable evidence.');
    } else {
      $('execution-state').textContent = 'none';
      $('execution-state').className = 'value';
      $('execution-meta').textContent = 'No admitted execution yet.';
      $('evidence-state').textContent = '—';
      $('evidence-state').className = 'value';
      $('evidence-meta').textContent = '';
    }

    if (runtimeState.lastQuotaUsed === null) {
      $('quota-effect').textContent = '0';
      $('quota-effect-meta').textContent = 'Status connection/read only: +0 quota.';
    }
    runtimeState.lastQuotaUsed = used;
    $('customer-report').textContent = JSON.stringify(buildCustomerReport(payload), null, 2);
    syncExecuteButton();
  }

  async function refreshStatus({ preserveQuotaEffect = false } = {}) {
    try {
      const payload = await request('/evaluation/runtime/status');
      renderStatus(payload);
      if (!preserveQuotaEffect && !runtimeState.executing) {
        $('quota-effect').textContent = '0';
        $('quota-effect-meta').textContent = 'Status refresh: +0 quota.';
      }
      setMessage('Connected. This bounded dashboard is read-only until you submit an authorized task; status reads consume +0 quota.', 'ok');
      return payload;
    } catch (error) {
      runtimeState.credentialStatus = 'unavailable';
      runtimeState.quotaRemaining = 0;
      syncExecuteButton();
      setMessage(`Unable to read evaluation status: ${error.message || error}`, 'bad');
      throw error;
    }
  }

  function nextIdempotencyKey() {
    const bytes = new Uint32Array(4);
    crypto.getRandomValues(bytes);
    return `eval-${Date.now()}-${Array.from(bytes).map((value) => value.toString(16)).join('')}`;
  }

  async function executeTask() {
    runtimeState.executing = true;
    syncExecuteButton();
    let input;
    try {
      input = JSON.parse($('task-input').value || '{}');
    } catch {
      setMessage('Task input must be valid JSON.', 'bad');
      runtimeState.executing = false;
      syncExecuteButton();
      return;
    }
    const body = {
      task_id: $('task-id').value.trim(),
      binding_id: $('binding-id').value.trim(),
      idempotency_key: $('idempotency-key').value.trim() || nextIdempotencyKey(),
      task_input: input,
    };
    $('idempotency-key').value = body.idempotency_key;
    $('result').textContent = 'Submitting for admission…';
    $('stage-admitted').className = 'stage current';
    $('execution-state').textContent = 'submitting';
    $('execution-state').className = statusClass('executing');
    const beforeUsed = Number(runtimeState.lastQuotaUsed ?? 0);
    try {
      const payload = await request('/evaluation/runtime/task-execute', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      $('result').textContent = JSON.stringify(payload, null, 2);
      const afterUsed = Number(payload.quota?.used ?? beforeUsed);
      const replay = payload.idempotent_replay === true;
      const delta = Math.max(0, afterUsed - beforeUsed);
      $('quota-effect').textContent = replay ? '+0 replay' : `+${delta || 1}`;
      $('quota-effect').className = replay ? 'value ok' : 'value warn';
      $('quota-effect-meta').textContent = replay
        ? 'Durable idempotent replay; no additional admitted-execution unit consumed.'
        : 'New execution admitted; one evaluation quota unit consumed.';
      if (payload.quota) runtimeState.lastQuotaUsed = afterUsed;
      await refreshStatus({ preserveQuotaEffect: true });
    } catch (error) {
      $('result').textContent = text(error.message || error);
      setMessage(`Execution failed: ${error.message || error}`, 'bad');
      try { await refreshStatus({ preserveQuotaEffect: true }); } catch {}
    } finally {
      runtimeState.executing = false;
      syncExecuteButton();
    }
  }

  function stopPolling() {
    if (pollTimer) window.clearInterval(pollTimer);
    pollTimer = null;
  }

  function startPolling() {
    stopPolling();
    pollTimer = window.setInterval(() => {
      if (apiKey && document.visibilityState === 'visible') {
        refreshStatus({ preserveQuotaEffect: true }).catch(() => {});
      }
    }, 5000);
  }

  $('connect').addEventListener('click', async () => {
    apiKey = $('api-key').value.trim();
    if (!apiKey) {
      setMessage('Enter the Evaluation API key first.', 'bad');
      return;
    }
    runtimeState.credentialStatus = 'connecting';
    runtimeState.quotaRemaining = 0;
    runtimeState.lastQuotaUsed = null;
    syncExecuteButton();
    try {
      const payload = await refreshStatus();
      const tasks = Array.isArray(payload.allowed_task_ids) ? payload.allowed_task_ids : [];
      const bindings = Array.isArray(payload.allowed_binding_ids) ? payload.allowed_binding_ids : [];
      if (!$('task-id').value && tasks.length === 1) $('task-id').value = tasks[0];
      if (!$('binding-id').value && bindings.length === 1) $('binding-id').value = bindings[0];
      startPolling();
    } catch {}
  });

  $('disconnect').addEventListener('click', () => {
    apiKey = '';
    $('api-key').value = '';
    runtimeState = {
      credentialStatus: 'disconnected',
      quotaRemaining: 0,
      executing: false,
      lastQuotaUsed: null,
    };
    syncExecuteButton();
    stopPolling();
    resetStages();
    $('customer-report').textContent = 'Connect an Evaluation API key to load the current safe report.';
    setMessage('Evaluation key forgotten from this page memory.');
  });

  $('execute').addEventListener('click', executeTask);
  $('idempotency-key').value = nextIdempotencyKey();
})();
