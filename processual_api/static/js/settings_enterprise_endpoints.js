(() => {
  'use strict';

  const ROOT_ID = 'see-endpoint-bindings';
  const TASKS_ENDPOINT = '/settings/enterprise-integration/task-catalog';
  const BINDINGS_ENDPOINT = '/settings/enterprise-integration/endpoint-bindings';
  const EVIDENCE_ENDPOINT = '/settings/enterprise-integration/sandbox-evidence';
  const CONSOLE_ENDPOINT = '/settings/enterprise-integration';
  const BODY_METHODS = new Set(['POST', 'PUT', 'PATCH']);
  let initialized = false;
  let observer = null;
  let loading = false;
  let taskCatalog = [];
  let qualificationProfiles = [];

  function el(tag, className, copy) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (copy !== undefined) node.textContent = String(copy);
    return node;
  }

  function field(label, inputNode) {
    const wrap = el('label', 'see-field');
    wrap.append(el('span', 'see-label', label), inputNode);
    return wrap;
  }

  function input(type, name, placeholder = '') {
    const node = document.createElement('input');
    node.type = type;
    node.name = name;
    node.placeholder = placeholder;
    node.autocomplete = 'off';
    return node;
  }

  function select(name) {
    const node = document.createElement('select');
    node.name = name;
    return node;
  }

  function option(value, label) {
    const node = document.createElement('option');
    node.value = value;
    node.textContent = label;
    return node;
  }

  function unique(values) {
    return [...new Set(values)].sort();
  }

  function contractLabel(contractId) {
    return String(contractId || '').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  function compatibleProfiles(task) {
    const required = new Set(task?.required_scope_ids || []);
    return qualificationProfiles.filter(profile => {
      const allowed = new Set(profile.allowed_scope_ids || []);
      return [...required].every(scope => allowed.has(scope));
    });
  }

  function status(root, copy, state = 'info') {
    let node = root.querySelector('[data-see-status]');
    if (!node) {
      node = el('div', 'see-status');
      node.dataset.seeStatus = 'true';
      node.setAttribute('role', 'status');
      node.setAttribute('aria-live', 'polite');
      root.appendChild(node);
    }
    node.dataset.state = state;
    node.textContent = copy;
  }

  function activeGrantFor(evidencePayload, bindingId) {
    const grants = evidencePayload?.grants || [];
    return [...grants].reverse().find(grant => (
      grant.binding_id === bindingId && grant.status === 'active'
    ));
  }

  function renderBindings(root, bindings, evidencePayload = {}) {
    const region = root.querySelector('[data-see-bindings]');
    if (!region) return;
    region.replaceChildren();
    if (!bindings.length) {
      region.appendChild(el('p', 'see-empty', 'No endpoint bindings have been configured yet.'));
      return;
    }
    bindings.forEach(binding => {
      const card = el('article', 'see-binding-card');
      const head = el('div', 'see-binding-head');
      const title = el('strong', 'see-binding-title', binding.display_name || binding.binding_id);
      const state = el('span', 'see-pill', binding.validation?.lifecycle_state || 'validated');
      const grant = activeGrantFor(evidencePayload, binding.binding_id);
      head.append(title, state);
      if (grant) head.appendChild(el('span', 'see-pill', 'Sandbox grant active'));
      const task = el('code', 'see-code', binding.task_id);
      const endpoint = el('code', 'see-code', `${binding.method} ${binding.base_url}${binding.path}`);
      const meta = el('p', 'see-meta', `${contractLabel(binding.adapter_contract_id)} · ${binding.credential_profile_id}`);
      card.append(head, task, endpoint, meta);
      region.appendChild(card);
    });
  }

  function renderEvidence(root, evidencePayload) {
    const region = root.querySelector('[data-see-evidence]');
    if (!region) return;
    region.replaceChildren();
    const evidence = [...(evidencePayload?.evidence || [])].reverse();
    if (!evidence.length) {
      region.appendChild(el('p', 'see-empty', 'No live sandbox proof has been recorded yet.'));
      return;
    }
    evidence.slice(0, 10).forEach(item => {
      const card = el('article', 'see-binding-card');
      const head = el('div', 'see-binding-head');
      head.append(
        el('strong', 'see-binding-title', item.task_id || item.binding_id),
        el('span', 'see-pill', item.network_request_executed ? 'Network crossed' : 'Not executed')
      );
      const digest = el('code', 'see-code', `SHA-256 ${item.evidence_sha256 || '—'}`);
      const detail = el(
        'p',
        'see-meta',
        `${item.destination_host || 'sandbox'} · HTTP ${item.http_status || '—'} · ${item.completed_at || '—'}`
      );
      card.append(head, digest, detail);
      region.appendChild(card);
    });
  }

  function renderResponseMappingFields(form, task) {
    const region = form.querySelector('[data-see-mapping]');
    region.replaceChildren();
    if (!task) return;
    region.appendChild(el(
      'p',
      'see-help',
      'Map customer API JSON paths to Maestro canonical fields. Required fields must be mapped before saving.'
    ));
    const grid = el('div', 'see-mapping-grid');
    const required = new Set(task.required_input_fields || []);
    [...(task.required_input_fields || []), ...(task.optional_input_fields || [])].forEach(name => {
      const source = input('text', `map:${name}`, `$.${name}`);
      source.dataset.canonicalField = name;
      source.dataset.required = required.has(name) ? 'true' : 'false';
      grid.appendChild(field(`${name}${required.has(name) ? ' *' : ''}`, source));
    });
    region.appendChild(grid);
  }

  function renderRequestBodyMappingFields(form, task) {
    const region = form.querySelector('[data-see-request-mapping]');
    region.replaceChildren();
    if (!task || !BODY_METHODS.has(form.elements.method.value)) {
      region.appendChild(el('p', 'see-help', 'This endpoint method does not send a JSON request body.'));
      return;
    }
    region.appendChild(el(
      'p',
      'see-help',
      'Map canonical Maestro task fields to customer API JSON body paths. Required task fields must be represented.'
    ));
    const grid = el('div', 'see-mapping-grid');
    const required = new Set(task.required_input_fields || []);
    [...(task.required_input_fields || []), ...(task.optional_input_fields || [])].forEach(name => {
      const externalPath = input('text', `body:${name}`, name);
      externalPath.dataset.bodyField = name;
      externalPath.dataset.required = required.has(name) ? 'true' : 'false';
      grid.appendChild(field(`${name} → external path${required.has(name) ? ' *' : ''}`, externalPath));
    });
    region.appendChild(grid);
  }

  function taskInputSkeleton(task) {
    const result = {};
    (task?.required_input_fields || []).forEach(name => { result[name] = ''; });
    return JSON.stringify(result, null, 2);
  }

  function syncTaskControls(form) {
    const contract = form.elements.adapter_contract_id.value;
    const taskSelect = form.elements.task_id;
    const currentTask = taskSelect.value;
    const candidates = taskCatalog.filter(task => task.adapter_contract_id === contract);
    taskSelect.replaceChildren(option('', 'Select a Maestro task'));
    candidates.forEach(task => taskSelect.appendChild(option(task.task_id, task.safe_operation)));
    if (candidates.some(task => task.task_id === currentTask)) taskSelect.value = currentTask;
    if (!taskSelect.value && candidates.length) taskSelect.value = candidates[0].task_id;

    const task = taskCatalog.find(item => item.task_id === taskSelect.value);
    const profileSelect = form.elements.credential_profile_id;
    profileSelect.replaceChildren(option('', 'Select credential reference profile'));
    compatibleProfiles(task).forEach(profile => {
      profileSelect.appendChild(option(profile.credential_profile_id, profile.display_name));
    });
    if (profileSelect.options.length === 2) profileSelect.selectedIndex = 1;
    form.elements.method.value = task?.operation_class === 'approval_gated_write' ? 'POST' : 'GET';
    renderResponseMappingFields(form, task);
    renderRequestBodyMappingFields(form, task);
    form.elements.task_input.placeholder = taskInputSkeleton(task);
    const hint = form.querySelector('[data-see-task-hint]');
    hint.textContent = task
      ? `${task.safe_operation} · scopes: ${(task.required_scope_ids || []).join(', ')} · output: ${task.output_slot}`
      : 'Choose a declared Maestro task.';
  }

  function pathParameterMapping(path, task) {
    const mapping = {};
    const canonical = new Set([
      ...(task?.required_input_fields || []),
      ...(task?.optional_input_fields || []),
    ]);
    for (const match of String(path || '').matchAll(/\{([A-Za-z0-9_.:-]+)\}/g)) {
      const name = match[1];
      if (!canonical.has(name)) {
        throw new Error(`Path parameter ${name} is not a canonical field for the selected task.`);
      }
      mapping[name] = `$task.${name}`;
    }
    return mapping;
  }

  function bindingPayload(form) {
    const task = taskCatalog.find(item => item.task_id === form.elements.task_id.value);
    if (!task) throw new Error('Select a Maestro task.');
    const mapping = {};
    form.querySelectorAll('[data-canonical-field]').forEach(node => {
      const value = node.value.trim();
      if (value) mapping[node.dataset.canonicalField] = value;
      if (node.dataset.required === 'true' && !value) {
        throw new Error(`Required mapping missing: ${node.dataset.canonicalField}`);
      }
    });
    const path = form.elements.path.value.trim();
    return {
      binding_id: form.elements.binding_id.value.trim(),
      display_name: form.elements.display_name.value.trim(),
      adapter_contract_id: form.elements.adapter_contract_id.value,
      task_id: task.task_id,
      credential_profile_id: form.elements.credential_profile_id.value,
      environment: 'sandbox',
      base_url: form.elements.base_url.value.trim(),
      method: form.elements.method.value,
      path,
      required_scope_ids: task.required_scope_ids,
      path_parameters: pathParameterMapping(path, task),
      query_parameters: {},
      request_headers: { Accept: 'application/json' },
      response_format: 'json',
      response_data_path: form.elements.response_data_path.value.trim() || '$',
      field_mapping: mapping,
      success_codes: form.elements.method.value === 'POST' ? [200, 201, 202] : [200],
      timeout_seconds: 15,
    };
  }

  function requestMappingPayload(form, binding) {
    const body_mapping = {};
    if (BODY_METHODS.has(binding.method)) {
      form.querySelectorAll('[data-body-field]').forEach(node => {
        const externalPath = node.value.trim();
        if (node.dataset.required === 'true' && !externalPath) {
          throw new Error(`Required request mapping missing: ${node.dataset.bodyField}`);
        }
        if (externalPath) body_mapping[externalPath] = `$task.${node.dataset.bodyField}`;
      });
    }
    return { binding_id: binding.binding_id, body_mapping };
  }

  function parseTaskInput(form) {
    const raw = form.elements.task_input.value.trim();
    if (!raw) throw new Error('Provide canonical task input JSON for the sandbox proof.');
    const value = JSON.parse(raw);
    if (!value || Array.isArray(value) || typeof value !== 'object') {
      throw new Error('Canonical task input must be a JSON object.');
    }
    return value;
  }

  async function persistBindingAndRequestMapping(form) {
    const binding = bindingPayload(form);
    if (!binding.binding_id || !binding.display_name || !binding.base_url || !binding.path || !binding.credential_profile_id) {
      throw new Error('Complete the binding name, ID, credential profile, base URL, and endpoint path.');
    }
    await CLIENT.put(`${BINDINGS_ENDPOINT}/${encodeURIComponent(binding.binding_id)}`, binding);
    if (BODY_METHODS.has(binding.method)) {
      const requestMapping = requestMappingPayload(form, binding);
      await CLIENT.put(
        `${BINDINGS_ENDPOINT}/${encodeURIComponent(binding.binding_id)}/request-mapping`,
        requestMapping
      );
    }
    return binding;
  }

  async function reloadState(root) {
    const [bindingsPayload, evidencePayload] = await Promise.all([
      CLIENT.get(BINDINGS_ENDPOINT),
      CLIENT.get(EVIDENCE_ENDPOINT),
    ]);
    renderBindings(root, bindingsPayload.bindings || [], evidencePayload);
    renderEvidence(root, evidencePayload);
  }

  async function saveBinding(root, form) {
    try {
      status(root, 'Validating endpoint, request mapping, and canonical response mapping…');
      await persistBindingAndRequestMapping(form);
      await reloadState(root);
      status(root, 'Endpoint binding saved and schema-validated for sandbox execution.', 'success');
    } catch (error) {
      status(root, error?.message || 'Endpoint binding could not be saved.', 'error');
    }
  }

  async function previewMapping(root, form) {
    try {
      const binding = await persistBindingAndRequestMapping(form);
      const raw = form.elements.sample_response.value.trim();
      if (!raw) throw new Error('Paste a sandbox/sample JSON response to preview the mapping.');
      const mapped = await CLIENT.post(
        `${BINDINGS_ENDPOINT}/${encodeURIComponent(binding.binding_id)}/mapping-preview`,
        { response_payload: JSON.parse(raw) }
      );
      const output = root.querySelector('[data-see-preview]');
      output.textContent = JSON.stringify(mapped.canonical_input || {}, null, 2);
      output.hidden = false;
      status(root, `Mapping valid for ${mapped.task_id}. No network request or production activation was performed.`, 'success');
    } catch (error) {
      status(root, error?.message || 'Mapping preview failed.', 'error');
    }
  }

  async function previewRequest(root, form) {
    try {
      const binding = await persistBindingAndRequestMapping(form);
      const preview = await CLIENT.post(
        `${BINDINGS_ENDPOINT}/${encodeURIComponent(binding.binding_id)}/request-preview`,
        { task_input: parseTaskInput(form) }
      );
      const output = root.querySelector('[data-see-preview]');
      output.textContent = JSON.stringify(preview, null, 2);
      output.hidden = false;
      status(root, 'Sandbox request preview built from canonical task input without network execution.', 'success');
    } catch (error) {
      status(root, error?.message || 'Request preview failed.', 'error');
    }
  }

  async function runLiveSandboxProof(root, form) {
    try {
      const binding = await persistBindingAndRequestMapping(form);
      status(root, 'Executing governed live sandbox proof…');
      const result = await CLIENT.post(
        `${BINDINGS_ENDPOINT}/${encodeURIComponent(binding.binding_id)}/sandbox-execute`,
        { task_input: parseTaskInput(form) }
      );
      const output = root.querySelector('[data-see-preview]');
      output.textContent = JSON.stringify({
        status: result.status,
        task_id: result.task_id,
        canonical_input: result.canonical_input,
        canonical_input_sha256: result.canonical_input_sha256,
        evidence_sha256: result.evidence_sha256,
        http_status: result.http_status,
        destination_host: result.destination_host,
        completed_at: result.completed_at,
      }, null, 2);
      output.hidden = false;
      await reloadState(root);
      status(root, `Live sandbox proof passed for ${result.task_id}. Evidence SHA-256: ${result.evidence_sha256}`, 'success');
    } catch (error) {
      status(root, error?.message || 'Live sandbox proof failed or requires a supervisor sandbox grant.', 'error');
    }
  }

  function buildWorkspace(consolePayload, bindingsPayload, evidencePayload) {
    const root = el('section', 'see-workspace');
    root.id = ROOT_ID;
    root.setAttribute('aria-labelledby', 'see-title');

    const header = el('div', 'see-header');
    const copy = el('div', '');
    copy.append(
      el('span', 'see-eyebrow', 'Endpoint → Canonical task binding'),
      el('h4', 'see-title', 'Enterprise API endpoint configuration'),
      el('p', 'see-copy', 'Configure customer sandbox APIs, map data into declared Maestro tasks, and produce a governed live proof with SHA-256 evidence.')
    );
    copy.querySelector('.see-title').id = 'see-title';
    const guard = el('div', 'see-guard');
    guard.append(
      el('span', 'see-pill', 'Sandbox configuration'),
      el('span', 'see-pill see-pill-blocked', 'Production blocked')
    );
    header.append(copy, guard);
    root.appendChild(header);

    if (consolePayload.enabled !== true) {
      root.appendChild(el('p', 'see-empty', 'Endpoint configuration requires an eligible Enterprise Integration entitlement.'));
      return root;
    }

    const form = document.createElement('form');
    form.className = 'see-form';
    form.addEventListener('submit', event => event.preventDefault());

    const contract = select('adapter_contract_id');
    contract.appendChild(option('', 'Select integration domain'));
    unique(taskCatalog.map(task => task.adapter_contract_id)).forEach(id => contract.appendChild(option(id, contractLabel(id))));
    const task = select('task_id');
    const credential = select('credential_profile_id');
    const method = select('method');
    ['GET', 'POST', 'PUT', 'PATCH'].forEach(item => method.appendChild(option(item, item)));

    const topGrid = el('div', 'see-grid');
    topGrid.append(
      field('Integration domain', contract),
      field('Maestro task', task),
      field('Credential reference profile', credential),
      field('Method', method),
      field('Binding ID', input('text', 'binding_id', 'customer-system.task.binding')),
      field('Display name', input('text', 'display_name', 'Customer billing account lookup')),
      field('Sandbox base URL', input('url', 'base_url', 'https://sandbox.customer.example/api')),
      field('Endpoint path', input('text', 'path', '/accounts/{account_id}')),
      field('Response data path', input('text', 'response_data_path', '$.data'))
    );
    form.appendChild(topGrid);

    const hint = el('p', 'see-task-hint', 'Choose a declared Maestro task.');
    hint.dataset.seeTaskHint = 'true';
    form.appendChild(hint);

    const requestMapping = el('section', 'see-mapping');
    requestMapping.dataset.seeRequestMapping = 'true';
    requestMapping.setAttribute('aria-label', 'Request body mapping');
    form.appendChild(requestMapping);

    const responseMapping = el('section', 'see-mapping');
    responseMapping.dataset.seeMapping = 'true';
    responseMapping.setAttribute('aria-label', 'Response mapping');
    form.appendChild(responseMapping);

    const taskInput = document.createElement('textarea');
    taskInput.name = 'task_input';
    taskInput.rows = 7;
    taskInput.placeholder = '{\n  "customer_id": "..."\n}';
    form.appendChild(field('Canonical task input for request preview / live proof', taskInput));

    const sample = document.createElement('textarea');
    sample.name = 'sample_response';
    sample.rows = 7;
    sample.placeholder = '{\n  "data": { "id": "..." }\n}';
    form.appendChild(field('Sandbox/sample JSON response for mapping preview', sample));

    const actions = el('div', 'see-actions');
    [
      ['Save validated binding', 'see-btn see-btn-primary', () => saveBinding(root, form)],
      ['Preview request', 'see-btn', () => previewRequest(root, form)],
      ['Preview canonical mapping', 'see-btn', () => previewMapping(root, form)],
      ['Run live sandbox proof', 'see-btn see-btn-primary', () => runLiveSandboxProof(root, form)],
    ].forEach(([label, className, handler]) => {
      const button = el('button', className, label);
      button.type = 'button';
      button.addEventListener('click', handler);
      actions.appendChild(button);
    });
    form.appendChild(actions);

    const previewOutput = el('pre', 'see-preview');
    previewOutput.dataset.seePreview = 'true';
    previewOutput.hidden = true;
    form.appendChild(previewOutput);
    root.appendChild(form);

    root.appendChild(el('h5', 'see-bindings-title', 'Validated endpoint bindings'));
    const bindings = el('div', 'see-bindings');
    bindings.dataset.seeBindings = 'true';
    root.appendChild(bindings);

    root.appendChild(el('h5', 'see-bindings-title', 'Live sandbox proof evidence'));
    const evidence = el('div', 'see-bindings');
    evidence.dataset.seeEvidence = 'true';
    evidence.setAttribute('aria-live', 'polite');
    root.appendChild(evidence);

    renderBindings(root, bindingsPayload.bindings || [], evidencePayload);
    renderEvidence(root, evidencePayload);

    contract.addEventListener('change', () => syncTaskControls(form));
    task.addEventListener('change', () => syncTaskControls(form));
    method.addEventListener('change', () => {
      const selectedTask = taskCatalog.find(item => item.task_id === task.value);
      renderRequestBodyMappingFields(form, selectedTask);
    });
    if (contract.options.length > 1) {
      contract.selectedIndex = 1;
      syncTaskControls(form);
    }
    return root;
  }

  async function refresh(force = false) {
    const card = document.getElementById('set-enterprise-console-card');
    if (!card || loading) return;
    if (!force && document.getElementById(ROOT_ID)) return;
    loading = true;
    try {
      const [consolePayload, tasksPayload, bindingsPayload, evidencePayload] = await Promise.all([
        CLIENT.get(CONSOLE_ENDPOINT),
        CLIENT.get(TASKS_ENDPOINT),
        CLIENT.get(BINDINGS_ENDPOINT),
        CLIENT.get(EVIDENCE_ENDPOINT),
      ]);
      taskCatalog = tasksPayload.tasks || [];
      qualificationProfiles = consolePayload.qualification_catalog?.profiles || [];
      document.getElementById(ROOT_ID)?.remove();
      const workspace = buildWorkspace(consolePayload, bindingsPayload, evidencePayload);
      const safety = document.getElementById('set-enterprise-console-safety');
      if (safety) card.insertBefore(workspace, safety);
      else card.appendChild(workspace);
    } catch (error) {
      document.getElementById(ROOT_ID)?.remove();
    } finally {
      loading = false;
    }
  }

  function watch() {
    if (observer || !document.body) return;
    observer = new MutationObserver(() => {
      if (document.getElementById('set-enterprise-console-card')) refresh(false);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function init() {
    if (!initialized) {
      initialized = true;
      watch();
    }
    refresh(false);
  }

  window.PMK_SETTINGS_ENTERPRISE_ENDPOINTS = { init, refresh };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
