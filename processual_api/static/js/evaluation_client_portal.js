(function () {
  let apiKey = '';
  let pollTimer = null;
  let runtimeState = {
    credentialStatus: 'disconnected',
    quotaRemaining: 0,
    executing: false,
    lastQuotaUsed: null,
    allowedTasks: [],
    allowedBindings: [],
    guidedScenarios: [],
    latestExecution: null,
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

  function scenarioCandidates() {
    return Array.isArray(runtimeState.guidedScenarios)
      ? runtimeState.guidedScenarios.filter((scenario) => scenario && scenario.scenario_id)
      : [];
  }

  function runnableScenarios() {
    return scenarioCandidates().filter((scenario) => scenario.runnable === true);
  }

  function hasPreparedExecution() {
    return Boolean($('task-id').value.trim() && $('binding-id').value.trim());
  }

  function setNextAction(title, copy, state) {
    $('next-action-title').textContent = title;
    $('next-action-copy').textContent = copy;
    $('next-action-state').textContent = state;
  }

  function renderNextAction() {
    const credential = text(runtimeState.credentialStatus).toLowerCase();
    const latest = runtimeState.latestExecution;

    if (!apiKey || credential === 'disconnected') {
      setNextAction(
        'Connect your Evaluation key',
        'Start by connecting the one-time Evaluation credential. Status reads consume +0 quota.',
        'Not connected'
      );
      return;
    }
    if (credential === 'connecting') {
      setNextAction('Reading sealed authority…', 'Maestro is loading grant scope, quota and scenario readiness from the backend.', 'Connecting');
      return;
    }
    if (credential !== 'active') {
      setNextAction(
        'Credential is not executable',
        `Current credential state is ${credential || 'unavailable'}. No new execution can be admitted.`,
        credential || 'Unavailable'
      );
      return;
    }
    if (Number(runtimeState.quotaRemaining) <= 0) {
      setNextAction('Evaluation quota is exhausted', 'Status and historical receipt remain readable, but no fresh execution can be admitted.', 'Quota exhausted');
      return;
    }
    if (runtimeState.executing || latest?.status === 'executing') {
      setNextAction('Execution is in progress', 'Keep this workspace open while Maestro updates outcome and durable evidence.', 'Executing');
      return;
    }
    if (latest?.evidence_persisted) {
      setNextAction('Review the completed proof', 'Inspect the evidence status, quota effect and customer evaluation receipt. You may prepare another authorized scenario if quota remains.', 'Evidence ready');
      return;
    }
    if (hasPreparedExecution()) {
      setNextAction('Execute the prepared sandbox scenario', 'Review the synthetic input in Technical execution details, then submit it for governed admission.', 'Ready to execute');
      return;
    }
    if (runnableScenarios().length) {
      setNextAction('Choose a runnable proof scenario', 'Select a green scenario card or use the selector, then prepare it from sealed backend authority.', 'Scenario available');
      return;
    }
    setNextAction('No runnable scenario yet', 'This grant is readable, but a matching prepared sandbox binding is still required before task execution.', 'Read-only');
  }

  function canExecute() {
    return Boolean(
      apiKey
      && runtimeState.credentialStatus === 'active'
      && Number(runtimeState.quotaRemaining) > 0
      && !runtimeState.executing
      && $('task-id').value.trim()
      && $('binding-id').value.trim()
    );
  }

  function syncExecuteButton() {
    $('execute').disabled = !canExecute();
    renderNextAction();
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

  function selectScenario(scenarioId) {
    const scenario = scenarioCandidates().find((item) => text(item.scenario_id) === text(scenarioId));
    if (!scenario || scenario.runnable !== true) return;
    $('scenario-select').value = text(scenario.scenario_id);
    document.querySelectorAll('.scenario-card').forEach((card) => {
      card.classList.toggle('selected', card.dataset.scenarioId === text(scenario.scenario_id));
    });
    $('prepare-scenario').disabled = false;
    setMessage(`Selected ${text(scenario.title || scenario.scenario_id)}. Prepare it to load the backend-authorized task, binding, and synthetic input.`, 'ok');
    renderNextAction();
  }

  function renderScenarios() {
    const grid = $('scenario-grid');
    const select = $('scenario-select');
    const summary = $('scenario-summary');
    const candidates = scenarioCandidates();
    const runnable = runnableScenarios();
    const previouslySelected = select.value;

    grid.innerHTML = '';
    select.innerHTML = '';

    if (!candidates.length) {
      summary.textContent = 'This grant does not contain a backend-authorized guided scenario yet. Status, quota, and receipt remain available.';
      select.innerHTML = '<option value="">No guided scenario available</option>';
      select.disabled = true;
      $('prepare-scenario').disabled = true;
      renderNextAction();
      return;
    }

    candidates.forEach((scenario) => {
      const ready = scenario.runnable === true;
      const card = document.createElement('div');
      card.className = `scenario-card ${ready ? 'ready' : 'locked'}`;
      card.dataset.scenarioId = text(scenario.scenario_id);
      if (ready) {
        card.tabIndex = 0;
        card.setAttribute('role', 'button');
        card.setAttribute('aria-label', `Select ${text(scenario.title || scenario.scenario_id)}`);
      }

      const head = document.createElement('div');
      head.className = 'scenario-head';
      const title = document.createElement('div');
      title.className = 'scenario-title';
      title.textContent = text(scenario.title || scenario.scenario_id);
      const badge = document.createElement('span');
      badge.className = `scenario-badge ${ready ? 'ready' : 'locked'}`;
      badge.textContent = ready ? 'Runnable' : 'Locked';
      head.append(title, badge);

      const value = document.createElement('div');
      value.className = 'muted';
      value.textContent = text(scenario.customer_value || 'Governed External Evaluation scenario.');
      const meta = document.createElement('div');
      meta.className = 'scenario-meta';
      const readiness = text(scenario.readiness || (ready ? 'ready' : 'locked'));
      meta.textContent = `${text(scenario.scenario_id)} · ${text(scenario.kind || 'scenario')} · ${readiness}`;
      card.append(head, value, meta);
      grid.appendChild(card);

      if (ready) {
        card.addEventListener('click', () => selectScenario(scenario.scenario_id));
        card.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            selectScenario(scenario.scenario_id);
          }
        });
        const option = document.createElement('option');
        option.value = text(scenario.scenario_id);
        option.textContent = `${text(scenario.title || scenario.scenario_id)} — ${text(scenario.scenario_id)}`;
        select.appendChild(option);
      }
    });

    if (runnable.length) {
      summary.textContent = `${runnable.length} of ${candidates.length} proof-of-value scenario(s) are runnable under the sealed backend grant authority.`;
      select.disabled = false;
      const selected = runnable.some((scenario) => text(scenario.scenario_id) === previouslySelected)
        ? previouslySelected
        : text(runnable[0].scenario_id);
      select.value = selected;
      document.querySelectorAll('.scenario-card').forEach((card) => {
        card.classList.toggle('selected', card.dataset.scenarioId === selected);
      });
      $('prepare-scenario').disabled = false;
    } else {
      summary.textContent = `${candidates.length} scenario(s) are authorized for visibility, but none is runnable yet. The backend requires task-execute plus a matching prepared sandbox binding.`;
      select.innerHTML = '<option value="">Prepared runtime authority required</option>';
      select.disabled = true;
      $('prepare-scenario').disabled = true;
    }
    renderNextAction();
  }

  function prepareSelectedScenario() {
    const scenario = scenarioCandidates().find(
      (item) => text(item.scenario_id) === $('scenario-select').value
    );
    if (!scenario) return;
    if (scenario.runnable !== true) {
      setMessage(`Scenario ${text(scenario.scenario_id)} is not runnable under the current sealed grant.`, 'bad');
      return;
    }
    const bindings = Array.isArray(scenario.binding_ids) ? scenario.binding_ids.filter(Boolean) : [];
    if (!bindings.length) {
      setMessage('This backend-authorized scenario has no prepared binding available.', 'bad');
      return;
    }
    $('task-id').value = text(scenario.task_id);
    $('binding-id').value = bindings.length === 1 ? text(bindings[0]) : '';
    $('task-input').value = JSON.stringify(scenario.sample_input || {}, null, 2);
    $('idempotency-key').value = nextIdempotencyKey();
    $('technical-execution').open = true;
    $('result').textContent = bindings.length === 1
      ? `Scenario ${text(scenario.scenario_id)} prepared from backend authority. Review the synthetic input, then execute.`
      : `Scenario ${text(scenario.scenario_id)} prepared. Select one matching backend-authorized binding before execution.`;
    setMessage(
      `Prepared ${text(scenario.title || scenario.scenario_id)} from sealed grant authority. No client-side capability was added.`,
      'ok'
    );
    syncExecuteButton();
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
      guided_scenario_ids: scenarioCandidates().map((item) => item.scenario_id),
      scenario_catalog_source: payload.scenario_catalog_source || null,
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
    runtimeState.allowedTasks = Array.isArray(payload.allowed_task_ids) ? payload.allowed_task_ids : [];
    runtimeState.allowedBindings = Array.isArray(payload.allowed_binding_ids) ? payload.allowed_binding_ids : [];
    runtimeState.guidedScenarios = Array.isArray(payload.guided_scenarios) ? payload.guided_scenarios : [];
    runtimeState.latestExecution = latest;

    $('credential').textContent = text(payload.credential_status || 'unknown');
    $('credential').className = statusClass(payload.credential_status);
    $('type').textContent = text(payload.evaluation_type || '—').toUpperCase();
    $('quota-used').textContent = `${text(quota.used ?? 0)} / ${text(quota.limit ?? 0)}`;
    $('quota-remaining').textContent = text(quota.remaining ?? 0);
    $('quota-remaining').className = statusClass(quota.warning);
    $('grant-id').textContent = text(payload.grant_id || '—');
    $('key-id').textContent = [payload.api_key_id, payload.api_key_prefix].filter(Boolean).join(' · ') || '—';
    $('expires-at').textContent = text(payload.expires_at || '—');

    renderChips('allowed-tasks', runtimeState.allowedTasks, 'No canonical tasks exposed by this grant.');
    renderChips('allowed-bindings', runtimeState.allowedBindings, 'No prepared binding required by this grant.');
    renderScenarios();

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
      setMessage('Connected. Guided scenarios are derived from sealed backend grant authority; status reads consume +0 quota.', 'ok');
      return payload;
    } catch (error) {
      runtimeState.credentialStatus = 'unavailable';
      runtimeState.quotaRemaining = 0;
      runtimeState.allowedTasks = [];
      runtimeState.allowedBindings = [];
      runtimeState.guidedScenarios = [];
      runtimeState.latestExecution = null;
      renderScenarios();
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
    if (!canExecute()) {
      setMessage('Prepare an authorized scenario with a task and binding before execution.', 'bad');
      return;
    }
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
      try {
        const statusPayload = await refreshStatus({ preserveQuotaEffect: true });
        const afterUsed = Number(statusPayload?.quota?.used ?? beforeUsed);
        const delta = Math.max(0, afterUsed - beforeUsed);
        $('quota-effect').textContent = `+${delta}`;
        $('quota-effect').className = delta > 0 ? 'value warn' : 'value';
        $('quota-effect-meta').textContent = delta > 0
          ? 'Execution failed after admission; the admitted-execution unit remains consumed.'
          : 'Request failed before admission; no evaluation quota unit was consumed.';
      } catch {}
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
    runtimeState.allowedTasks = [];
    runtimeState.allowedBindings = [];
    runtimeState.guidedScenarios = [];
    runtimeState.latestExecution = null;
    syncExecuteButton();
    try {
      await refreshStatus();
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
      allowedTasks: [],
      allowedBindings: [],
      guidedScenarios: [],
      latestExecution: null,
    };
    $('task-id').value = '';
    $('binding-id').value = '';
    $('task-input').value = '{}';
    syncExecuteButton();
    stopPolling();
    resetStages();
    renderScenarios();
    $('customer-report').textContent = 'Connect an Evaluation API key to load the current safe report.';
    setMessage('Evaluation key forgotten from this page memory.');
  });

  $('prepare-scenario').addEventListener('click', prepareSelectedScenario);
  $('scenario-select').addEventListener('change', () => selectScenario($('scenario-select').value));
  $('task-id').addEventListener('input', syncExecuteButton);
  $('binding-id').addEventListener('input', syncExecuteButton);
  $('execute').addEventListener('click', executeTask);
  $('idempotency-key').value = nextIdempotencyKey();
  renderScenarios();
  renderNextAction();
})();