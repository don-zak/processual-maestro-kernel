(() => {
  'use strict';

  const ROOT_ID = 'seq18-workspace';
  const ENDPOINT = '/settings/enterprise-integration';
  const QUALIFY_ENDPOINT = '/settings/enterprise-integration/sandbox-qualification';
  const DRAFT_ENDPOINT = '/settings/enterprise-integration/sandbox-qualification/draft';
  const SUBMIT_ENDPOINT = `${DRAFT_ENDPOINT}/submit`;
  let initialized = false;
  let loading = false;
  let observer = null;

  function element(tag, className, copy) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (copy !== undefined) node.textContent = copy;
    return node;
  }

  function checkbox(id, label, hint) {
    const wrap = element('label', 'seq18-choice');
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.value = id;
    input.dataset.seq18Value = id;
    const copy = element('span', 'seq18-choice-copy');
    copy.append(element('strong', '', label), element('small', '', hint || id));
    wrap.append(input, copy);
    return wrap;
  }

  function fieldLabel(text) {
    return element('span', 'seq18-field-label', text);
  }

  function metric(label, value) {
    const item = element('div', 'seq18-result-metric');
    item.append(
      element('span', '', label),
      element('strong', '', String(value))
    );
    return item;
  }

  function renderResult(root, result, heading) {
    let panel = root.querySelector('[data-seq18-result]');
    if (!panel) {
      panel = element('section', 'seq18-result');
      panel.dataset.seq18Result = 'true';
      panel.setAttribute('role', 'status');
      panel.setAttribute('aria-live', 'polite');
      root.appendChild(panel);
    }
    panel.replaceChildren();

    const ready = result?.sandbox_ready === true;
    const draftStatus = result?.draft_status || '';
    const title = heading || (
      draftStatus === 'pending_review'
        ? 'Submitted for supervised review'
        : ready
          ? 'Ready for sandbox review'
          : 'Qualification remains blocked'
    );
    panel.append(
      element('span', 'seq18-eyebrow', 'Server state'),
      element('h5', 'seq18-result-title', title),
      element(
        'p',
        'seq18-result-copy',
        result?.next_action || 'Review the remaining qualification requirements.'
      )
    );

    const metrics = element('div', 'seq18-result-metrics');
    metrics.append(
      metric('Missing inputs', result?.missing_input_ids?.length || 0),
      metric('Security approvals', result?.security_controls_approved || 0),
      metric('Write scopes', result?.scope_posture?.write || 0),
      metric('Restricted scopes', result?.scope_posture?.restricted || 0)
    );
    if (result?.persisted === true) {
      metrics.append(
        metric('Draft revision', result?.revision || 0),
        metric('Review state', draftStatus || 'draft')
      );
    }
    panel.appendChild(metrics);
    panel.appendChild(
      element(
        'p',
        'seq18-guard-copy',
        'Production remains blocked. Runtime connector approval cannot be granted from this workspace.'
      )
    );
  }

  function selectedValues(root, selector) {
    return Array.from(root.querySelectorAll(selector + ':checked')).map(
      (node) => node.value
    );
  }

  function requestPayload(root, profileSelect) {
    const requestedScopeIds = selectedValues(
      root,
      '[data-seq18-scope] input'
    );
    const providedInputIds = selectedValues(
      root,
      '[data-seq18-input] input'
    );
    if (!profileSelect.value || requestedScopeIds.length === 0) {
      renderResult(root, {
        next_action: 'Choose one credential profile and at least one compatible catalog scope.',
      });
      return null;
    }
    return {
      credential_profile_id: profileSelect.value,
      requested_scope_ids: requestedScopeIds,
      provided_input_ids: providedInputIds,
    };
  }

  function setBusy(buttons, busy) {
    buttons.forEach((button) => {
      button.disabled = busy;
      button.setAttribute('aria-busy', busy ? 'true' : 'false');
    });
  }

  async function evaluate(root, profileSelect, buttons) {
    const payload = requestPayload(root, profileSelect);
    if (!payload) return;
    setBusy(buttons, true);
    try {
      const result = await CLIENT.post(QUALIFY_ENDPOINT, payload);
      renderResult(root, result, 'Sandbox qualification evaluated');
    } catch (error) {
      renderResult(root, {
        next_action:
          error?.detail ||
          'Qualification could not be evaluated. No approval was inferred.',
      });
    } finally {
      setBusy(buttons, false);
    }
  }

  async function saveDraft(root, profileSelect, buttons) {
    const payload = requestPayload(root, profileSelect);
    if (!payload) return null;
    setBusy(buttons, true);
    try {
      const result = await CLIENT.put(DRAFT_ENDPOINT, payload);
      renderResult(root, result, 'Qualification draft saved');
      return result;
    } catch (error) {
      renderResult(root, {
        next_action:
          error?.detail ||
          'Draft could not be saved. No review or approval was inferred.',
      });
      return null;
    } finally {
      setBusy(buttons, false);
    }
  }

  async function submitForReview(root, profileSelect, buttons) {
    const payload = requestPayload(root, profileSelect);
    if (!payload) return;
    setBusy(buttons, true);
    try {
      await CLIENT.put(DRAFT_ENDPOINT, payload);
      const result = await CLIENT.post(SUBMIT_ENDPOINT, {});
      renderResult(root, result, 'Submitted for supervised review');
    } catch (error) {
      renderResult(root, {
        next_action:
          error?.detail ||
          'Draft could not be submitted. No review or approval was inferred.',
      });
    } finally {
      setBusy(buttons, false);
    }
  }

  function restoreChecked(root, selector, values) {
    const selected = new Set(values || []);
    root.querySelectorAll(selector).forEach((node) => {
      node.checked = selected.has(node.value);
    });
  }

  function render(payload) {
    const host = document.getElementById('set-enterprise-console-card');
    if (!host) return;
    document.getElementById(ROOT_ID)?.remove();

    const catalog = payload?.qualification_catalog || {};
    if (payload?.enabled !== true || catalog.enabled !== true) return;

    const root = element('section', 'seq18-workspace');
    root.id = ROOT_ID;
    root.setAttribute('aria-labelledby', 'seq18-title');

    const header = element('div', 'seq18-header');
    header.append(
      element('span', 'seq18-eyebrow', 'Sandbox qualification'),
      element('h4', 'seq18-title', 'Prepare a supervised sandbox review'),
      element(
        'p',
        'seq18-copy',
        'Select catalog identifiers only. Do not enter API keys, passwords, tokens, certificate material, or endpoint secrets.'
      )
    );
    header.querySelector('.seq18-title').id = 'seq18-title';
    root.appendChild(header);

    const grid = element('div', 'seq18-grid');
    const profileField = element('label', 'seq18-field');
    profileField.appendChild(fieldLabel('Credential profile'));
    const profileSelect = document.createElement('select');
    profileSelect.className = 'seq18-select';
    profileSelect.setAttribute('aria-label', 'Credential profile');
    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    emptyOption.textContent = 'Choose a catalog profile';
    profileSelect.appendChild(emptyOption);
    (catalog.profiles || []).forEach((profile) => {
      const option = document.createElement('option');
      option.value = profile.credential_profile_id;
      option.textContent = profile.display_name;
      profileSelect.appendChild(option);
    });
    profileField.appendChild(profileSelect);

    const profileInfo = element(
      'p',
      'seq18-help',
      'Profile requirements are supplied by the server catalog.'
    );
    profileField.appendChild(profileInfo);
    grid.appendChild(profileField);

    const scopeField = element('fieldset', 'seq18-field seq18-fieldset');
    scopeField.dataset.seq18Scope = 'true';
    scopeField.appendChild(
      element('legend', 'seq18-field-label', 'Requested compatible scopes')
    );
    const scopeList = element('div', 'seq18-choice-list');
    scopeField.appendChild(scopeList);
    grid.appendChild(scopeField);

    const inputField = element(
      'fieldset',
      'seq18-field seq18-fieldset seq18-field-wide'
    );
    inputField.dataset.seq18Input = 'true';
    inputField.appendChild(
      element(
        'legend',
        'seq18-field-label',
        'Customer inputs already available'
      )
    );
    const inputList = element(
      'div',
      'seq18-choice-list seq18-choice-list-inputs'
    );
    inputField.appendChild(inputList);
    grid.appendChild(inputField);

    function selectedProfile() {
      return (catalog.profiles || []).find(
        (item) => item.credential_profile_id === profileSelect.value
      );
    }

    function syncProfile(options = {}) {
      inputList.replaceChildren();
      scopeList.replaceChildren();
      if (options.keepResult !== true) {
        root.querySelector('[data-seq18-result]')?.remove();
      }

      const profile = selectedProfile();
      const allowed = new Set(profile?.allowed_scope_ids || []);
      (catalog.scopes || [])
        .filter((scope) => allowed.has(scope.scope_id))
        .forEach((scope) => {
          const supervision = scope.requires_supervisor_approval
            ? ' · supervised'
            : '';
          const hint = `${scope.access_level} · ${scope.risk_level}${supervision}`;
          scopeList.appendChild(
            checkbox(scope.scope_id, scope.scope_id, hint)
          );
        });

      (profile?.required_input_ids || []).forEach((inputId) => {
        inputList.appendChild(
          checkbox(
            inputId,
            inputId.replaceAll('_', ' '),
            'Presence only — never paste the underlying value.'
          )
        );
      });
      profileInfo.textContent =
        profile?.description ||
        'Profile requirements are supplied by the server catalog.';
    }
    profileSelect.addEventListener('change', () => syncProfile());

    root.appendChild(grid);

    const actions = element('div', 'seq18-actions');
    const boundary = element(
      'p',
      'seq18-boundary',
      'Draft persistence stores catalog identifiers and input-presence declarations only. Submission requests supervised review; it does not approve security controls, runtime connectors, or production access.'
    );
    const buttonRow = element('div', 'seq18-action-row');
    const evaluateButton = element(
      'button',
      'seq18-evaluate',
      'Evaluate qualification'
    );
    const saveButton = element(
      'button',
      'seq18-evaluate',
      'Save draft'
    );
    const submitButton = element(
      'button',
      'seq18-evaluate',
      'Submit for supervised review'
    );
    const buttons = [evaluateButton, saveButton, submitButton];
    buttons.forEach((button) => {
      button.type = 'button';
    });
    evaluateButton.addEventListener('click', () =>
      evaluate(root, profileSelect, buttons)
    );
    saveButton.addEventListener('click', () =>
      saveDraft(root, profileSelect, buttons)
    );
    submitButton.addEventListener('click', () =>
      submitForReview(root, profileSelect, buttons)
    );
    buttonRow.append(evaluateButton, saveButton, submitButton);
    actions.append(boundary, buttonRow);
    root.appendChild(actions);

    const draft = payload?.qualification_draft;
    if (draft?.persisted === true) {
      profileSelect.value = draft.credential_profile_id || '';
      syncProfile({ keepResult: true });
      restoreChecked(
        root,
        '[data-seq18-scope] input',
        draft.requested_scope_ids
      );
      restoreChecked(
        root,
        '[data-seq18-input] input',
        draft.provided_input_ids
      );
      renderResult(
        root,
        draft,
        draft.draft_status === 'pending_review'
          ? 'Submitted for supervised review'
          : 'Saved qualification draft'
      );
    }

    const safety = document.getElementById('set-enterprise-console-safety');
    if (safety) host.insertBefore(root, safety);
    else host.appendChild(root);
  }

  async function refresh() {
    const host = document.getElementById('set-enterprise-console-card');
    if (!host || loading) return;
    loading = true;
    try {
      render(await CLIENT.get(ENDPOINT));
    } catch (error) {
      document.getElementById(ROOT_ID)?.remove();
    } finally {
      loading = false;
    }
  }

  function watch() {
    if (observer || !document.body) return;
    observer = new MutationObserver(() => {
      if (
        document.getElementById('set-enterprise-console-card') &&
        !document.getElementById(ROOT_ID)
      ) {
        refresh();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function init() {
    if (!initialized) {
      initialized = true;
      watch();
    }
    refresh();
  }

  window.PMK_SETTINGS_ENTERPRISE_QUALIFICATION_18 = { init, refresh };
})();
