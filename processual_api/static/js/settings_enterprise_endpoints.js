(() => {
  'use strict';

  const ROOT_ID = 'see-endpoint-bindings';
  const TASKS_ENDPOINT = '/settings/enterprise-integration/task-catalog';
  const BINDINGS_ENDPOINT = '/settings/enterprise-integration/endpoint-bindings';
  const CONSOLE_ENDPOINT = '/settings/enterprise-integration';
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

  function field(label, input) {
    const wrap = el('label', 'see-field');
    wrap.append(el('span', 'see-label', label), input);
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

  function renderBindings(root, bindings) {
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
      head.append(title, state);
      const task = el('code', 'see-code', binding.task_id);
      const endpoint = el('code', 'see-code', `${binding.method} ${binding.base_url}${binding.path}`);
      const meta = el('p', 'see-meta', `${contractLabel(binding.adapter_contract_id)} · ${binding.credential_profile_id}`);
      card.append(head, task, endpoint, meta);
      region.appendChild(card);
    });
  }

  function renderMappingFields(form, task) {
    const region = form.querySelector('[data-see-mapping]');
    region.replaceChildren();
    if (!task) return;
    const intro = el('p', 'see-help', 'Map customer API JSON paths to Maestro canonical fields. Required fields must be mapped before saving.');
    region.appendChild(intro);
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
    renderMappingFields(form, task);
    const taskHint = form.querySelector('[data-see-task-hint]');
    taskHint.textContent = task
      ? `${task.safe_operation} · scopes: ${(task.required_scope_ids || []).join(', ')} · output: ${task.output_slot}`
      : 'Choose a declared Maestro task.';
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
    const bindingId = form.elements.binding_id.value.trim();
    return {
      binding_id: bindingId,
      display_name: form.elements.display_name.value.trim(),
      adapter_contract_id: form.elements.adapter_contract_id.value,
      task_id: task.task_id,
      credential_profile_id: form.elements.credential_profile_id.value,
      environment: 'sandbox',
      base_url: form.elements.base_url.value.trim(),
      method: form.elements.method.value,
      path: form.elements.path.value.trim(),
      required_scope_ids: task.required_scope_ids,
      path_parameters: {},
      query_parameters: {},
      request_headers: { Accept: 'application/json' },
      response_format: 'json',
      response_data_path: form.elements.response_data_path.value.trim() || '$',
      field_mapping: mapping,
      success_codes: [200],
      timeout_seconds: 15,
    };
  }

  async function saveBinding(root, form) {
    try {
      const payload = bindingPayload(form);
      if (!payload.binding_id || !payload.display_name || !payload.base_url || !payload.path || !payload.credential_profile_id) {
        throw new Error('Complete the binding name, ID, credential profile, base URL, and endpoint path.');
      }
      status(root, 'Validating and saving endpoint binding…');
      await CLIENT.put(`${BINDINGS_ENDPOINT}/${encodeURIComponent(payload.binding_id)}`, payload);
      status(root, 'Endpoint binding saved and schema-validated for sandbox configuration.', 'success');
      const listed = await CLIENT.get(BINDINGS_ENDPOINT);
      renderBindings(root, listed.bindings || []);
    } catch (error) {
      status(root, error?.message || 'Endpoint binding could not be saved.', 'error');
    }
  }

  async function previewMapping(root, form) {
    try {
      const payload = bindingPayload(form);
      if (!payload.binding_id) throw new Error('Save or provide a binding ID before previewing mapping.');
      await CLIENT.put(`${BINDINGS_ENDPOINT}/${encodeURIComponent(payload.binding_id)}`, payload);
      const raw = form.elements.sample_response.value.trim();
      if (!raw) throw new Error('Paste a sandbox/sample JSON response to preview the mapping.');
      const responsePayload = JSON.parse(raw);
      const mapped = await CLIENT.post(
        `${BINDINGS_ENDPOINT}/${encodeURIComponent(payload.binding_id)}/mapping-preview`,
        { response_payload: responsePayload }
      );
      const output = root.querySelector('[data-see-preview]');
      output.textContent = JSON.stringify(mapped.canonical_input || {}, null, 2);
      output.hidden = false;
      status(root, `Mapping valid for ${mapped.task_id}. No network request or production activation was performed.`, 'success');
    } catch (error) {
      status(root, error?.message || 'Mapping preview failed.', 'error');
    }
  }

  function buildWorkspace(consolePayload, bindingsPayload) {
    const root = el('section', 'see-workspace');
    root.id = ROOT_ID;
    root.setAttribute('aria-labelledby', 'see-title');

    const header = el('div', 'see-header');
    const copy = el('div', '');
    const eyebrow = el('span', 'see-eyebrow', 'Endpoint → Canonical task binding');
    const title = el('h4', 'see-title', 'Enterprise API endpoint configuration');
    title.id = 'see-title';
    const description = el(
      'p',
      'see-copy',
      'Define customer API endpoints and map their JSON fields into the exact Maestro tasks declared for CRM, billing, banking, government, network, research, university, documents, orders, and support.'
    );
    copy.append(eyebrow, title, description);
    const guard = el('div', 'see-guard');
    guard.append(el('span', 'see-pill', 'Sandbox configuration'), el('span', 'see-pill see-pill-blocked', 'Production blocked'));
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
    ['GET', 'POST'].forEach(item => method.appendChild(option(item, item)));
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
    const taskHint = el('p', 'see-task-hint', 'Choose a declared Maestro task.');
    taskHint.dataset.seeTaskHint = 'true';
    form.appendChild(taskHint);

    const mapping = el('div', 'see-mapping');
    mapping.dataset.seeMapping = 'true';
    form.appendChild(mapping);

    const sample = document.createElement('textarea');
    sample.name = 'sample_response';
    sample.rows = 7;
    sample.placeholder = '{\n  "data": { "id": "..." }\n}';
    form.appendChild(field('Sandbox/sample JSON response', sample));

    const actions = el('div', 'see-actions');
    const save = el('button', 'see-btn see-btn-primary', 'Save validated binding');
    save.type = 'button';
    save.addEventListener('click', () => saveBinding(root, form));
    const preview = el('button', 'see-btn', 'Preview canonical mapping');
    preview.type = 'button';
    preview.addEventListener('click', () => previewMapping(root, form));
    actions.append(save, preview);
    form.appendChild(actions);
    const previewOutput = el('pre', 'see-preview');
    previewOutput.dataset.seePreview = 'true';
    previewOutput.hidden = true;
    form.appendChild(previewOutput);
    root.appendChild(form);

    const bindingsTitle = el('h5', 'see-bindings-title', 'Validated endpoint bindings');
    root.appendChild(bindingsTitle);
    const bindings = el('div', 'see-bindings');
    bindings.dataset.seeBindings = 'true';
    root.appendChild(bindings);
    renderBindings(root, bindingsPayload.bindings || []);

    contract.addEventListener('change', () => syncTaskControls(form));
    task.addEventListener('change', () => syncTaskControls(form));
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
      const [consolePayload, tasksPayload, bindingsPayload] = await Promise.all([
        CLIENT.get(CONSOLE_ENDPOINT),
        CLIENT.get(TASKS_ENDPOINT),
        CLIENT.get(BINDINGS_ENDPOINT),
      ]);
      taskCatalog = tasksPayload.tasks || [];
      qualificationProfiles = consolePayload.qualification_catalog?.profiles || [];
      document.getElementById(ROOT_ID)?.remove();
      const workspace = buildWorkspace(consolePayload, bindingsPayload);
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
