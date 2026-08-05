(function () {
  'use strict';

  const API_ROOT = '/admin-marketplace/payment-destinations';
  const ADMIN_MARKET_ROOT = '/admin-marketplace';
  let destinations = [];
  let orders = [];
  let contracts = [];
  let paymentEvidence = [];
  let pendingCreateKey = '';
  let pendingMfaOperation = null;

  function element(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function safeDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date);
  }

  function uniqueKey(prefix) {
    const random = window.crypto && typeof window.crypto.randomUUID === 'function'
      ? window.crypto.randomUUID()
      : Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
    return prefix + '-' + random;
  }

  function authHeaders(extra) {
    const headers = window.PMK_ADMIN_AUTH && typeof window.PMK_ADMIN_AUTH.headers === 'function'
      ? window.PMK_ADMIN_AUTH.headers(extra)
      : new Headers(extra || {});
    if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    headers.set('Accept', 'application/json');
    return headers;
  }

  async function request(path, options) {
    const settings = options || {};
    const response = await fetch(path, {
      method: settings.method || 'GET',
      credentials: 'include',
      headers: authHeaders(settings.headers),
      body: settings.body === undefined ? undefined : JSON.stringify(settings.body),
    });
    const text = await response.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch (error) {}
    if (!response.ok) {
      const failure = new Error('Admin Market request failed.');
      failure.status = response.status;
      failure.detail = data && typeof data === 'object' ? data.detail : '';
      throw failure;
    }
    return data;
  }

  function setAuthorityState(state, text) {
    const target = element('admin-marketplace-authority-state');
    if (!target) return;
    target.dataset.state = state;
    target.textContent = text;
  }

  function showNotice(message, kind) {
    const notice = element('am-payment-notice');
    if (!notice) return;
    notice.hidden = false;
    notice.dataset.kind = kind || 'info';
    notice.textContent = message;
  }

  function clearNotice() {
    const notice = element('am-payment-notice');
    if (!notice) return;
    notice.hidden = true;
    notice.textContent = '';
    delete notice.dataset.kind;
  }

  function clearIdentifier() {
    const input = element('am-account-identifier');
    if (input) input.value = '';
    pendingCreateKey = '';
    updateSubmitState();
  }

  function updateSubmitState() {
    const form = element('am-payment-destination-form');
    const button = element('am-create-validate');
    if (!form || !button) return;
    button.disabled = button.dataset.loading === 'true' || !form.checkValidity();
  }

  function setMutationLoading(button, loading, label) {
    if (!button) return;
    if (loading) {
      button.dataset.loading = 'true';
      button.dataset.label = button.textContent;
      button.textContent = label || 'Working…';
      button.disabled = true;
      return;
    }
    delete button.dataset.loading;
    button.textContent = button.dataset.label || button.textContent;
    delete button.dataset.label;
    button.disabled = false;
    updateSubmitState();
  }

  function reasonMessage(error) {
    const status = error && error.status;
    if (status === 401) return 'Your identity session is unavailable. Sign in again before using Admin Market.';
    if (status === 403) return 'An active platform administrator authority is required.';
    if (status === 404) return 'The payment destination no longer exists. Refresh the list.';
    if (status === 409) return 'The request conflicts with the current destination state or an existing reference.';
    if (status === 413) return 'The submitted request is too large.';
    if (status === 422 || status === 400) return 'The submitted values are invalid. Review the fields and identifier format.';
    if (status === 429) return 'Too many verification attempts. Wait before retrying.';
    if (status === 503) return 'Admin Market is temporarily unavailable. No change was confirmed.';
    return 'The request could not be completed. No sensitive details were displayed.';
  }

  function destinationActions(item) {
    const actions = [];
    if (item.status === 'draft') actions.push(['validate', 'Validate']);
    if (item.status === 'validated') actions.push(['activate', 'Activate']);
    if (item.status === 'active' && !item.is_default) actions.push(['set-default', 'Set default']);
    if (item.status === 'active') actions.push(['deactivate', 'Deactivate']);
    return actions.map(([action, label]) =>
      '<button type="button" class="btn secondary sm" data-am-destination-action="' +
      action + '" data-destination-ref="' + escapeHtml(item.destination_ref) + '">' +
      escapeHtml(label) + '</button>'
    ).join('');
  }

  function renderDestinations() {
    const target = element('am-payment-destination-list');
    const count = element('am-destination-count');
    if (!target) return;
    if (count) count.textContent = String(destinations.length);

    element('am-kpi-destination-count').textContent = String(destinations.length);
    element('am-kpi-active-count').textContent = String(destinations.filter((item) => item.is_active).length);
    element('am-kpi-default-count').textContent = String(destinations.filter((item) => item.is_default && item.is_active).length);

    if (!destinations.length) {
      target.dataset.state = 'empty';
      target.innerHTML = '<div class="am-empty">No payment destinations are configured. Create and validate the first Tunisian receiving account.</div>';
      return;
    }

    target.dataset.state = 'ready';
    target.innerHTML = destinations.map((item) => {
      const classes = 'am-destination-item' + (item.is_default ? ' is-default' : '');
      const type = item.destination_type === 'postal_account' ? 'Postal account' : 'Bank account';
      return [
        '<article class="' + classes + '" data-destination="' + escapeHtml(item.destination_ref) + '">',
        '<div class="am-destination-title"><div><h4>' + escapeHtml(item.display_name) + '</h4><p>' + escapeHtml(item.destination_ref) + '</p></div>',
        '<div class="am-badges"><span class="am-badge ' + escapeHtml(item.status) + '">' + escapeHtml(item.status) + '</span>',
        item.is_default ? '<span class="am-badge default">Default</span>' : '',
        '</div></div>',
        '<div class="am-destination-details">',
        '<div><span>Type</span><strong>' + escapeHtml(type) + '</strong></div>',
        '<div><span>Institution</span><strong>' + escapeHtml(item.institution_name) + '</strong></div>',
        '<div><span>Account holder</span><strong>' + escapeHtml(item.account_holder_name) + '</strong></div>',
        '<div><span>Masked identifier</span><strong>' + escapeHtml(item.masked_identifier) + '</strong></div>',
        '<div><span>Validation</span><strong>' + escapeHtml(item.validation_method || 'Pending') + '</strong></div>',
        '<div><span>Effective</span><strong>' + escapeHtml(safeDate(item.effective_at)) + '</strong></div>',
        '</div>',
        item.instructions ? '<p>' + escapeHtml(item.instructions) + '</p>' : '',
        '<div class="am-destination-actions">' + destinationActions(item) + '</div>',
        '</article>',
      ].join('');
    }).join('');
  }

  async function loadDestinations(options) {
    const target = element('am-payment-destination-list');
    const nav = element('admin-marketplace-nav');
    if (target && !(options && options.quiet)) {
      target.dataset.state = 'loading';
      target.innerHTML = '<div class="am-empty">Loading payment destinations…</div>';
    }
    try {
      const result = await request(API_ROOT);
      destinations = Array.isArray(result.items) ? result.items : [];
      if (nav) nav.hidden = false;
      setAuthorityState('ready', 'Active platform administrator');
      renderDestinations();
      return true;
    } catch (error) {
      destinations = [];
      if (error.status === 403 || error.status === 401) {
        if (nav) nav.hidden = true;
        setAuthorityState('denied', error.status === 403 ? 'Platform authority required' : 'Sign-in required');
      } else {
        setAuthorityState('unavailable', 'Authority could not be verified');
      }
      if (target) {
        target.dataset.state = 'error';
        target.innerHTML = '<div class="am-empty">' + escapeHtml(reasonMessage(error)) + '</div>';
      }
      return false;
    }
  }

  function renderOrders() {
    const target = element('am-order-list');
    if (!target) return;
    if (!orders.length) {
      target.dataset.state = 'empty';
      target.innerHTML = '<div class="am-empty">No commercial orders have been created.</div>';
      return;
    }
    target.dataset.state = 'ready';
    target.innerHTML = orders.map((item) => [
      '<article class="am-destination-item">',
      '<div class="am-destination-title"><div><h4>' + escapeHtml(item.order_ref) + '</h4><p>' + escapeHtml(item.customer_ref) + '</p></div>',
      '<div class="am-badges"><span class="am-badge ' + escapeHtml(item.status) + '">' + escapeHtml(item.status) + '</span></div></div>',
      '<div class="am-destination-details">',
      '<div><span>Plan / offer</span><strong>' + escapeHtml(item.plan_ref + ' / ' + item.offer_ref) + '</strong></div>',
      '<div><span>Billing</span><strong>' + escapeHtml(item.billing_period) + '</strong></div>',
      '<div><span>Contract</span><strong>' + escapeHtml(item.contract_status) + '</strong></div>',
      '<div><span>Payment</span><strong>' + escapeHtml(item.payment_status) + '</strong></div>',
      '<div><span>Amount</span><strong>' + escapeHtml(item.total_amount + ' ' + item.currency) + '</strong></div>',
      '<div><span>Created</span><strong>' + escapeHtml(safeDate(item.created_at)) + '</strong></div>',
      '</div></article>',
    ].join('')).join('');
  }

  function renderContracts() {
    const target = element('am-contract-list');
    if (!target) return;
    if (!contracts.length) {
      target.dataset.state = 'empty';
      target.innerHTML = '<div class="am-empty">No completed contracts are recorded.</div>';
      return;
    }
    target.dataset.state = 'ready';
    target.innerHTML = contracts.map((item) => [
      '<article class="am-destination-item">',
      '<div class="am-destination-title"><div><h4>' + escapeHtml(item.contract_ref) + '</h4><p>Order ' + escapeHtml(item.order_ref) + '</p></div>',
      '<div class="am-badges"><span class="am-badge ' + escapeHtml(item.status) + '">' + escapeHtml(item.status) + '</span></div></div>',
      '<div class="am-destination-details">',
      '<div><span>Customer</span><strong>' + escapeHtml(item.customer_ref) + '</strong></div>',
      '<div><span>Version</span><strong>' + escapeHtml(item.contract_version) + '</strong></div>',
      '<div><span>Method</span><strong>' + escapeHtml(item.acceptance_method) + '</strong></div>',
      '<div><span>Evidence reference</span><strong>' + escapeHtml(item.evidence_reference) + '</strong></div>',
      '<div><span>Completed</span><strong>' + escapeHtml(safeDate(item.completed_at)) + '</strong></div>',
      '</div></article>',
    ].join('')).join('');
  }

  function renderPaymentEvidence() {
    const target = element('am-payment-evidence-list');
    if (!target) return;
    if (!paymentEvidence.length) {
      target.dataset.state = 'empty';
      target.innerHTML = '<div class="am-empty">No customer payment reports are recorded.</div>';
      return;
    }
    target.dataset.state = 'ready';
    target.innerHTML = paymentEvidence.map((item) => [
      '<article class="am-destination-item">',
      '<div class="am-destination-title"><div><h4>' + escapeHtml(item.evidence_ref) + '</h4><p>Order ' + escapeHtml(item.order_ref) + '</p></div>',
      '<div class="am-badges"><span class="am-badge ' + escapeHtml(item.status) + '">' + escapeHtml(item.status) + '</span></div></div>',
      '<div class="am-destination-details">',
      '<div><span>Customer</span><strong>' + escapeHtml(item.customer_ref) + '</strong></div>',
      '<div><span>Amount</span><strong>' + escapeHtml(item.actual_amount + ' ' + item.currency) + '</strong></div>',
      '<div><span>Safe transfer reference</span><strong>' + escapeHtml(item.safe_source_reference) + '</strong></div>',
      '<div><span>Match</span><strong>' + escapeHtml(item.match_reason_code) + '</strong></div>',
      '<div><span>Reported</span><strong>' + escapeHtml(safeDate(item.reported_at)) + '</strong></div>',
      '</div>',
      item.status === 'matched'
        ? '<div class="am-destination-actions"><button type="button" class="btn accent sm" data-am-payment-verify="' + escapeHtml(item.evidence_ref) + '">Verify payment</button></div>'
        : '<p>Verification is blocked until all server-side match gates pass.</p>',
      '</article>',
    ].join('')).join('');
  }

  async function loadCommercialList(kind) {
    const target = element(
      kind === 'orders' ? 'am-order-list' :
        (kind === 'contracts' ? 'am-contract-list' : 'am-payment-evidence-list')
    );
    if (target) {
      target.dataset.state = 'loading';
      target.innerHTML = '<div class="am-empty">Loading ' + escapeHtml(kind) + '…</div>';
    }
    try {
      const result = await request(ADMIN_MARKET_ROOT + '/' + kind);
      if (kind === 'orders') {
        orders = Array.isArray(result.items) ? result.items : [];
        renderOrders();
      } else if (kind === 'contracts') {
        contracts = Array.isArray(result.items) ? result.items : [];
        renderContracts();
      } else {
        paymentEvidence = Array.isArray(result.items) ? result.items : [];
        renderPaymentEvidence();
      }
    } catch (error) {
      if (target) {
        target.dataset.state = 'error';
        target.innerHTML = '<div class="am-empty">' + escapeHtml(reasonMessage(error)) + '</div>';
      }
    }
  }

  function confirmAction(title, message, confirmLabel) {
    const dialog = element('am-confirm-dialog');
    if (!dialog || typeof dialog.showModal !== 'function') {
      return Promise.resolve(window.confirm(message));
    }
    element('am-confirm-title').textContent = title;
    element('am-confirm-message').textContent = message;
    element('am-confirm-submit').textContent = confirmLabel || 'Confirm';
    dialog.showModal();
    return new Promise((resolve) => {
      dialog.addEventListener('close', function onClose() {
        dialog.removeEventListener('close', onClose);
        resolve(dialog.returnValue === 'confirm');
      });
    });
  }

  function requestMfa(operation) {
    pendingMfaOperation = operation;
    const dialog = element('am-mfa-dialog');
    const code = element('am-mfa-code');
    const error = element('am-mfa-error');
    if (code) code.value = '';
    if (error) error.textContent = '';
    if (dialog && typeof dialog.showModal === 'function') {
      dialog.showModal();
      if (code) code.focus();
      return;
    }
    showNotice('Recent MFA is required. Complete MFA verification and retry.', 'warning');
  }

  async function withMfaRetry(operation) {
    try {
      return await operation();
    } catch (error) {
      if (error.status === 428) {
        requestMfa(operation);
        return null;
      }
      throw error;
    }
  }

  async function submitMfa(event) {
    event.preventDefault();
    const dialog = element('am-mfa-dialog');
    const codeInput = element('am-mfa-code');
    const errorTarget = element('am-mfa-error');
    const submit = element('am-mfa-submit');
    const code = codeInput ? codeInput.value.trim() : '';
    if (codeInput) codeInput.value = '';
    if (!/^[0-9]{6,8}$/.test(code)) {
      if (errorTarget) errorTarget.textContent = 'Enter a valid authenticator code.';
      return;
    }
    setMutationLoading(submit, true, 'Verifying…');
    try {
      await request('/auth/mfa/verify', { method: 'POST', body: { code } });
      if (dialog) dialog.close();
      const operation = pendingMfaOperation;
      pendingMfaOperation = null;
      if (operation) {
        try {
          await operation();
        } catch (operationError) {
          showNotice(reasonMessage(operationError), 'error');
        }
      }
    } catch (error) {
      if (errorTarget) errorTarget.textContent = reasonMessage(error);
    } finally {
      setMutationLoading(submit, false);
    }
  }

  function createPayload(form) {
    const data = new FormData(form);
    return {
      destination_ref: String(data.get('destination_ref') || '').trim(),
      display_name: String(data.get('display_name') || '').trim(),
      destination_type: String(data.get('destination_type') || ''),
      institution_name: String(data.get('institution_name') || '').trim(),
      account_holder_name: String(data.get('account_holder_name') || '').trim(),
      raw_account_identifier: String(data.get('raw_account_identifier') || '').trim(),
      instructions: String(data.get('instructions') || '').trim() || null,
    };
  }

  async function submitCreate(event) {
    event.preventDefault();
    const form = element('am-payment-destination-form');
    const button = element('am-create-validate');
    if (!form || !form.reportValidity()) return;
    const confirmed = await confirmAction(
      'Create and validate destination?',
      'The identifier will be encrypted and cannot be edited after creation. Activation and default selection remain separate.',
      'Create & Validate'
    );
    if (!confirmed) return;
    clearNotice();
    setMutationLoading(button, true, 'Creating securely…');
    if (!pendingCreateKey) pendingCreateKey = uniqueKey('payment-destination-create');
    const operation = async function () {
      const payload = createPayload(form);
      try {
        const created = await request(API_ROOT + '/create-and-validate', {
          method: 'POST',
          headers: {
            'X-Correlation-ID': uniqueKey('admin-market-ui'),
            'Idempotency-Key': pendingCreateKey,
          },
          body: payload,
        });
        form.reset();
        clearIdentifier();
        showNotice('Payment destination created and validated. Activate it separately when ready.', 'success');
        await loadDestinations({ quiet: true });
        return created;
      } finally {
        payload.raw_account_identifier = '';
      }
    };
    try {
      await withMfaRetry(operation);
    } catch (error) {
      showNotice(reasonMessage(error), 'error');
    } finally {
      setMutationLoading(button, false);
    }
  }

  async function runLifecycle(action, destinationRef, button) {
    const labels = {
      validate: ['Validate destination?', 'Validate'],
      activate: ['Activate destination?', 'Activate'],
      'set-default': ['Set as the default destination?', 'Set default'],
      deactivate: ['Deactivate destination?', 'Deactivate'],
    };
    const [title, confirmLabel] = labels[action] || ['Confirm destination action?', 'Confirm'];
    const confirmed = await confirmAction(
      title,
      'This protected transition is enforced by platform authority, recent MFA, row locking, and audit.',
      confirmLabel
    );
    if (!confirmed) return;
    clearNotice();
    setMutationLoading(button, true, 'Working…');
    const operation = async function () {
      await request(API_ROOT + '/' + encodeURIComponent(destinationRef) + '/' + action, {
        method: 'POST',
        headers: { 'X-Correlation-ID': uniqueKey('admin-market-ui') },
        body: {},
      });
      showNotice('Payment destination state updated.', 'success');
      await loadDestinations({ quiet: true });
    };
    try {
      await withMfaRetry(operation);
    } catch (error) {
      showNotice(reasonMessage(error), 'error');
    } finally {
      setMutationLoading(button, false);
    }
  }

  async function verifyPayment(evidenceRef, button) {
    const confirmed = await confirmAction(
      'Verify this matched payment?',
      'This is the final payment decision. It requires recent MFA and moves the order to ready for activation.',
      'Verify payment'
    );
    if (!confirmed) return;
    setMutationLoading(button, true, 'Verifying…');
    const idempotencyKey = uniqueKey('payment-verification');
    const operation = async function () {
      await request(
        ADMIN_MARKET_ROOT + '/payment-evidence/' + encodeURIComponent(evidenceRef) + '/verify',
        {
          method: 'POST',
          headers: {
            'X-Correlation-ID': uniqueKey('admin-market-ui'),
            'Idempotency-Key': idempotencyKey,
          },
          body: { decision: 'verified', reason_code: 'admin_exact_match_confirmed' },
        }
      );
      showNotice('Payment verified. The order is ready for the separate activation phase.', 'success');
      await loadCommercialList('payment-evidence');
      await loadCommercialList('orders');
    };
    try {
      await withMfaRetry(operation);
    } catch (error) {
      showNotice(reasonMessage(error), 'error');
    } finally {
      setMutationLoading(button, false);
    }
  }

  function activateSection(section) {
    const name = section || 'overview';
    document.querySelectorAll('[data-am-section]').forEach((button) => {
      button.classList.toggle('active', button.dataset.amSection === name);
    });
    document.querySelectorAll('[data-am-panel]').forEach((panel) => {
      panel.classList.toggle('active', panel.dataset.amPanel === name);
    });
    if (name !== 'payment-destinations') clearIdentifier();
    if (name === 'orders') loadCommercialList('orders');
    if (name === 'contracts') loadCommercialList('contracts');
    if (name === 'payments') loadCommercialList('payment-evidence');
  }

  function bind() {
    const form = element('am-payment-destination-form');
    if (form) {
      form.addEventListener('submit', submitCreate);
      form.addEventListener('input', function () {
        pendingCreateKey = '';
        updateSubmitState();
      });
      form.addEventListener('change', function () {
        pendingCreateKey = '';
        updateSubmitState();
      });
    }
    document.querySelectorAll('[data-am-section]').forEach((button) => {
      button.addEventListener('click', () => activateSection(button.dataset.amSection));
    });
    document.querySelectorAll('[data-am-open]').forEach((button) => {
      button.addEventListener('click', () => activateSection(button.dataset.amOpen));
    });
    const refresh = element('am-refresh-destinations');
    if (refresh) refresh.addEventListener('click', () => loadDestinations());
    const refreshOrders = element('am-refresh-orders');
    if (refreshOrders) refreshOrders.addEventListener('click', () => loadCommercialList('orders'));
    const refreshContracts = element('am-refresh-contracts');
    if (refreshContracts) refreshContracts.addEventListener('click', () => loadCommercialList('contracts'));
    const refreshPayments = element('am-refresh-payments');
    if (refreshPayments) refreshPayments.addEventListener('click', () => loadCommercialList('payment-evidence'));
    const list = element('am-payment-destination-list');
    if (list) list.addEventListener('click', (event) => {
      const button = event.target.closest('[data-am-destination-action]');
      if (!button) return;
      runLifecycle(button.dataset.amDestinationAction, button.dataset.destinationRef, button);
    });
    const paymentList = element('am-payment-evidence-list');
    if (paymentList) paymentList.addEventListener('click', (event) => {
      const button = event.target.closest('[data-am-payment-verify]');
      if (!button) return;
      verifyPayment(button.dataset.amPaymentVerify, button);
    });
    const mfaForm = element('am-mfa-form');
    if (mfaForm) mfaForm.addEventListener('submit', submitMfa);
    const mfaCancel = element('am-mfa-cancel');
    if (mfaCancel) mfaCancel.addEventListener('click', () => {
      pendingMfaOperation = null;
      element('am-mfa-code').value = '';
      element('am-mfa-dialog').close();
    });
    window.addEventListener('hashchange', () => {
      if (window.location.hash !== '#admin-marketplace') clearIdentifier();
    });
    window.addEventListener('pagehide', clearIdentifier);
    updateSubmitState();
  }

  function boot() {
    bind();
    loadDestinations();
  }

  window.PMK_ADMIN_MARKETPLACE = {
    loadDestinations,
    activateSection,
    clearIdentifier,
    reasonMessage,
    loadCommercialList,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
