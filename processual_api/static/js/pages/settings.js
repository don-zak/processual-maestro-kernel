PAGES.settings = (() => {
  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value || '-';
  }

  function sessionRole() {
    return sessionStorage.getItem('maestro_role') || 'client';
  }

  function refresh() {
    loadClientSettings();
  }

  async function loadAccount() {
    try {
      const me = await CLIENT.get('/auth/me');
      setText('set-account-user', me.user_id || me.client_id || me.sub || 'current client');
      setText('set-account-role', me.role || sessionRole());
      const scopes = Array.isArray(me.scopes) ? me.scopes.join(', ') : (me.scopes || '');
      setText('set-account-session', (me.session_type || 'ui_client') + (scopes ? ' / ' + scopes : ''));
    } catch (e) {
      setText('set-account-user', 'current client');
      setText('set-account-role', sessionRole());
      setText('set-account-session', 'UI client session');
    }
  }

  function applyGeneral(general) {
    if (!general) return;
    const lang = document.getElementById('set-lang');
    const refresh = document.getElementById('set-refresh');
    const tz = document.getElementById('set-tz');
    if (lang) lang.value = general.language || 'en';
    if (refresh) refresh.value = String(general.refresh_interval || '30');
    if (tz) tz.value = general.timezone || 'UTC';
  }

  function applySubscription(sub) {
    if (!sub) return;
    setText('set-sub-plan', sub.plan || '-');
    const statusEl = document.getElementById('set-sub-status');
    if (statusEl) {
      statusEl.textContent = sub.status || '-';
      const stageColors = { active: 'var(--ok)', grace: 'var(--warn)', suspended: 'var(--error)', expired: 'var(--error)' };
      statusEl.style.color = stageColors[sub.stage] || 'var(--warn)';
    }
    setText('set-sub-renews', sub.renews_at || '-');
    const seats = sub.seats || 1;
    const maxSeats = sub.max_seats || 1;
    setText('set-sub-seats', seats + ' / ' + maxSeats);
  }
  function formatNumber(value) {
    if (value === null || value === undefined || value === '') return '-';
    const num = Number(value);
    if (Number.isFinite(num)) return num.toLocaleString();
    return String(value);
  }

  function latestUsageStatus(summary) {
    const latest = Array.isArray(summary.latest_events) ? summary.latest_events[0] : null;
    if (!latest) return 'No recent usage';

    const status = latest.status_code || latest.status || '-';
    const endpoint = latest.endpoint || latest.path || 'latest event';
    const rejected = latest.quota_rejected === true || Number(status) === 429;
    const prefix = rejected ? 'Rejected' : 'Latest';
    return prefix + ' ' + status + ' / ' + endpoint;
  }

  function applyUsageSummary(summary) {
    if (!summary) return;

    setText('set-usage-plan', summary.plan_id || summary.plan || '-');
    setText('set-usage-quota-used', formatNumber(summary.quota_used));
    setText('set-usage-quota-remaining', formatNumber(summary.quota_remaining));
    setText('set-usage-total-units', formatNumber(summary.total_units));
    setText('set-usage-rejected-requests', formatNumber(summary.rejected_requests));
    setText('set-usage-latest-status', latestUsageStatus(summary));

    const rejectedEl = document.getElementById('set-usage-rejected-requests');
    if (rejectedEl) {
      rejectedEl.style.color = Number(summary.rejected_requests || 0) > 0 ? 'var(--warn)' : '';
    }
  }

  async function loadUsageSummary() {
    try {
      const summary = await CLIENT.get('/settings/usage-summary');
      applyUsageSummary(summary);
    } catch (e) {
      setText('set-usage-latest-status', 'Usage summary unavailable');
    }
  }

  function renderIntegrationKeys(keys) {
    if (!Array.isArray(keys) || keys.length === 0) {
      return 'No integration keys issued yet. Contact the Maestro admin team to create one.';
    }

    return keys.map((key) => {
      const scopes = Array.isArray(key.scopes) ? key.scopes.join(', ') : '-';
      const quota = key.quota_limit === -1 ? 'unlimited' : formatNumber(key.quota_limit);
      const used = formatNumber(key.quota_used);
      const lastUsed = key.last_used_at || 'never';

      return [
        'key_id=' + (key.key_id || key.id || '-'),
        'prefix=' + (key.prefix || '-'),
        'status=' + (key.status || '-'),
        'scopes=' + scopes,
        'quota_used=' + used,
        'quota_limit=' + quota,
        'last_used_at=' + lastUsed,
      ].join(' | ');
    }).join('\n');
  }

  function applyApiKeyIntegration(info) {
    const card = document.getElementById('set-api-key-integration-card');
    if (!card) return;

    const enabled = info && info.enabled === true;
    card.style.display = enabled ? '' : 'none';
    if (!enabled) return;

    const keys = Array.isArray(info.keys) ? info.keys : [];
    const firstKey = keys[0] || {};
    const scopes = Array.isArray(firstKey.scopes) ? firstKey.scopes.join(', ') : '-';

    setText('set-api-key-integration-plan', info.plan_id || '-');
    setText('set-api-key-integration-status', info.status || 'available');
    setText('set-api-key-integration-count', formatNumber(info.key_count || keys.length));
    setText('set-api-key-integration-scopes', scopes);
    setText('set-api-key-integration-keys', renderIntegrationKeys(keys));
  }

  async function loadApiKeyIntegration() {
    try {
      const info = await CLIENT.get('/settings/api-key-integration');
      applyApiKeyIntegration(info);
    } catch (e) {
      applyApiKeyIntegration(null);
    }
  }


  function applyProviderConnection(info) {
    if (!info) {
      setText('set-provider-connection-status', 'Provider status unavailable');
      return;
    }

    const statusEl = document.getElementById('set-provider-connection-status');
    if (statusEl) {
      statusEl.textContent = info.status || 'not_configured';
      statusEl.style.color = info.configured ? 'var(--ok)' : 'var(--warn)';
    }

    setText('set-provider-connection-provider', info.provider || '-');
    setText('set-provider-connection-model', info.model || '-');
    setText('set-provider-connection-cost', String(info.provider_cost_included === true));

    const providers = Array.isArray(info.available_providers)
      ? info.available_providers.join(', ')
      : '-';
    setText('set-provider-connection-providers', 'Available providers: ' + providers);
    setText('set-provider-connection-note', info.message || 'Client BYOK provider status loaded.');
  }

  async function loadProviderConnection() {
    try {
      const info = await CLIENT.get('/settings/provider-connection');
      applyProviderConnection(info);
    } catch (e) {
      applyProviderConnection(null);
    }
  }


  function renderClientRequests(requests) {
    if (!Array.isArray(requests) || requests.length === 0) {
      return 'No client requests submitted yet.';
    }

    return requests.map((request) => [
      'id=' + (request.id || '-'),
      'type=' + (request.request_label || request.request_type || '-'),
      'status=' + (request.status || '-'),
      'requested_plan=' + (request.requested_plan || '-'),
      'created_at=' + (request.created_at || '-'),
    ].join(' | ')).join('\n');
  }

  function applyClientRequests(info) {
    if (!info) {
      setText('set-client-request-status', 'Request status unavailable');
      return;
    }

    const latest = Array.isArray(info.latest_requests) ? info.latest_requests : [];
    setText('set-client-request-status', 'Ready / ' + formatNumber(info.request_count || 0));
    setText('set-client-request-history', renderClientRequests(latest));
  }

  async function loadClientRequests() {
    try {
      const info = await CLIENT.get('/settings/client-requests');
      applyClientRequests(info);
    } catch (e) {
      applyClientRequests(null);
    }
  }

  async function submitClientRequest() {
    const submitBtn = document.getElementById('set-client-request-submit');
    const messageEl = document.getElementById('set-client-request-message');
    const body = {
      request_type: document.getElementById('set-client-request-type')?.value || 'general_support',
      requested_plan: document.getElementById('set-client-request-plan')?.value || null,
      message: messageEl?.value || '',
    };

    if (body.message.trim().length < 10) {
      setText('set-client-request-status', 'Message must be at least 10 characters');
      return;
    }

    if (submitBtn) submitBtn.disabled = true;
    try {
      const result = await CLIENT.post('/settings/client-request', body);
      setText('set-client-request-status', result.message || 'Request submitted');
      if (messageEl) messageEl.value = '';
      APP.showToast('Client request submitted', 'success');
      await loadClientRequests();
    } catch (e) {
      setText('set-client-request-status', 'Error: ' + (e.detail || e.message));
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  }


  function focusClientRequestsCard() {
    const card = document.getElementById('set-client-requests-card');
    if (card && typeof card.scrollIntoView === 'function') {
      card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function prepareClientSupportRequest(requestType, requestedPlan, message) {
    const typeEl = document.getElementById('set-client-request-type');
    const planEl = document.getElementById('set-client-request-plan');
    const messageEl = document.getElementById('set-client-request-message');

    if (typeEl) typeEl.value = requestType || 'general_support';
    if (planEl) planEl.value = requestedPlan || '';
    if (messageEl) messageEl.value = message || '';

    setText('set-client-request-status', 'Prepared support request. Review and submit.');
    setText('set-client-support-status', 'Support request prepared in Requests & Billing.');
    focusClientRequestsCard();
  }

  function initClientSupportActions() {
    document.getElementById('set-support-onboarding')?.addEventListener('click', () => {
      prepareClientSupportRequest(
        'general_support',
        '',
        'Please help us with onboarding next steps for this Maestro client account.'
      );
    });

    document.getElementById('set-support-provider')?.addEventListener('click', () => {
      prepareClientSupportRequest(
        'provider_setup_help',
        '',
        'Please help us set up or verify our BYOK provider connection. No provider secrets are included in this message.'
      );
    });

    document.getElementById('set-support-billing')?.addEventListener('click', () => {
      prepareClientSupportRequest(
        'billing_usage_review',
        '',
        'Please review our billing and usage status and advise on the next operational step.'
      );
    });

    document.getElementById('set-support-enterprise')?.addEventListener('click', () => {
      prepareClientSupportRequest(
        'enterprise_integration_upgrade',
        'enterprise_integration',
        'Please evaluate this client account for Enterprise Integration upgrade and integration key provisioning.'
      );
    });
  }


  async function loadClientSettings() {
    await loadAccount();
    let settings = null;
    try {
      settings = await CLIENT.get('/settings');
      applyGeneral(settings.general);
      applySubscription(settings.subscription);
    } catch (e) {
      APP.showToast('Failed to load client settings: ' + (e.detail || e.message), 'error');
    }

    try {
      const sub = await CLIENT.get('/settings/subscription');
      applySubscription(sub);
    } catch (e) {
      if (settings && settings.subscription) applySubscription(settings.subscription);
    }
    await loadUsageSummary();
    await loadApiKeyIntegration();
    await loadProviderConnection();
  }

  function init() {
    document.getElementById('set-general-save')?.addEventListener('click', async () => {
      const body = {
        language: document.getElementById('set-lang')?.value || 'en',
        refresh_interval: parseInt(document.getElementById('set-refresh')?.value || '30', 10),
        timezone: document.getElementById('set-tz')?.value || 'UTC',
      };
      try {
        await CLIENT.put('/settings/general', body);
        setText('set-general-status', 'Saved');
        APP.showToast('Client preferences saved', 'success');
      } catch (e) {
        setText('set-general-status', 'Error: ' + (e.detail || e.message));
      }
    });

    document.getElementById('set-client-request-submit')?.addEventListener('click', submitClientRequest);
    initClientSupportActions();

    document.getElementById('set-sub-manage')?.addEventListener('click', () => {
      APP.showToast('Subscription management coming soon', 'info');
    });

    refresh();
  }

  return { init, refresh };
})();
