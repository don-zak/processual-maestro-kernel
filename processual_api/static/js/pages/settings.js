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

    document.getElementById('set-sub-manage')?.addEventListener('click', () => {
      APP.showToast('Subscription management coming soon', 'info');
    });

    refresh();
  }

  return { init, refresh };
})();
