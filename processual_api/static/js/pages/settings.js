PAGES.settings = (() => {
  const readinessState = {
    account: null,
    subscription: null,
    usage: null,
    integration: null,
    provider: null,
    requests: null,
  };

  let settingsInitDone = false;

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value || '-';
  }

  function sessionRole() {
    return sessionStorage.getItem('maestro_role') || 'client';
  }

  async function refresh() {
    loadClientSettings();
    await loadClientRequests();
  }

  function accountIdentityValue(account) {
    return account.user_id || account.client_id || account.sub || "current client";
  }

  function accountClientId(account) {
    return account.client_id || account.user_id || account.sub || "-";
  }

  function accountScopes(account) {
    const scopes = account.scopes;
    if (Array.isArray(scopes)) return scopes.join(", ");
    return scopes || "evaluation";
  }
  async function loadAccount() {
    try {
      const me = await CLIENT.get('/auth/me');
      const scopes = accountScopes(me);
      readinessState.account = me;
      updateClientReadiness();
      setText('set-account-user', accountIdentityValue(me));
      setText('set-account-role', me.role || sessionRole());
      setText('set-account-session', (me.session_type || 'ui_client') + (scopes ? ' / ' + scopes : ''));
      setText('set-account-client-id', accountClientId(me));
      setText('set-account-session-type', me.session_type || 'ui_client');
      setText('set-account-scopes', scopes);
      setText('set-account-status', 'Verified via /auth/me');
    } catch (e) {
      setText('set-account-user', 'current client');
      setText('set-account-role', sessionRole());
      setText('set-account-session', 'UI client session');
      setText('set-account-client-id', '-');
      setText('set-account-session-type', 'ui_client');
      setText('set-account-scopes', 'evaluation');
      setText('set-account-status', 'Fallback session identity');
      readinessState.account = { role: sessionRole(), fallback: true };
      updateClientReadiness();
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

  function normalizeClientPlanId(plan) {
    return String(plan || "")
      .trim()
      .toLowerCase()
      .replace(/[\s-]+/g, "_");
  }

  function clientSubscriptionPlanId(sub) {
    return sub.plan_id || sub.plan || "";
  }

  function isEnterpriseClientPlan(sub) {
    const planId = normalizeClientPlanId(clientSubscriptionPlanId(sub));
    return planId === "enterprise" || planId.indexOf("enterprise_") === 0;
  }

  function updateEnterpriseIntegrationEligibility(sub) {
    const card = document.getElementById("set-enterprise-integration-eligibility-card");
    if (!card || !sub) return;

    const planId = normalizeClientPlanId(clientSubscriptionPlanId(sub));
    const eligible = isEnterpriseClientPlan(sub);
    card.style.display = eligible ? "" : "none";
    setText("set-enterprise-integration-eligibility-plan", planId || "-");
    setText(
      "set-enterprise-integration-eligibility-status",
      eligible ? "Eligible for enterprise integration" : "Hidden for non-enterprise plans"
    );
  }
  function applySubscription(sub) {
    if (!sub) return;
    readinessState.subscription = sub;
    updateClientReadiness();
    setText('set-sub-plan', sub.plan || '-');
    updateEnterpriseIntegrationEligibility(sub);
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

  function usageSummaryPlan(summary) {
    const plan = summary.plan && typeof summary.plan === 'object' ? summary.plan : {};
    return {
      planId: plan.plan_id || summary.plan_id || summary.plan || 'unknown',
      source: plan.source || summary.plan_source || 'missing',
      pricingVersion: plan.pricing_version || summary.pricing_version || summary.pricing?.pricing_version || '-',
      billingPolicy: plan.billing_policy || summary.billing_policy || summary.pricing?.billing_policy || 'byok',
      allowance: plan.monthly_unit_allowance ?? summary.monthly_included_units ?? summary.quota_limit ?? 0,
    };
  }

  function usageSummaryUsage(summary) {
    const usage = summary.usage && typeof summary.usage === 'object' ? summary.usage : {};
    return {
      used: usage.monthly_units_used ?? summary.total_units ?? summary.quota_used ?? 0,
      allowance: usage.monthly_units_allowance ?? summary.monthly_included_units ?? summary.quota_limit ?? 0,
      remaining: usage.monthly_units_remaining ?? summary.quota_remaining,
      percent: usage.usage_percent ?? summary.usage_percent,
    };
  }

  function usageSummaryQuota(summary) {
    const quota = summary.quota && typeof summary.quota === 'object' ? summary.quota : {};
    return {
      status: quota.status || summary.quota_status || 'ok',
      nearLimit: quota.near_limit === true,
      exceeded: quota.exceeded === true,
    };
  }

  function usageSummaryProvider(summary) {
    const provider = summary.provider && typeof summary.provider === 'object' ? summary.provider : {};
    return {
      status: provider.connection_status || 'unknown',
      byokRequired: provider.byok_required === true,
      providerCostIncluded: provider.provider_cost_included === true,
      providerName: provider.provider || '-',
    };
  }

  function renderUsageRecommendations(recommendations) {
    if (!Array.isArray(recommendations) || recommendations.length === 0) {
      return 'No usage or subscription recommendations right now.';
    }

    return recommendations.map((item) => {
      const severity = item.severity || 'info';
      const kind = item.kind || 'recommendation';
      const message = item.message || '';
      return severity + ' / ' + kind + ': ' + message;
    }).join('\n');
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
    const safeSummary = summary || {};
    readinessState.usage = safeSummary;
    updateClientReadiness();

    const plan = usageSummaryPlan(safeSummary);
    const usage = usageSummaryUsage(safeSummary);
    const quota = usageSummaryQuota(safeSummary);
    const provider = usageSummaryProvider(safeSummary);

    const rejectedRequests = Number(safeSummary.rejected_requests || safeSummary.quota_rejected || 0);

    setText('set-usage-plan', plan.planId);
    setText('set-usage-plan-source', plan.source);
    setText('set-usage-monthly-included-units', formatNumber(usage.allowance));
    setText('set-usage-quota-used', formatNumber(usage.used));
    setText('set-usage-quota-remaining', usage.remaining === null || usage.remaining === undefined ? 'Not available' : formatNumber(usage.remaining));
    setText('set-usage-total-units', formatNumber(usage.used));
    setText('set-usage-rejected-requests', formatNumber(rejectedRequests));
    setText('set-usage-quota-status', quota.status + (quota.exceeded ? ' / exceeded' : (quota.nearLimit ? ' / near limit' : '')));
    setText('set-usage-percent', usage.percent === null || usage.percent === undefined ? 'Not available' : String(usage.percent) + '%');
    setText('set-usage-provider-status', provider.status + ' / ' + provider.providerName);
    setText('set-usage-recommendations', renderUsageRecommendations(safeSummary.recommendations));
    setText('set-usage-latest-status', latestUsageStatus(safeSummary));
  }

  async function loadUsageSummary() {
    try {
      const summary = await CLIENT.get('/settings/client/usage-summary');
      applyUsageSummary(summary);
    } catch (e) {
      setText('set-usage-latest-status', 'Usage summary unavailable');
    }
  }

  function prepareUsageReviewRequest() {
    const summary = readinessState.usage || {};
    const requestType = document.getElementById('set-client-request-type');
    const requestedPlan = document.getElementById('set-client-request-plan');
    const message = document.getElementById('set-client-request-message');
    const plan = usageSummaryPlan(summary);
    const usage = usageSummaryUsage(summary);
    const quota = usageSummaryQuota(summary);
    const provider = usageSummaryProvider(summary);
    const usageDetails = summary.usage && typeof summary.usage === 'object' ? summary.usage : {};
    const latestUsageAt = usageDetails.latest_usage_at || summary.latest_usage_at || 'No recent usage';
    const currentPeriod = usageDetails.current_period || summary.current_period || '-';
    const recommendations = Array.isArray(summary.recommendations)
      ? summary.recommendations.map((item) => {
          if (item && typeof item === 'object') {
            return item.message || item.kind || '';
          }
          return String(item || '');
        }).filter(Boolean)
      : [];
    const remaining = usage.remaining === null || usage.remaining === undefined
      ? 'Not available'
      : formatNumber(usage.remaining);
    const percent = usage.percent === null || usage.percent === undefined
      ? 'Not available'
      : String(usage.percent) + '%';
    const quotaState = quota.status + (quota.exceeded ? ' / exceeded' : (quota.nearLimit ? ' / near limit' : ''));
    const recommendationText = recommendations.length
      ? recommendations.join(' | ')
      : 'No usage or subscription recommendations right now.';

    if (requestType) requestType.value = 'billing_usage_review';
    if (requestedPlan) requestedPlan.value = '';

    if (message) {
      message.value = [
        'Please review our Maestro usage and quota status.',
        'plan=' + plan.planId,
        'plan_source=' + plan.source,
        'pricing_version=' + (plan.pricingVersion || '-'),
        'billing_policy=' + (plan.billingPolicy || '-'),
        'monthly_units_used=' + formatNumber(usage.used),
        'monthly_units_allowance=' + formatNumber(usage.allowance),
        'monthly_units_remaining=' + remaining,
        'usage_percent=' + percent,
        'current_period=' + currentPeriod,
        'latest_usage_at=' + latestUsageAt,
        'quota_status=' + quotaState,
        'provider_connection=' + provider.status,
        'byok_required=' + (provider.byokRequired ? 'yes' : 'no'),
        'provider_cost_included=false',
        'No provider secrets or raw keys included.',
        'recommendations=' + recommendationText,
      ].join('\n');
    }

    setText('set-usage-review-status', 'Prepared in Requests & Billing');
    const requestsCard = document.querySelector('[data-settings-section-key="requests"]');
    if (requestsCard) {
      requestsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
      const remaining = key.quota_remaining === undefined ? '-' : formatNumber(key.quota_remaining);
      const lastUsed = key.last_used_at || 'never';
      const createdAt = key.created_at || '-';

      return [
        'key_id=' + (key.key_id || key.id || '-'),
        'prefix=' + (key.prefix || '-'),
        'status=' + (key.status || '-'),
        'scopes=' + scopes,
        'quota_used=' + used,
        'quota_remaining=' + remaining,
        'quota_limit=' + quota,
        'last_used_at=' + lastUsed,
        'created_at=' + createdAt,
      ].join(' | ');
    }).join('\n');
  }

  function normalizeIntegrationOperationalProfiles(info) {   const profiles = info && Array.isArray(info.operational_profiles) ? info.operational_profiles : [];   return profiles.filter((profile) => profile && profile.client_visible === true); } function integrationProfileScopes(profile, key) {   const scopes = Array.isArray(profile && profile[key]) ? profile[key] : [];   return scopes.length ? scopes.join(", ") : "-"; } function integrationOperationalProfileLabel(profile) {   return (profile.profile_id || "-") + " / " + (profile.display_name || "Operational profile"); } function selectedIntegrationOperationalProfile(info) {   const profiles = normalizeIntegrationOperationalProfiles(info);   const select = document.getElementById("set-api-key-operational-profile-selector");   const selected = select ? select.value : "";   return profiles.find((profile) => profile.profile_id === selected) || profiles[0] || null; } function renderIntegrationOperationalProfileSelector(info) {   const select = document.getElementById("set-api-key-operational-profile-selector");   if (!select) return;   const profiles = normalizeIntegrationOperationalProfiles(info);   const previous = select.value;   select.innerHTML = "";   const placeholder = document.createElement("option");   placeholder.value = "";   placeholder.textContent = "Choose operational purpose";   select.appendChild(placeholder);   profiles.forEach((profile) => {     const option = document.createElement("option");     option.value = profile.profile_id || "";     option.textContent = integrationOperationalProfileLabel(profile);     select.appendChild(option);   });   const profileIds = profiles.map((profile) => profile.profile_id);   if (profiles.length) {     select.value = profileIds.includes(previous) ? previous : profiles[0].profile_id;   }   select.disabled = profiles.length === 0;   setText("set-api-key-operational-profile-count", formatNumber(info?.operational_profile_count ?? profiles.length));   setText("set-api-key-operational-profile-enabled", String(info?.operational_profiles_enabled === true)); } function renderSelectedIntegrationOperationalProfile(info) {   const profile = selectedIntegrationOperationalProfile(info);   if (!profile) {     setText("set-api-key-operational-profile-summary", "No operational profiles available for this client plan.");     setText("set-api-key-operational-profile-allowed-scopes", "-");     setText("set-api-key-operational-profile-forbidden-scopes", "-");     setText("set-api-key-operational-profile-readiness", "Integration readiness is required before production work.");     setText("set-api-key-operational-profile-safety", "Production connector approval remains separate. Runtime connectors are not approved from this selector. Raw integration secrets are never displayed.");     return;   }   const mode = profile.read_only === true ? "read_only" : "sandbox_write_review";   setText("set-api-key-operational-profile-summary", [     "profile_id=" + (profile.profile_id || "-"),     "display_name=" + (profile.display_name || "-"),     "base_key_profile=" + (profile.base_key_profile || "-"),     "environment=" + (profile.environment || "sandbox"),     "mode=" + mode,     "next_action=" + (profile.next_action || "-"),   ].join("\n"));   setText("set-api-key-operational-profile-allowed-scopes", integrationProfileScopes(profile, "allowed_scopes"));   setText("set-api-key-operational-profile-forbidden-scopes", integrationProfileScopes(profile, "forbidden_scopes"));   setText("set-api-key-operational-profile-readiness", [     "requires_enterprise_plan=" + String(profile.requires_enterprise_plan === true),     "requires_integration_readiness=" + String(profile.requires_integration_readiness === true),     "requires_supervisor_for_write=" + String(profile.requires_supervisor_for_write === true),     "production_allowed=" + String(profile.production_allowed === true),     "runtime_connector_approved=" + String(profile.runtime_connector_approved === true),   ].join("\n"));   setText("set-api-key-operational-profile-safety", "Production connector approval remains separate. Runtime connectors are not approved from this selector. Raw integration secrets are never displayed."); } function initIntegrationOperationalProfileSelector() {   const select = document.getElementById("set-api-key-operational-profile-selector");   if (!select || select.dataset.profileSelectorReady === "true") return;   select.dataset.profileSelectorReady = "true";   select.addEventListener("change", () => {     renderSelectedIntegrationOperationalProfile(readinessState.integration || {});   }); } function applyApiKeyIntegration(info) {
    readinessState.integration = info || null;
    updateClientReadiness();
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


  function integrationKeyRequestMessage(action) {
    const info = readinessState.integration || {};
    const keys = Array.isArray(info.keys) ? info.keys : [];
    const key = keys[0] || {};
    const actionLabels = {
      provisioning: "provisioning",
      rotation: "rotation",
      deactivation: "deactivation",
    };
    const actionLabel = actionLabels[action] || "provisioning";
    const scopes = Array.isArray(key.scopes) ? key.scopes.join(", ") : "-";

    return [
      "Please process an integration key " + actionLabel + " request.",
      "plan=" + (info.plan_id || "-"),
      "integration_status=" + (info.status || "-"),
      "active_key_count=" + formatNumber(info.key_count || keys.length),
      "target_key_id=" + (key.key_id || key.id || "-"),
      "target_prefix=" + (key.prefix || "-"),
      "target_status=" + (key.status || "-"),
      "target_scopes=" + scopes,
      "quota_limit=" + formatNumber(key.quota_limit),
      "quota_used=" + formatNumber(key.quota_used),
      "quota_remaining=" + formatNumber(key.quota_remaining),
      "last_used_at=" + (key.last_used_at || "never"),
      "created_at=" + (key.created_at || "-"),
      "No raw integration secret is included.",
    ].join("\n");
  }

  function prepareIntegrationKeyRequest(action) {
    const requestTypes = {
      provisioning: "integration_key_provisioning",
      rotation: "integration_key_rotation",
      deactivation: "integration_key_deactivation",
    };
    const requestLabels = {
      provisioning: "Integration key provisioning request prepared.",
      rotation: "Integration key rotation request prepared.",
      deactivation: "Integration key deactivation request prepared.",
    };
    const requestType = requestTypes[action] || requestTypes.provisioning;
    prepareClientSupportRequest(requestType, "", integrationKeyRequestMessage(action));
    setText("set-api-key-request-status", requestLabels[action] || requestLabels.provisioning);
    focusClientRequestsCard();
  }

  function applyProviderConnection(info) {
    readinessState.provider = info || null;
    updateClientReadiness();
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
    setText('set-provider-connection-last-tested', info.last_tested || 'never');
    setText('set-provider-connection-secret-status', info.configured ? 'stored encrypted / hidden' : 'not stored');

    const providers = Array.isArray(info.available_providers)
      ? info.available_providers.join(', ')
      : '-';
    setText('set-provider-connection-providers', 'Available providers: ' + providers);
    setText('set-provider-connection-note', info.message || 'Client BYOK provider status loaded.');
  }

  function providerSetupRequestPayload() {
    return {
      provider: document.getElementById('set-provider-setup-provider')?.value.trim() || '',
      model: document.getElementById('set-provider-setup-model')?.value.trim() || '',
    };
  }

  function providerSetupRequestMessage() {
    const body = providerSetupRequestPayload();
    return [
      'Please help configure the client BYOK provider connection.',
      'Requested provider: ' + (body.provider || 'not selected'),
      'Requested model: ' + (body.model || 'not specified'),
      'Provider policy: BYOK; provider costs are not included.',
      'Safety: no raw provider secrets are included in this request.'
    ].join('\n');
  }

  function prepareProviderSetupRequest() {
    prepareClientSupportRequest(
      'provider_setup_help',
      '',
      providerSetupRequestMessage()
    );
    setText('set-provider-setup-request-status', 'Prepared provider setup request. Review it in Requests & Billing before submitting.');
  }

  function providerSecretSetupPayload() {
    return {
      provider: document.getElementById('set-provider-setup-provider')?.value.trim() || '',
      model: document.getElementById('set-provider-setup-model')?.value.trim() || '',
      provider_secret: document.getElementById('set-provider-secret-input')?.value.trim() || '',
    };
  }

  function clearProviderSecretInput() {
    const secretInput = document.getElementById('set-provider-secret-input');
    if (secretInput) secretInput.value = '';
  }

  function setProviderSecretStatus(message) {
    setText('set-provider-setup-request-status', message);
  }

  async function testProviderSecretConnection() {
    const body = providerSecretSetupPayload();
    if (!body.provider) {
      setProviderSecretStatus('Choose a provider before testing.');
      return;
    }

    try {
      const result = await CLIENT.post('/settings/provider-connection/test', body);
      const message = result.success
        ? 'Provider connection test passed' + (result.latency_ms ? ' in ' + result.latency_ms + 'ms' : '')
        : 'Provider connection test failed: ' + (result.error || 'unknown error');
      setProviderSecretStatus(message);
      APP.showToast(message, result.success ? 'success' : 'error');
    } catch (e) {
      setProviderSecretStatus('Error testing provider: ' + (e.detail || e.message));
    } finally {
      clearProviderSecretInput();
    }
  }

  async function saveProviderSecretConnection() {
    const body = providerSecretSetupPayload();
    if (!body.provider) {
      setProviderSecretStatus('Choose a provider before saving.');
      return;
    }
    if (!body.provider_secret) {
      setProviderSecretStatus('Paste the provider key before saving. It will not be displayed after submission.');
      return;
    }

    try {
      const result = await CLIENT.put('/settings/provider-connection/setup', body);
      setProviderSecretStatus(result.message || 'Provider connection saved.');
      APP.showToast('Provider connection saved', 'success');
      clearProviderSecretInput();
      await loadProviderConnection();
    } catch (e) {
      setProviderSecretStatus('Error saving provider: ' + (e.detail || e.message));
    }
  }

  async function clearProviderSecretConnection() {
    try {
      const result = await CLIENT.del('/settings/provider-connection/setup');
      setProviderSecretStatus(result.message || 'Provider connection cleared.');
      APP.showToast('Provider connection cleared', 'success');
      clearProviderSecretInput();
      await loadProviderConnection();
    } catch (e) {
      setProviderSecretStatus('Error clearing provider: ' + (e.detail || e.message));
    }
  }

  function initProviderSecretSetupControls() {
    document.getElementById('set-provider-secret-test')?.addEventListener('click', testProviderSecretConnection);
    document.getElementById('set-provider-secret-save')?.addEventListener('click', saveProviderSecretConnection);
    document.getElementById('set-provider-secret-clear')?.addEventListener('click', clearProviderSecretConnection);
  }
  function initProviderSetupRequestControls() {
    document.getElementById('set-provider-setup-request-prepare')?.addEventListener('click', prepareProviderSetupRequest);
  }
  async function loadProviderConnection() {
    try {
      const info = await CLIENT.get('/settings/provider-connection');
      applyProviderConnection(info);
    } catch (e) {
      applyProviderConnection(null);
    }
  }


  function clientRequestTypeLabel(value) {
    const labels = {
      enterprise_integration_upgrade: 'Enterprise integration upgrade',
      integration_key_provisioning: 'Integration key provisioning',
      integration_key_rotation: 'Integration key rotation',
      integration_key_deactivation: 'Integration key deactivation',
      provider_setup_help: 'Provider setup help',
      billing_usage_review: 'Billing and usage review',
      general_support: 'General support',
    };
    return labels[value] || labels.general_support;
  }

  function clientRequestStatusLabel(status) {
    const labels = {
      pending: "Pending admin review",
      reviewed: "Admin review started",
      approved: "Approved for follow-up",
      rejected: "Rejected or needs revision",
      completed: "Completed",
    };
    return labels[status] || labels.pending;
  }

  function clientRequestStatusRank(status) {
    const ranks = {
      pending: 0,
      reviewed: 1,
      approved: 2,
      rejected: 2,
      completed: 3,
    };
    return ranks[status] === undefined ? 0 : ranks[status];
  }

  function clientRequestStatusStages(status) {
    if (status === "rejected") {
      return ["pending", "reviewed", "rejected"];
    }
    return ["pending", "reviewed", "approved", "completed"];
  }

  function latestClientRequest(requests) {
    if (!Array.isArray(requests) || requests.length === 0) {
      return null;
    }
    return requests[0];
  }

  function clientRequestSummaryLine(request) {
    if (!request) {
      return "No client requests yet";
    }

    const requestId = String(request.request_id || request.id || "");
    const shortId = request.short_id || (requestId ? requestId.slice(0, 8) : "-");
    const requestType = request.request_type || "general_support";
    const requestTypeLabel = request.request_type_label || clientRequestTypeLabel(requestType);
    const requestedPlan = request.requested_plan || "none";
    const status = request.status || "pending";
    const createdAt = request.created_at || "-";

    return [
      "Latest request",
      "short_id=" + shortId,
      "type=" + requestTypeLabel,
      "status=" + clientRequestStatusLabel(status),
      "requested_plan=" + requestedPlan,
      "created_at=" + createdAt,
    ].join(" | ");
  }


  function clientRequestSupervisorResponses(request) {
    const responses = Array.isArray(request?.supervisor_responses)
      ? request.supervisor_responses
      : [];
    const seen = new Set();
    return responses.filter((response) => {
      const key = response?.draft_id ||
        response?.response_id ||
        [response?.sent_at || "", response?.body || ""].join("|");
      if (!key) return true;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function renderClientRequestSupervisorResponses(request) {
    const responses = clientRequestSupervisorResponses(request);
    if (!responses.length) return "";

    const lines = responses.map((response) => {
      return [
        "supervisor_response_sent",
        response.sent_at || "-",
        response.source || "supervisor_panel",
        "Supervisor response",
        response.body || "",
      ].join(" | ");
    });

    return ["Supervisor response timeline"].concat(lines).join("\n");
  }

  function renderClientRequestStatusTimeline(requests) {
    const request = latestClientRequest(requests);
    if (!request) {
      return "No client request timeline yet. Submit a request to create one.";
    }

    const status = request.status || "pending";
    const rank = clientRequestStatusRank(status);
    const stages = clientRequestStatusStages(status);
    const lines = stages.map((stage) => {
      const prefix = stage === status ? "> " : (clientRequestStatusRank(stage) < rank ? "✓ " : "- ");
      return prefix + stage + ": " + clientRequestStatusLabel(stage);
    });

    const supervisorResponses = renderClientRequestSupervisorResponses(request);
    if (supervisorResponses) {
      lines.push(supervisorResponses);
    }

    return ["Latest request status timeline"].concat(lines).join("\n");
  }

  function clientRequestNextSafeAction(requests) {
    const request = latestClientRequest(requests);
    if (!request) {
      return "Submit a request through Requests & Billing when support, billing, provider, or integration help is needed.";
    }

    const status = request.status || "pending";
    if (status === "completed") {
      return "No action required. Monitor usage, provider status, and integration access.";
    }
    if (status === "rejected") {
      return "Review admin follow-up, then submit a revised client-safe request if needed.";
    }
    if (status === "approved") {
      return "Wait for admin execution or supervisor follow-up. Do not paste provider secrets or raw integration keys.";
    }
    if (status === "reviewed") {
      return "Wait for admin follow-up or send a supervisor message with client-safe context.";
    }
    return "Wait for admin review. You can send a supervisor message if the request is urgent.";
  }
  function renderClientRequests(requests) {
    if (!Array.isArray(requests) || requests.length === 0) {
      return 'No client requests submitted yet. Submitted requests will appear here newest first.';
    }

    return requests.map((request, index) => {
      const requestId = String(request.request_id || request.id || '');
      const shortId = request.short_id || (requestId ? requestId.slice(0, 8) : '-');
      const requestType = request.request_type || 'general_support';
      const requestTypeLabel = request.request_type_label || clientRequestTypeLabel(requestType);
      const requestedPlan = request.requested_plan || 'none';
      const status = request.status || 'pending';
      const createdAt = request.created_at || '-';
      const source = request.source || 'client';

      return [
        '#' + (index + 1),
        'short_id=' + shortId,
        'type=' + requestTypeLabel,
        'request_type=' + requestType,
        'requested_plan=' + requestedPlan,
        'status=' + status,
        'created_at=' + createdAt,
        'source=' + source,
      ].join(' | ');
    }).join('\n');
  }

  function applyClientRequests(info) {
    readinessState.requests = info || null;
    updateClientReadiness();
    if (!info) {
      setText('set-client-request-status', 'Request status unavailable');
      setText('set-client-request-latest-summary', 'Request summary unavailable');
      setText('set-client-request-timeline', 'Request timeline unavailable');
      setText('set-client-request-next-action', 'Reload requests or contact support if this persists.');
      return;
    }

    const latest = Array.isArray(info.latest_requests) ? info.latest_requests : [];
    const latestCount = Array.isArray(info.latest_requests) ? info.latest_requests.length : 0;
    setText(
      'set-client-request-status',
      'Ready / ' + formatNumber(info.request_count || 0) + ' requests / latest ' + formatNumber(latestCount)
    );
    setText('set-client-request-latest-summary', clientRequestSummaryLine(latestClientRequest(latest)));
    setText('set-client-request-timeline', renderClientRequestStatusTimeline(latest));
    setText('set-client-request-next-action', clientRequestNextSafeAction(latest));
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

  function focusSupervisorMessagesCard() {
    const card = document.getElementById('set-client-support-card');
    if (card && typeof card.scrollIntoView === 'function') {
      card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function prepareClientSupportRequest(requestType, requestedPlan, message) {
    const typeEl = document.getElementById('set-client-request-type');
    const planEl = document.getElementById('set-client-request-plan');
    const messageEl = document.getElementById('set-client-request-message');
    const supervisorTypeEl = document.getElementById('set-supervisor-message-type');
    const supervisorPlanEl = document.getElementById('set-supervisor-message-plan');
    const supervisorMessageEl = document.getElementById('set-supervisor-message-body');

    if (typeEl) typeEl.value = requestType || 'general_support';
    if (planEl) planEl.value = requestedPlan || '';
    if (messageEl) messageEl.value = message || '';

    if (supervisorTypeEl) supervisorTypeEl.value = requestType || 'general_support';
    if (supervisorPlanEl) supervisorPlanEl.value = requestedPlan || '';
    if (supervisorMessageEl) supervisorMessageEl.value = message || '';

    setText('set-client-request-status', 'Prepared support request. Review and submit.');
    setText('set-supervisor-message-status', 'Prepared supervisor message. Review and send.');
    focusSupervisorMessagesCard();
  }

  async function sendSupervisorMessage() {
    const sendBtn = document.getElementById('set-supervisor-message-send');
    const bodyEl = document.getElementById('set-supervisor-message-body');
    const body = {
      request_type: document.getElementById('set-supervisor-message-type')?.value || 'general_support',
      requested_plan: document.getElementById('set-supervisor-message-plan')?.value || null,
      message: bodyEl?.value || '',
    };

    if (body.message.trim().length < 10) {
      setText('set-supervisor-message-status', 'Message must be at least 10 characters');
      return;
    }

    if (sendBtn) sendBtn.disabled = true;
    try {
      const result = await CLIENT.post('/settings/client-request', body);
      setText('set-supervisor-message-status', result.message || 'Supervisor message sent');
      setText('set-client-request-status', result.message || 'Supervisor message sent');
      if (bodyEl) bodyEl.value = '';
      APP.showToast('Supervisor message sent', 'success');
      await loadClientRequests();
    } catch (e) {
      setText('set-supervisor-message-status', 'Error: ' + (e.detail || e.message));
    } finally {
      if (sendBtn) sendBtn.disabled = false;
    }
  }

  function prefillSupervisorReadinessReview() {
    prepareClientSupportRequest(
      'general_support',
      '',
      'Please review this client account readiness checklist and advise on the next setup step.'
    );
  }

  function initClientSupportActions() {
    document.getElementById('set-supervisor-message-send')?.addEventListener('click', sendSupervisorMessage);
    document.getElementById('set-supervisor-message-prefill')?.addEventListener('click', prefillSupervisorReadinessReview);
  }

  function readinessLine(ok, label, status) {
    return (ok ? '✓ ' : '! ') + label + ': ' + status;
  }

  function clientLaunchOwner(action) {
    const owners = {
      reload: "Client",
      plan: "Client and admin",
      usage: "Client",
      provider: "Client",
      integration: "Admin",
      requests: "Admin",
      complete: "Client",
    };
    return owners[action] || "Client";
  }

  function clientLaunchActionLabel(action) {
    const labels = {
      reload: "Reload client settings",
      plan: "Prepare plan review request",
      usage: "Open usage review request",
      provider: "Prepare provider setup request",
      integration: "Request integration key provisioning",
      requests: "Open Requests & Billing",
      complete: "Open Requests & Billing",
    };
    return labels[action] || labels.requests;
  }

  function buildClientLaunchSteps(integration, provider, requests) {
    const accountOk = Boolean(readinessState.account);
    const planOk = Boolean(readinessState.subscription);
    const usageOk = Boolean(readinessState.usage);
    const planStatus = planOk
      ? ((readinessState.subscription.plan || readinessState.subscription.plan_id || "-") + " / " + (readinessState.subscription.status || "-"))
      : "loading";

    return [
      { ok: accountOk, label: "1. Confirm client account session", status: accountOk ? "verified" : "reload account session", action: "reload" },
      { ok: planOk, label: "2. Confirm active plan", status: planStatus, action: "plan" },
      { ok: usageOk, label: "3. Review usage and quota summary", status: usageOk ? "available" : "loading", action: "usage" },
      { ok: provider.ok, label: "4. Connect BYOK provider", status: provider.status, action: "provider" },
      { ok: integration.ok, label: "5. Prepare integration access", status: integration.status, action: "integration" },
      { ok: requests.ok, label: "6. Track requests and admin follow-up", status: requests.status, action: "requests" },
    ];
  }

  function clientLaunchStepLine(step) {
    return (step.ok ? "✓ " : "! ") + step.label + ": " + step.status;
  }

  function renderClientLaunchPath(integration, provider, requests) {
    const steps = buildClientLaunchSteps(integration, provider, requests);
    const current = steps.find((step) => !step.ok) || {
      ok: true,
      label: "Client workspace is ready",
      status: "monitor usage and requests",
      action: "complete",
    };

    setText("set-launch-current-step", current.label + " / " + current.status);
    setText("set-launch-owner", clientLaunchOwner(current.action));
    setText("set-launch-action-status", "Next action: " + clientLaunchActionLabel(current.action));
    setText("set-launch-checklist", steps.map(clientLaunchStepLine).join("\n"));
    renderClientWorkspaceActionCenter(integration, provider, requests, current);

    const primary = document.getElementById("set-launch-primary-action");
    if (primary) {
      primary.dataset.launchAction = current.action;
      primary.textContent = clientLaunchActionLabel(current.action);
    }
  }

  function handleClientLaunchPrimaryAction() {
    const action = document.getElementById("set-launch-primary-action")?.dataset.launchAction || "requests";

    if (action === "reload") {
      setText("set-launch-action-status", "Reloading client settings...");
      loadClientSettings();
      return;
    }

    if (action === "plan") {
      prepareClientSupportRequest(
        "enterprise_integration_upgrade",
        "enterprise_integration",
        "Please review this client workspace plan and confirm the next launch step. No provider secrets or raw integration keys are included."
      );
      setText("set-launch-action-status", "Plan review request prepared in Requests & Billing.");
      focusClientRequestsCard();
      return;
    }

    if (action === "usage") {
      prepareUsageReviewRequest();
      setText("set-launch-action-status", "Usage review request prepared in Requests & Billing.");
      focusClientRequestsCard();
      return;
    }

    if (action === "provider") {
      prepareProviderSetupRequest();
      setText("set-launch-action-status", "Provider setup request prepared in Requests & Billing.");
      focusClientRequestsCard();
      return;
    }

    if (action === "integration") {
      prepareIntegrationKeyRequest("provisioning");
      setText("set-launch-action-status", "Integration key provisioning request prepared.");
      focusClientRequestsCard();
      return;
    }

    focusClientRequestsCard();
    setText("set-launch-action-status", "Requests & Billing opened for follow-up.");
  }

  function openClientLaunchRequests() {
    focusClientRequestsCard();
    setText("set-launch-action-status", "Requests & Billing opened for follow-up.");
  }

  function initClientLaunchActions() {
    bindClientWorkspaceActionButton("set-launch-primary-action", handleClientLaunchPrimaryAction);
    bindClientWorkspaceActionButton("set-launch-secondary-action", openClientLaunchRequests);
    bindClientWorkspaceActionButton("set-action-center-provider-action", prepareActionCenterProviderSetup);
    bindClientWorkspaceActionButton("set-action-center-usage-action", prepareActionCenterUsageReview);
    bindClientWorkspaceActionButton("set-action-center-integration-action", prepareActionCenterIntegrationKey);
    bindClientWorkspaceActionButton("set-action-center-requests-action", openActionCenterRequests);
  }
  function clientWorkspacePendingFollowUpCount(requests) {
    const info = requests || {};
    const counts = info.status_counts || {};
    if (counts.pending !== undefined) {
      return Number(counts.pending || 0);
    }

    const latest = Array.isArray(info.latest_requests) ? info.latest_requests : [];
    return latest.filter((request) => (request.status || "pending") !== "completed").length;
  }

  function clientWorkspaceLatestRequestSummary(requests) {
    const info = requests || {};
    const latest = Array.isArray(info.latest_requests) ? info.latest_requests : [];
    const request = latest[0];
    if (!request) {
      return "No client requests yet";
    }

    const requestType = request.request_type || "general_support";
    const requestLabel = request.request_type_label || clientRequestTypeLabel(requestType);
    const status = request.status || "pending";
    const shortId = request.short_id || String(request.request_id || request.id || "-").slice(0, 8);
    return requestLabel + " / " + status + " / " + shortId;
  }

  function renderClientWorkspaceActionCenter(integration, provider, requests, current) {
    const activeStep = current || { action: "requests", label: "Client workspace", status: "ready" };
    const pending = clientWorkspacePendingFollowUpCount(requests);
    const latestSummary = clientWorkspaceLatestRequestSummary(requests);

    setText("set-action-center-next", clientLaunchActionLabel(activeStep.action));
    setText("set-action-center-owner", clientLaunchOwner(activeStep.action));
    setText("set-action-center-pending", formatNumber(pending));
    setText("set-action-center-last-request", latestSummary);
    setText("set-action-center-provider", provider.status);
    setText("set-action-center-integration", integration.status);
    setText("set-action-center-status", "Ready / " + clientLaunchActionLabel(activeStep.action));
  }

  function bindClientWorkspaceActionButton(id, handler) {
    const button = document.getElementById(id);
    if (!button || button.dataset.workspaceActionBound === "1") {
      return;
    }
    button.dataset.workspaceActionBound = "1";
    button.addEventListener("click", handler);
  }

  function prepareActionCenterProviderSetup() {
    prepareProviderSetupRequest();
    setText("set-action-center-status", "Provider setup request prepared in Requests & Billing.");
    focusClientRequestsCard();
  }

  function prepareActionCenterUsageReview() {
    prepareUsageReviewRequest();
    setText("set-action-center-status", "Usage review request prepared in Requests & Billing.");
    focusClientRequestsCard();
  }

  function prepareActionCenterIntegrationKey() {
    prepareIntegrationKeyRequest("provisioning");
    setText("set-action-center-status", "Integration key provisioning request prepared.");
    focusClientRequestsCard();
  }

  function openActionCenterRequests() {
    focusClientRequestsCard();
    setText("set-action-center-status", "Requests & Billing opened for follow-up.");
  }

  function integrationReadiness() {
    const integration = readinessState.integration;
    if (!integration) return { ok: false, status: 'loading' };
    if (integration.enabled !== true) {
      return { ok: true, status: 'not included in current plan' };
    }
    const keyCount = Number(integration.key_count || 0);
    if (keyCount > 0) {
      return { ok: true, status: 'ready / ' + formatNumber(keyCount) + ' key(s)' };
    }
    return { ok: false, status: 'enabled / key provisioning pending' };
  }

  function providerReadiness() {
    const provider = readinessState.provider;
    if (!provider) return { ok: false, status: 'loading' };
    if (provider.configured === true) {
      return { ok: true, status: provider.provider || 'configured' };
    }
    return { ok: false, status: 'BYOK provider not configured' };
  }

  function requestsReadiness() {
    const requests = readinessState.requests;
    if (!requests) return { ok: false, status: 'loading' };
    return {
      ok: true,
      status: 'ready / ' + formatNumber(requests.request_count || 0) + ' request(s)',
    };
  }

  function nextReadinessStep(integration, provider, requests) {
    if (!readinessState.account) return 'Reload account session';
    if (!readinessState.subscription) return 'Confirm active plan';
    if (!readinessState.usage) return 'Wait for usage summary';
    if (!provider.ok) return 'Prepare provider setup request';
    if (!integration.ok) return 'Request integration key provisioning';
    if (requests.status.indexOf('0 request') === -1) return 'Wait for admin follow-up';
    return 'Client console is ready; monitor usage and requests';
  }

  function updateClientReadiness() {
    const integration = integrationReadiness();
    const provider = providerReadiness();
    const requests = requestsReadiness();
    const accountOk = Boolean(readinessState.account);
    const planOk = Boolean(readinessState.subscription);
    const usageOk = Boolean(readinessState.usage);

    const checks = [
      {
        ok: accountOk,
        label: 'Account session',
        status: accountOk ? 'loaded' : 'loading',
      },
      {
        ok: planOk,
        label: 'Plan status',
        status: planOk ? (readinessState.subscription.status || 'loaded') : 'loading',
      },
      {
        ok: usageOk,
        label: 'Usage summary',
        status: usageOk ? 'available' : 'loading',
      },
      {
        ok: integration.ok,
        label: 'Integration key',
        status: integration.status,
      },
      {
        ok: provider.ok,
        label: 'BYOK provider',
        status: provider.status,
      },
      {
        ok: requests.ok,
        label: 'Requests workflow',
        status: requests.status,
      },
    ];

    const readyCount = checks.filter((check) => check.ok).length;
    const score = Math.round((readyCount / checks.length) * 100);

    setText('set-readiness-score', score + '% ready');
    setText('set-readiness-next-step', nextReadinessStep(integration, provider, requests));
    setText('set-readiness-account', accountOk ? 'Ready' : 'Loading');
    setText(
      'set-readiness-plan',
      planOk
        ? ((readinessState.subscription.plan || readinessState.subscription.plan_id || '-') + ' / ' + (readinessState.subscription.status || '-'))
        : 'Loading'
    );
    setText('set-readiness-integration', integration.status);
    setText('set-readiness-provider', provider.status);
    setText(
      'set-readiness-checklist',
      checks.map((check) => readinessLine(check.ok, check.label, check.status)).join('\n')
    );
    renderClientLaunchPath(integration, provider, requests);
  }

  function prepareReadinessSupportRequest() {
    prefillSupervisorReadinessReview();
  }

  function clientIntegrationGuideText(kind) {
    const baseUrl = window.location.origin || '<maestro-base-url>';
    if (kind === 'checklist') {
      return [
        'Maestro client readiness checklist',
        '1. Confirm account session is loaded.',
        '2. Confirm active plan and usage summary.',
        '3. Confirm integration key provisioning status.',
        '4. Confirm BYOK provider status.',
        '5. Submit a support request for missing setup steps.',
        '6. Never paste raw provider secrets or raw integration keys in support notes.',
      ].join('\n');
    }

    return [
      'Maestro client integration quickstart',
      'Base URL: ' + baseUrl,
      'Auth header: Authorization: Bearer <client-integration-key>',
      'Provider policy: BYOK; provider costs are not included.',
      'Usage: monitor Usage & Quotas before production rollout.',
      'Support: use Requests & Billing for setup or upgrade help.',
      'Safety: use placeholders only; never paste raw secrets.',
    ].join('\n');
  }

  async function copyClientIntegrationGuide(kind) {
    const text = clientIntegrationGuideText(kind);
    setText('set-guide-base-url', window.location.origin || '<maestro-base-url>');
    setText('set-guide-output', text);

    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        APP.showToast('Integration guide copied', 'success');
      } else {
        APP.showToast('Integration guide prepared', 'info');
      }
    } catch (e) {
      APP.showToast('Integration guide prepared', 'info');
    }
  }

  function prepareIntegrationGuideSupportRequest() {
    prepareClientSupportRequest(
      'provider_setup_help',
      '',
      'Please help us complete the client integration setup using the copy-safe integration guide. No raw secrets are included in this message.'
    );
  }

  function initClientIntegrationGuide() {
    setText('set-guide-base-url', window.location.origin || '<maestro-base-url>');

    document.getElementById('set-guide-copy-quickstart')?.addEventListener('click', () => {
      copyClientIntegrationGuide('quickstart');
    });

    document.getElementById('set-guide-copy-checklist')?.addEventListener('click', () => {
      copyClientIntegrationGuide('checklist');
    });

    document.getElementById('set-guide-support')?.addEventListener('click', prepareIntegrationGuideSupportRequest);
  }


  function settingsPageRoot() {
    return (
      document.querySelector('#page-settings .settings-sections') ||
      document.querySelector('.settings-sections') ||
      document.getElementById('page-settings') ||
      document
    );
  }

  function settingsSectionBodyNodes(card) {
    return Array.from(card.children).filter((child) => !child.classList.contains('sec-hdr'));
  }

  function setSettingsSectionCollapsed(card, collapsed) {
    const bodyNodes = settingsSectionBodyNodes(card);
    bodyNodes.forEach((node) => {
      node.hidden = collapsed;
    });

    card.dataset.collapsed = collapsed ? 'true' : 'false';

    const toggle = card.querySelector('[data-settings-section-toggle="true"]');
    if (toggle) {
      toggle.textContent = collapsed ? 'Show' : 'Hide';
      toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    }
  }

  function settingsSectionCards() {
    return Array.from(settingsPageRoot().querySelectorAll('.settings-section'));
  }

  function collapseSettingsSections(collapseAll) {
    settingsSectionCards().forEach((card) => {
      const keepOpen = card.id === 'set-client-readiness-card';
      setSettingsSectionCollapsed(card, collapseAll && !keepOpen);
    });
    setText(
      'set-sections-collapse-status',
      collapseAll ? 'Collapsed non-readiness sections' : 'Expanded all sections'
    );
  }

  function initSettingsSectionNavigation() {
  const root = settingsPageRoot();
  const navButtons = Array.from(
    root.querySelectorAll("[data-settings-nav-target]")
  );

  if (!navButtons.length) {
    return;
  }

  navButtons.forEach((button) => {
    button.onclick = () => {
      const targetKey = button.getAttribute("data-settings-nav-target");
      const target = root.querySelector(
        `[data-settings-section-key="${targetKey}"]`
      );

      if (!target) {
        return;
      }

      navButtons.forEach((item) => {
        item.classList.remove("settings-section-nav__button--active");
        item.classList.remove("accent");
      });
      button.classList.add("settings-section-nav__button--active");
      button.classList.add("accent");

      target.scrollIntoView({ behavior: "smooth", block: "start" });
    };
  });
}

function initCollapsibleSettingsSections() {
    settingsSectionCards().forEach((card) => {
      const header = card.querySelector('.sec-hdr');
      if (!header) return;

      let toggle = header.querySelector('[data-settings-section-toggle="true"]');
      if (!toggle) {
        toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'btn sm';
        toggle.dataset.settingsSectionToggle = 'true';
        toggle.style.marginLeft = 'auto';
        header.appendChild(toggle);
      }

      toggle.textContent = card.dataset.collapsed === 'true' ? 'Show' : 'Hide';
      toggle.setAttribute('aria-expanded', card.dataset.collapsed === 'true' ? 'false' : 'true');
      toggle.onclick = () => {
        const collapsed = card.dataset.collapsed !== 'true';
        setSettingsSectionCollapsed(card, collapsed);
      };
    });

    const expandButton = document.getElementById('set-sections-expand');
    if (expandButton) {
      expandButton.type = 'button';
      expandButton.onclick = () => collapseSettingsSections(false);
    }

    const collapseButton = document.getElementById('set-sections-collapse');
    if (collapseButton) {
      collapseButton.type = 'button';
      collapseButton.onclick = () => collapseSettingsSections(true);
    }

    setText('set-sections-collapse-status', 'Sections are ready');
  }

  function initUsageReviewRequestWorkflow() {
    const button = document.getElementById('set-usage-review-request');
    if (button) {
      button.type = 'button';
      button.onclick = prepareUsageReviewRequest;
    }
  }

  function initIntegrationKeyRequestWorkflow() {
    document.getElementById("set-api-key-request-provisioning")?.addEventListener("click", () => {
      prepareIntegrationKeyRequest("provisioning");
    });
    document.getElementById("set-api-key-request-rotation")?.addEventListener("click", () => {
      prepareIntegrationKeyRequest("rotation");
    });
    document.getElementById("set-api-key-request-deactivation")?.addEventListener("click", () => {
      prepareIntegrationKeyRequest("deactivation");
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
    if (settingsInitDone) {
      initCollapsibleSettingsSections();
  initSettingsSectionNavigation();
      initUsageReviewRequestWorkflow();
      initIntegrationKeyRequestWorkflow();
    initClientLaunchActions();
      refresh();
      return;
    }
    settingsInitDone = true;

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
    initClientIntegrationGuide();
    initProviderSetupRequestControls();
    initProviderSecretSetupControls();
    document.getElementById('set-readiness-support')?.addEventListener('click', prepareReadinessSupportRequest);
    initCollapsibleSettingsSections();
  initSettingsSectionNavigation();
      initUsageReviewRequestWorkflow();
      initIntegrationKeyRequestWorkflow();
    initClientLaunchActions();

    document.getElementById('set-sub-manage')?.addEventListener('click', () => {
      APP.showToast('Subscription management coming soon', 'info');
    });

    refresh();
  }

  return { init, refresh };
})();
