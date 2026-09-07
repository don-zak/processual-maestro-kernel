(function () {
  let apiKey = '';
  let pollTimer = null;

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
    if (['executing', 'low'].includes(value)) return 'value warn';
    if (['failed', 'revoked', 'expired', 'quota_exhausted', 'exhausted'].includes(value)) return 'value bad';
    return 'value';
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

  function renderStatus(payload) {
    const quota = payload.quota || {};
    const latest = payload.latest_execution || null;
    $('credential').textContent = text(payload.credential_status || 'unknown');
    $('credential').className = statusClass(payload.credential_status);
    $('type').textContent = text(payload.evaluation_type || '—');
    $('quota-used').textContent = `${text(quota.used ?? 0)} / ${text(quota.limit ?? 0)}`;
    $('quota-remaining').textContent = text(quota.remaining ?? 0);
    $('quota-remaining').className = statusClass(quota.warning);

    const limit = Number(quota.limit || 0);
    const used = Number(quota.used || 0);
    const pct = limit > 0 ? Math.min(100, Math.max(0, (used / limit) * 100)) : 0;
    $('quota-bar').style.width = `${pct}%`;
    $('quota-caption').textContent = `${used} of ${limit} admitted executions used · ${quota.remaining ?? 0} remaining · status checks and idempotent replays consume 0 units.`;

    if (latest) {
      $('execution-state').textContent = text(latest.status || 'unknown');
      $('execution-state').className = statusClass(latest.status);
      $('execution-meta').textContent = `${text(latest.task_id || '')} · ${text(latest.binding_id || '')} · ${text(latest.execution_id || latest.record_id || '')}`;
      const evidenceState = latest.evidence_persisted ? 'persisted' : latest.status === 'failed' ? 'failed' : 'pending';
      $('evidence-state').textContent = evidenceState;
      $('evidence-state').className = statusClass(evidenceState);
      $('evidence-meta').textContent = latest.evidence_sha256 ? `sha256 ${latest.evidence_sha256}` : text(latest.failure_code || '');
    } else {
      $('execution-state').textContent = 'none';
      $('execution-state').className = 'value';
      $('execution-meta').textContent = 'No admitted execution yet.';
      $('evidence-state').textContent = '—';
      $('evidence-state').className = 'value';
      $('evidence-meta').textContent = '';
    }
    $('execute').disabled = payload.credential_status !== 'active';
  }

  async function refreshStatus() {
    try {
      const payload = await request('/evaluation/runtime/status');
      renderStatus(payload);
      setMessage('Connected. Status is read-only and does not consume evaluation quota.', 'ok');
      return payload;
    } catch (error) {
      $('execute').disabled = true;
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
    const button = $('execute');
    button.disabled = true;
    let input;
    try {
      input = JSON.parse($('task-input').value || '{}');
    } catch {
      setMessage('Task input must be valid JSON.', 'bad');
      button.disabled = false;
      return;
    }
    const body = {
      task_id: $('task-id').value.trim(),
      binding_id: $('binding-id').value.trim(),
      idempotency_key: $('idempotency-key').value.trim() || nextIdempotencyKey(),
      task_input: input,
    };
    $('idempotency-key').value = body.idempotency_key;
    $('result').textContent = 'Executing…';
    $('execution-state').textContent = 'executing';
    $('execution-state').className = statusClass('executing');
    try {
      const payload = await request('/evaluation/runtime/task-execute', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      $('result').textContent = JSON.stringify(payload, null, 2);
      if (payload.quota) {
        renderStatus({
          credential_status: payload.quota.remaining > 0 ? 'active' : 'quota_exhausted',
          evaluation_type: $('type').textContent,
          quota: payload.quota,
          latest_execution: payload.execution_status || null,
        });
      }
      await refreshStatus();
    } catch (error) {
      $('result').textContent = text(error.message || error);
      setMessage(`Execution failed: ${error.message || error}`, 'bad');
      try { await refreshStatus(); } catch {}
    } finally {
      button.disabled = !apiKey;
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
        refreshStatus().catch(() => {});
      }
    }, 5000);
  }

  $('connect').addEventListener('click', async () => {
    apiKey = $('api-key').value.trim();
    if (!apiKey) {
      setMessage('Enter the Evaluation API key first.', 'bad');
      return;
    }
    try {
      await refreshStatus();
      startPolling();
    } catch {}
  });

  $('disconnect').addEventListener('click', () => {
    apiKey = '';
    $('api-key').value = '';
    $('execute').disabled = true;
    stopPolling();
    setMessage('Evaluation key forgotten from this page memory.');
  });

  $('execute').addEventListener('click', executeTask);
  $('idempotency-key').value = nextIdempotencyKey();
})();