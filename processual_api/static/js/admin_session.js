document.addEventListener('DOMContentLoaded', () => {
  const EVALUATION_SCRIPT_SELECTOR = 'script[data-admin-evaluation-grants]';
  const EVALUATION_SCRIPT_SRC = '/console/js/admin_evaluation_grants.js?v=admineval-authority-v2';
  const API_KEY_WORKSPACE_SCRIPT_SELECTOR = 'script[data-admin-api-key-provisioning-workspace]';
  const API_KEY_WORKSPACE_SCRIPT_SRC = '/console/js/admin_api_key_provisioning_workspace.js?v=adminapikeyworkspace-authority-v2';
  const API_KEY_EVALUATION_LIFECYCLE_SCRIPT_SELECTOR = 'script[data-admin-api-key-evaluation-lifecycle]';
  const API_KEY_EVALUATION_LIFECYCLE_SCRIPT_SRC = '/console/js/admin_api_key_evaluation_lifecycle.js?v=adminapikevaluation-authority-v2';
  const API_KEY_LIFECYCLE_CARD_ID = 'admin-api-key-lifecycle-card';
  const EVALUATION_CARD_ID = 'admin-api-key-external-evaluation-card';
  const EVALUATION_BODY_ID = 'admin-api-key-external-evaluation-body';
  const EVALUATION_HOST_ID = 'admin-evaluation-grants';
  const PROVISIONING_WORKSPACE_ID = 'admin-api-key-provisioning-workspace';
  const EXTERNAL_CATEGORY = 'external_evaluation';
  const AUTHORITY_ENDPOINT = '/settings/admin/evaluation-grants/authority';
  const SESSION_REFRESH_ENDPOINT = '/auth/session/refresh';
  const CSRF_COOKIE = 'pmk_csrf_token';
  const SESSION_RETRY_DELAYS_MS = [400, 1200, 2500];
  const EXTERNAL_ENTRY_RETRY_MS = 100;
  const EXTERNAL_ENTRY_MAX_ATTEMPTS = 80;
  let refreshInFlight = null;
  let externalEntryAttempts = 0;
  let externalEntryActivated = false;

  function externalEvaluationSelected() {
    return document.getElementById('admin-api-key-category')?.value === EXTERNAL_CATEGORY;
  }

  function authorityHeaders() {
    if (window.PMK_ADMIN_AUTH && typeof window.PMK_ADMIN_AUTH.headers === 'function') {
      return window.PMK_ADMIN_AUTH.headers({ Accept: 'application/json' });
    }
    return new Headers({ Accept: 'application/json' });
  }

  function cookieValue(name) {
    const prefix = `${encodeURIComponent(name)}=`;
    return document.cookie
      .split(';')
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => part.startsWith(prefix) ? decodeURIComponent(part.slice(prefix.length)) : '')
      .find(Boolean) || '';
  }

  function setExternalEvaluationSurfaceVisibility(selected) {
    const supervisorPanel = document.getElementById('admin-supervisor-session-key-panel');
    const supervisorAudit = document.getElementById('admin-supervisor-audit-summary');
    const lifecycleSummary = document.getElementById('admin-api-key-lifecycle-summary');
    const page = document.getElementById('page-admin-api-keys');
    const staticStandardBlock = page?.firstElementChild;

    [supervisorPanel, supervisorAudit, lifecycleSummary, staticStandardBlock].forEach((node) => {
      if (!node) return;
      if (node.dataset.externalEvaluationPreviousDisplay === undefined) {
        node.dataset.externalEvaluationPreviousDisplay = node.style.display || '';
        node.dataset.externalEvaluationPreviousHidden = node.hidden ? 'true' : 'false';
      }
      if (selected) {
        node.hidden = true;
        node.style.display = 'none';
      } else {
        node.hidden = node.dataset.externalEvaluationPreviousHidden === 'true';
        node.style.display = node.dataset.externalEvaluationPreviousDisplay || '';
      }
    });
  }

  function placeEvaluationWorkspaceInsideCard() {
    if (!externalEvaluationSelected()) return;
    const body = document.getElementById(EVALUATION_BODY_ID);
    const host = document.getElementById(EVALUATION_HOST_ID);
    const workspace = document.getElementById(PROVISIONING_WORKSPACE_ID);
    if (!body || !workspace) return;
    if (workspace.parentElement !== body) body.insertBefore(workspace, host || body.firstChild);
  }

  function ensureEvaluationGrantPlaceholder() {
    let host = document.getElementById(EVALUATION_HOST_ID);
    if (host) return host;
    const lifecycleCard = document.getElementById(API_KEY_LIFECYCLE_CARD_ID);
    if (!lifecycleCard) return null;

    let card = document.getElementById(EVALUATION_CARD_ID);
    if (!card) {
      card = document.createElement('section');
      card.id = EVALUATION_CARD_ID;
      card.className = 'card flat';
      card.style.marginTop = 'var(--s-4)';
      card.hidden = true;
      card.dataset.activated = 'false';
      card.innerHTML = `
        <div class="sec-hdr">
          <div class="sh-title">External Evaluation Authority</div>
          <div class="sh-sub">platform admin → governed grant → one-time key → sandbox execution → evidence → revocation</div>
        </div>
        <div class="admin-note">
          PostgreSQL-backed Evaluation authority is authoritative. Browser role labels and legacy admin tokens are not accepted as grant authority.
        </div>
        <div id="${EVALUATION_BODY_ID}" hidden style="margin-top:var(--s-3)">
          <div id="${EVALUATION_HOST_ID}" class="card flat" data-evaluation-grant-placeholder="true">
            <div class="admin-note" data-evaluation-access-status>Verifying active Platform Administrator authority…</div>
          </div>
        </div>`;
      const lifecycleForm = lifecycleCard.querySelector('.admin-grid');
      if (lifecycleForm) lifecycleCard.insertBefore(card, lifecycleForm);
      else lifecycleCard.appendChild(card);
    }
    return document.getElementById(EVALUATION_HOST_ID);
  }

  function syncEvaluationSelectionState() {
    const card = document.getElementById(EVALUATION_CARD_ID);
    const body = document.getElementById(EVALUATION_BODY_ID);
    if (!card || !body) return;
    const selected = externalEvaluationSelected();
    card.hidden = !selected;
    body.hidden = !selected;
    card.style.display = selected ? '' : 'none';
    body.style.display = selected ? '' : 'none';
    card.dataset.activated = selected ? 'true' : 'false';
    setExternalEvaluationSurfaceVisibility(selected);
    if (selected) placeEvaluationWorkspaceInsideCard();
  }

  function activateExternalEvaluationEntry() {
    if (externalEntryActivated) return true;
    const select = document.getElementById('admin-api-key-category');
    const option = select?.querySelector(`option[value="${EXTERNAL_CATEGORY}"]`);
    if (!select || !option) {
      externalEntryAttempts += 1;
      if (externalEntryAttempts < EXTERNAL_ENTRY_MAX_ATTEMPTS) {
        window.setTimeout(activateExternalEvaluationEntry, EXTERNAL_ENTRY_RETRY_MS);
      }
      return false;
    }

    externalEntryAttempts = 0;
    externalEntryActivated = true;
    if (select.value !== EXTERNAL_CATEGORY) {
      select.value = EXTERNAL_CATEGORY;
      select.dispatchEvent(new Event('change', { bubbles: true }));
    }
    syncEvaluationSelectionState();
    window.PMK_ADMIN_EXTERNAL_EVALUATION_CATEGORY_FLOW?.apply?.();
    placeEvaluationWorkspaceInsideCard();
    document.body.dataset.adminExternalEvaluationEntry = 'active';
    return true;
  }

  function setEvaluationAccessStatus(message, danger = false, ok = false) {
    const host = ensureEvaluationGrantPlaceholder();
    const target = host?.querySelector('[data-evaluation-access-status]');
    if (!target) return;
    target.className = ok ? 'admin-note ok' : danger ? 'admin-note danger' : 'admin-note';
    target.textContent = message;
  }

  function markSessionExpired(status) {
    document.body.dataset.adminSession = `expired-${status}`;
    document.body.dataset.adminEvaluationGrants = 'auth-expired';
    window.PMK_ADMIN_AUTH?.clearIdentitySession?.();
    setEvaluationAccessStatus('Administrator session expired. Sign in again and complete MFA before using Evaluation authority.', true);
    const bannerId = 'admin-session-expired-banner';
    let banner = document.getElementById(bannerId);
    if (!banner) {
      banner = document.createElement('div');
      banner.id = bannerId;
      banner.className = 'admin-note danger';
      banner.style.margin = '16px';
      banner.innerHTML = '<strong>Administrator session expired.</strong> Protected controls are locked. <a href="/login?mode=admin">Sign in again</a>.';
      document.body.prepend(banner);
    }
  }

  function loadScript(selector, src, datasetKey, onLoad) {
    if (document.querySelector(selector)) {
      onLoad?.();
      return;
    }
    const script = document.createElement('script');
    script.src = src;
    script.dataset[datasetKey] = 'true';
    script.addEventListener('load', () => onLoad?.());
    script.addEventListener('error', () => {
      document.body.dataset.adminEvaluationGrants = 'load-error';
      setEvaluationAccessStatus(`Protected Evaluation asset failed to load: ${src}`, true);
    });
    document.body.appendChild(script);
  }

  function loadProtectedEvaluationControls() {
    loadScript(
      API_KEY_WORKSPACE_SCRIPT_SELECTOR,
      API_KEY_WORKSPACE_SCRIPT_SRC,
      'adminApiKeyProvisioningWorkspace',
      () => window.setTimeout(placeEvaluationWorkspaceInsideCard, 0)
    );
    loadScript(
      EVALUATION_SCRIPT_SELECTOR,
      EVALUATION_SCRIPT_SRC,
      'adminEvaluationGrants',
      () => {
        document.body.dataset.adminEvaluationGrants = 'loaded';
        window.PMK_ADMIN_EXTERNAL_EVALUATION_CATEGORY_FLOW?.renderContract?.();
      }
    );
    loadScript(
      API_KEY_EVALUATION_LIFECYCLE_SCRIPT_SELECTOR,
      API_KEY_EVALUATION_LIFECYCLE_SCRIPT_SRC,
      'adminApiKeyEvaluationLifecycle',
      () => window.setTimeout(placeEvaluationWorkspaceInsideCard, 0)
    );
    window.setTimeout(activateExternalEvaluationEntry, 0);
  }

  async function verifyAuthorityOnce() {
    return fetch(AUTHORITY_ENDPOINT, {
      method: 'GET',
      credentials: 'include',
      cache: 'no-store',
      headers: authorityHeaders(),
    });
  }

  async function verifyPlatformAdminAuthority() {
    let response = await verifyAuthorityOnce();
    if (response.status !== 503) return response;
    for (const delayMs of SESSION_RETRY_DELAYS_MS) {
      document.body.dataset.adminSession = 'retrying-503';
      await new Promise((resolve) => window.setTimeout(resolve, delayMs));
      response = await verifyAuthorityOnce();
      if (response.status !== 503) return response;
    }
    return response;
  }

  async function refreshIdentitySession() {
    if (refreshInFlight) return refreshInFlight;
    refreshInFlight = (async () => {
      const csrf = cookieValue(CSRF_COOKIE);
      if (!csrf) return false;
      const response = await fetch(SESSION_REFRESH_ENDPOINT, {
        method: 'POST',
        credentials: 'include',
        cache: 'no-store',
        headers: {
          Accept: 'application/json',
          'X-CSRF-Token': csrf,
        },
      });
      if (!response.ok) return false;
      const payload = await response.json().catch(() => ({}));
      if (payload?.mfa_required === true) return false;
      const token = String(payload?.access_token || '').trim();
      if (!token) return false;
      sessionStorage.setItem('maestro_token', token);
      sessionStorage.setItem('maestro_ui_session_refreshed_at', new Date().toISOString());
      return true;
    })();
    try {
      return await refreshInFlight;
    } finally {
      refreshInFlight = null;
    }
  }

  function dispatchAdminSessionVerified(authority) {
    window.dispatchEvent(new CustomEvent('pmk-admin-session-verified', {
      detail: {
        authority: authority.authority || 'platform_admin',
        authorityStore: authority.authority_store || 'postgresql_shared',
      },
    }));
  }

  async function checkAdminSession() {
    ensureEvaluationGrantPlaceholder();
    syncEvaluationSelectionState();
    const token = window.PMK_ADMIN_AUTH?.bearer?.() || '';
    if (!token) {
      document.body.dataset.adminSession = 'auth-missing';
      document.body.dataset.adminEvaluationGrants = 'auth-missing';
      setEvaluationAccessStatus('Active administrator Identity session required. Sign in and complete MFA.', true);
      return false;
    }

    try {
      let response = await verifyPlatformAdminAuthority();
      if (response.status === 401) {
        document.body.dataset.adminSession = 'refreshing';
        setEvaluationAccessStatus('Administrator access token expired. Refreshing the same MFA-backed Identity session…');
        const refreshed = await refreshIdentitySession();
        if (refreshed) response = await verifyPlatformAdminAuthority();
      }
      if (response.status === 401 || response.status === 403) {
        markSessionExpired(response.status);
        return false;
      }
      if (!response.ok) {
        document.body.dataset.adminSession = `error-${response.status}`;
        document.body.dataset.adminEvaluationGrants = 'authority-unavailable';
        setEvaluationAccessStatus(`Platform Administrator authority unavailable: HTTP ${response.status}. Protected controls remain locked.`, true);
        return false;
      }

      const authority = await response.json();
      if (authority?.authorized !== true || authority?.authority !== 'platform_admin') {
        document.body.dataset.adminSession = 'authority-denied';
        document.body.dataset.adminEvaluationGrants = 'not-authorized';
        setEvaluationAccessStatus('Authenticated identity does not hold active Platform Administrator authority.', true);
        return false;
      }

      document.getElementById('admin-session-expired-banner')?.remove();
      document.body.dataset.adminSession = 'ok';
      document.body.dataset.adminEvaluationGrants = 'authorized';
      setEvaluationAccessStatus('Platform Administrator verified from PostgreSQL-backed authority. Loading governed Evaluation controls…', false, true);
      loadProtectedEvaluationControls();
      dispatchAdminSessionVerified(authority);
      window.setTimeout(activateExternalEvaluationEntry, 0);
      return true;
    } catch (error) {
      document.body.dataset.adminSession = 'error';
      document.body.dataset.adminEvaluationGrants = 'authority-unavailable';
      setEvaluationAccessStatus(`Administrator authority check failed safely: ${error.message || error}`, true);
      return false;
    }
  }

  window.PMK_ADMIN_SESSION = {
    check: checkAdminSession,
    syncEvaluationSelectionState,
    activateExternalEvaluationEntry,
    authorityEndpoint: AUTHORITY_ENDPOINT,
    refreshEndpoint: SESSION_REFRESH_ENDPOINT,
  };

  window.addEventListener('pmk-api-key-category-changed', async () => {
    syncEvaluationSelectionState();
    if (externalEvaluationSelected()) await checkAdminSession();
  });

  ensureEvaluationGrantPlaceholder();
  syncEvaluationSelectionState();
  checkAdminSession();
});