document.addEventListener('DOMContentLoaded', () => {
  const EVALUATION_SCRIPT_SELECTOR = 'script[data-admin-evaluation-grants]';
  const EVALUATION_SCRIPT_SRC =
    '/console/js/admin_evaluation_grants.js?v=adminevaltasks05-accesscatalog';
  const API_KEY_WORKSPACE_SCRIPT_SELECTOR =
    'script[data-admin-api-key-provisioning-workspace]';
  const API_KEY_WORKSPACE_SCRIPT_SRC =
    '/console/js/admin_api_key_provisioning_workspace.js?v=adminapikeyworkspace02';
  const API_KEY_EVALUATION_LIFECYCLE_SCRIPT_SELECTOR =
    'script[data-admin-api-key-evaluation-lifecycle]';
  const API_KEY_EVALUATION_LIFECYCLE_SCRIPT_SRC =
    '/console/js/admin_api_key_evaluation_lifecycle.js?v=adminapikevaluation01';
  const API_KEY_LIFECYCLE_CARD_ID = 'admin-api-key-lifecycle-card';
  const EVALUATION_CARD_ID = 'admin-api-key-external-evaluation-card';
  const EVALUATION_BODY_ID = 'admin-api-key-external-evaluation-body';
  const EVALUATION_ACTIVATE_ID = 'admin-api-key-external-evaluation-activate';
  const EVALUATION_HOST_ID = 'admin-evaluation-grants';
  const EVALUATION_DEV_AUTH_ID = 'admin-evaluation-dev-auth';
  const PROVISIONING_MODE_ID = 'admin-api-key-provisioning-mode';
  const LOCAL_DEVELOPMENT_HOSTS = new Set(['127.0.0.1', 'localhost', '::1']);
  const ADMIN_ROLES = new Set([
    'admin',
    'administrator',
    'owner_admin',
    'security_admin',
    'billing_admin',
    'ops_admin',
    'support_admin',
  ]);
  const EVALUATION_ADMIN_ROLES = new Set([
    'admin',
    'owner_admin',
    'security_admin',
    'billing_admin',
  ]);
  const SESSION_RETRY_DELAYS_MS = [400, 1200, 2500];

  function normalizedRole(me) {
    return String(
      me.role ||
        me.user_role ||
        me.account_role ||
        (me.user && me.user.role) ||
        ''
    )
      .trim()
      .toLowerCase();
  }

  function normalizedScopes(me) {
    const raw = me.scopes || me.permissions || [];
    return Array.isArray(raw)
      ? raw.map((scope) => String(scope || '').trim().toLowerCase()).filter(Boolean)
      : [];
  }

  function isAdminSession(me) {
    const role = normalizedRole(me);
    const scopes = normalizedScopes(me);
    return (
      role === 'admin' ||
      role === 'administrator' ||
      ADMIN_ROLES.has(role) ||
      scopes.includes('admin') ||
      scopes.includes('admin:settings') ||
      scopes.some(
        (scope) =>
          scope === '*' ||
          scope.startsWith('admin:')
      )
    );
  }

  function canManageEvaluationGrants(me) {
    const role = normalizedRole(me);
    const scopes = new Set(normalizedScopes(me));
    return (
      EVALUATION_ADMIN_ROLES.has(role) ||
      scopes.has('*') ||
      scopes.has('admin:*') ||
      scopes.has('admin:api_keys:write')
    );
  }

  function isLocalDevelopmentOrigin() {
    return LOCAL_DEVELOPMENT_HOSTS.has(window.location.hostname);
  }

  function applyExternalEvaluationActivation() {
    const card = document.getElementById(EVALUATION_CARD_ID);
    const body = document.getElementById(EVALUATION_BODY_ID);
    const button = document.getElementById(EVALUATION_ACTIVATE_ID);
    if (!card || !body || !button) return;

    card.dataset.activated = 'true';
    body.hidden = false;
    button.disabled = true;
    button.textContent = 'External Evaluation Active';

    const mode = document.getElementById(PROVISIONING_MODE_ID);
    if (mode && mode.value !== 'external_evaluation') {
      mode.value = 'external_evaluation';
      mode.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  function ensureEvaluationGrantPlaceholder() {
    let host = document.getElementById(EVALUATION_HOST_ID);
    if (host) return host;

    const lifecycleCard = document.getElementById(API_KEY_LIFECYCLE_CARD_ID);
    const page = document.getElementById('page-admin-api-keys');
    const parent = lifecycleCard || page;
    if (!parent) return null;

    let card = document.getElementById(EVALUATION_CARD_ID);
    if (!card) {
      card = document.createElement('section');
      card.id = EVALUATION_CARD_ID;
      card.className = 'card flat';
      card.style.marginTop = 'var(--s-4)';
      card.dataset.lifecycleEmbedded = lifecycleCard ? 'true' : 'fallback-page';
      card.innerHTML = `
        <div class="sec-hdr">
          <div class="sh-title">External Evaluation Access</div>
          <div class="sh-sub">supervisor-governed sandbox API key preparation, issue, test, and revoke</div>
        </div>
        <div class="admin-note">
          This is part of Admin API Key Lifecycle. Activate it to reveal the governed provisioning and evaluation controls. Production access remains disabled.
        </div>
        <div class="admin-actions">
          <button id="${EVALUATION_ACTIVATE_ID}" class="btn primary" type="button">
            Activate External Evaluation
          </button>
        </div>
        <div id="${EVALUATION_BODY_ID}" hidden style="margin-top:var(--s-3)">
          <div id="${EVALUATION_HOST_ID}" class="card flat" data-evaluation-grant-placeholder="true">
            <div class="admin-note" data-evaluation-access-status>
              Activate External Evaluation to verify administrator authority and load controls.
            </div>
            <div class="muted" style="margin-top:var(--s-2)">
              Backend scopes remain authoritative. Raw API keys are shown only at issue time.
            </div>
          </div>
        </div>
      `;
      parent.appendChild(card);

      document.getElementById(EVALUATION_ACTIVATE_ID)?.addEventListener('click', async () => {
        applyExternalEvaluationActivation();
        await checkAdminSession();
      });
    }

    return document.getElementById(EVALUATION_HOST_ID);
  }

  function setEvaluationAccessStatus(message, danger = false) {
    const host = ensureEvaluationGrantPlaceholder();
    if (!host) return;
    const target = host.querySelector('[data-evaluation-access-status]');
    if (!target) return;
    target.className = danger ? 'admin-note danger' : 'admin-note';
    target.textContent = message;
  }

  function clearDevelopmentAuthBootstrap() {
    document.getElementById(EVALUATION_DEV_AUTH_ID)?.remove();
  }

  function renderDevelopmentAuthBootstrap() {
    if (!isLocalDevelopmentOrigin()) return;
    const host = ensureEvaluationGrantPlaceholder();
    if (!host) return;

    const existing = document.getElementById(EVALUATION_DEV_AUTH_ID);
    if (existing) {
      const existingInput = existing.querySelector('#admin-evaluation-dev-api-key');
      const existingButton = existing.querySelector('#admin-evaluation-dev-api-key-save');
      const existingMessage = existing.querySelector('[data-evaluation-dev-auth-message]');
      if (existingButton) existingButton.disabled = false;
      if (existingMessage) {
        existingMessage.textContent =
          'Credential was not accepted. Enter another development API key.';
      }
      existingInput?.focus();
      return;
    }

    const bootstrap = document.createElement('div');
    bootstrap.id = EVALUATION_DEV_AUTH_ID;
    bootstrap.className = 'admin-note';
    bootstrap.style.marginTop = 'var(--s-3)';
    bootstrap.innerHTML = `
      <div style="font-weight:700">Local development credential</div>
      <div class="muted" style="margin-top:var(--s-1)">
        Enter the development API key for this browser session. It is stored in sessionStorage only.
      </div>
      <div style="display:flex;gap:var(--s-2);margin-top:var(--s-2);align-items:center">
        <input
          id="admin-evaluation-dev-api-key"
          type="password"
          autocomplete="off"
          placeholder="Development API key"
          style="flex:1"
        >
        <button id="admin-evaluation-dev-api-key-save" class="btn primary" type="button">
          Verify & Load Controls
        </button>
      </div>
      <div class="muted" data-evaluation-dev-auth-message style="margin-top:var(--s-1)"></div>
    `;
    host.appendChild(bootstrap);

    const input = bootstrap.querySelector('#admin-evaluation-dev-api-key');
    const button = bootstrap.querySelector('#admin-evaluation-dev-api-key-save');
    const message = bootstrap.querySelector('[data-evaluation-dev-auth-message]');

    async function saveCredential() {
      const value = String(input?.value || '').trim();
      if (!value) {
        if (message) message.textContent = 'Enter a development API key.';
        return;
      }

      try {
        sessionStorage.setItem('api_key', value);
        if (input) input.value = '';
        if (button) button.disabled = true;
        if (message) message.textContent = 'Credential saved for this tab. Verifying administrator authority...';
        setEvaluationAccessStatus('Verifying local development administrator credential...');
        await checkAdminSession();
      } catch (error) {
        if (button) button.disabled = false;
        if (message) {
          message.textContent =
            'Unable to store the development credential for this browser session.';
        }
      }
    }

    button?.addEventListener('click', saveCredential);
    input?.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      saveCredential();
    });
  }

  function evaluationLoadFailure(message) {
    document.body.dataset.adminEvaluationGrants = 'load-error';
    setEvaluationAccessStatus(message, true);
  }

  function loadEvaluationGrantControls() {
    if (document.querySelector(EVALUATION_SCRIPT_SELECTOR)) return;

    setEvaluationAccessStatus('Authorized. Loading evaluation grant controls...');
    const script = document.createElement('script');
    script.src = EVALUATION_SCRIPT_SRC;
    script.dataset.adminEvaluationGrants = 'true';
    script.addEventListener('load', () => {
      document.body.dataset.adminEvaluationGrants = 'loaded';
    });
    script.addEventListener('error', () => {
      evaluationLoadFailure(
        'Evaluation grant controls could not be loaded. Reload the admin page after verifying the local static assets.'
      );
    });
    document.body.appendChild(script);
  }

  function loadApiKeyProvisioningWorkspace() {
    if (document.querySelector(API_KEY_WORKSPACE_SCRIPT_SELECTOR)) {
      if (document.getElementById(EVALUATION_CARD_ID)?.dataset.activated === 'true') {
        applyExternalEvaluationActivation();
      }
      return;
    }

    const script = document.createElement('script');
    script.src = API_KEY_WORKSPACE_SCRIPT_SRC;
    script.dataset.adminApiKeyProvisioningWorkspace = 'true';
    script.addEventListener('load', () => {
      if (!document.body.dataset.adminApiKeyProvisioningWorkspace) {
        document.body.dataset.adminApiKeyProvisioningWorkspace = 'loading';
      }
      if (document.getElementById(EVALUATION_CARD_ID)?.dataset.activated === 'true') {
        window.setTimeout(applyExternalEvaluationActivation, 0);
      }
    });
    script.addEventListener('error', () => {
      document.body.dataset.adminApiKeyProvisioningWorkspace = 'load-error';
    });
    document.body.appendChild(script);
  }

  function loadApiKeyEvaluationLifecycle() {
    if (document.querySelector(API_KEY_EVALUATION_LIFECYCLE_SCRIPT_SELECTOR)) return;

    const script = document.createElement('script');
    script.src = API_KEY_EVALUATION_LIFECYCLE_SCRIPT_SRC;
    script.dataset.adminApiKeyEvaluationLifecycle = 'true';
    script.addEventListener('load', () => {
      if (!document.body.dataset.adminApiKeyEvaluationLifecycle) {
        document.body.dataset.adminApiKeyEvaluationLifecycle = 'loading';
      }
      if (document.getElementById(EVALUATION_CARD_ID)?.dataset.activated === 'true') {
        window.setTimeout(applyExternalEvaluationActivation, 0);
      }
    });
    script.addEventListener('error', () => {
      document.body.dataset.adminApiKeyEvaluationLifecycle = 'load-error';
    });
    document.body.appendChild(script);
  }

  function wait(delayMs) {
    return new Promise((resolve) => window.setTimeout(resolve, delayMs));
  }

  async function fetchAdminIdentity(headers) {
    const response = await fetch('/auth/me', {
      method: 'GET',
      credentials: 'include',
      headers,
    });

    if (response.ok || response.status !== 503) {
      return response;
    }

    for (const delayMs of SESSION_RETRY_DELAYS_MS) {
      document.body.dataset.adminSession = 'retrying-503';
      document.body.dataset.adminEvaluationGrants = 'auth-retrying';
      setEvaluationAccessStatus(
        'Administrator verification is temporarily unavailable. Retrying safely...'
      );
      await wait(delayMs);
      const retry = await fetch('/auth/me', {
        method: 'GET',
        credentials: 'include',
        headers,
      });
      if (retry.ok || retry.status !== 503) {
        return retry;
      }
    }

    return response;
  }

  function dispatchAdminSessionVerified(me) {
    try {
      window.dispatchEvent(
        new CustomEvent('pmk-admin-session-verified', {
          detail: {
            role: normalizedRole(me),
            scopes: normalizedScopes(me),
          },
        })
      );
    } catch {
      window.dispatchEvent(new Event('pmk-admin-session-verified'));
    }
  }

  async function checkAdminSession() {
    ensureEvaluationGrantPlaceholder();

    const protectedBlocks = Array.from(
      document.querySelectorAll('.mono-block')
    ).filter((el) =>
      (el.textContent || '').includes('Checking admin session')
    );

    function writeProtected(message) {
      protectedBlocks.forEach((el) => {
        el.textContent = message;
      });
    }

    try {
      const headers =
        window.PMK_ADMIN_AUTH &&
        typeof PMK_ADMIN_AUTH.headers === 'function'
          ? PMK_ADMIN_AUTH.headers()
          : new Headers({ 'Content-Type': 'application/json' });

      if (!headers.has('Authorization') && !headers.has('X-API-Key')) {
        document.body.dataset.adminSession = 'auth-missing';
        document.body.dataset.adminEvaluationGrants = 'auth-missing';
        const message =
          'Administrator credential is required before evaluation grant controls can be shown.';
        setEvaluationAccessStatus(message, true);
        if (document.getElementById(EVALUATION_CARD_ID)?.dataset.activated === 'true') {
          renderDevelopmentAuthBootstrap();
        }
        writeProtected(
          'Admin auth token missing. Login did not persist a Bearer token for admin API calls.'
        );
        return;
      }

      const response = await fetchAdminIdentity(headers);

      if (!response.ok) {
        document.body.dataset.adminSession = 'error-' + response.status;
        document.body.dataset.adminEvaluationGrants = 'auth-error';
        setEvaluationAccessStatus(
          'Administrator verification failed: HTTP ' + response.status,
          true
        );
        if (
          (response.status === 401 || response.status === 403) &&
          document.getElementById(EVALUATION_CARD_ID)?.dataset.activated === 'true'
        ) {
          renderDevelopmentAuthBootstrap();
        }
        writeProtected('Admin session check failed: HTTP ' + response.status);
        return;
      }

      const me = await response.json();
      if (!isAdminSession(me)) {
        document.body.dataset.adminSession = 'not-admin';
        document.body.dataset.adminEvaluationGrants = 'not-authorized';
        setEvaluationAccessStatus(
          'The current session is authenticated but does not have administrator authority for this area.',
          true
        );
        writeProtected('Session exists, but admin scope was not found.');
        return;
      }

      clearDevelopmentAuthBootstrap();
      document.body.dataset.adminSession = 'ok';
      writeProtected(
        'Admin session verified. Backend scopes remain the authority.'
      );
      loadApiKeyProvisioningWorkspace();
      dispatchAdminSessionVerified(me);

      if (canManageEvaluationGrants(me)) {
        document.body.dataset.adminEvaluationGrants = 'authorized';
        loadEvaluationGrantControls();
        loadApiKeyEvaluationLifecycle();
      } else {
        document.body.dataset.adminEvaluationGrants = 'not-authorized';
        setEvaluationAccessStatus(
          'Administrator session verified, but evaluation grant management requires owner, security, billing, wildcard, or admin:api_keys:write authority.',
          true
        );
      }
    } catch (error) {
      document.body.dataset.adminSession = 'error';
      document.body.dataset.adminEvaluationGrants = 'auth-error';
      setEvaluationAccessStatus(
        'Administrator verification failed: ' + (error.message || String(error)),
        true
      );
      writeProtected(
        'Admin session check failed: ' + (error.message || String(error))
      );
    }
  }

  ensureEvaluationGrantPlaceholder();
  checkAdminSession();
});