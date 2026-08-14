document.addEventListener('DOMContentLoaded', () => {
  const EVALUATION_SCRIPT_SELECTOR = 'script[data-admin-evaluation-grants]';
  const EVALUATION_SCRIPT_SRC =
    '/console/js/admin_evaluation_grants.js?v=adminevaltasks03-visible';
  const EVALUATION_HOST_ID = 'admin-evaluation-grants';
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

  function ensureEvaluationGrantPlaceholder() {
    let host = document.getElementById(EVALUATION_HOST_ID);
    if (host) return host;

    const page = document.getElementById('page-admin-api-keys');
    if (!page) return null;

    host = document.createElement('div');
    host.id = EVALUATION_HOST_ID;
    host.className = 'card';
    host.style.marginTop = 'var(--s-5)';
    host.dataset.evaluationGrantPlaceholder = 'true';
    host.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">External Evaluation Access</div>
        <div class="sh-sub">supervisor-governed API access outside paid subscription onboarding</div>
      </div>
      <div class="admin-note" data-evaluation-access-status>
        Checking administrator authority for evaluation grant management...
      </div>
      <div class="muted" style="margin-top:var(--s-2)">
        Backend scopes remain authoritative. Management controls appear only after verified authorization.
      </div>
    `;
    page.appendChild(host);
    return host;
  }

  function setEvaluationAccessStatus(message, danger = false) {
    const host = ensureEvaluationGrantPlaceholder();
    if (!host) return;
    const target = host.querySelector('[data-evaluation-access-status]');
    if (!target) return;
    target.className = danger ? 'admin-note danger' : 'admin-note';
    target.textContent = message;
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

      document.body.dataset.adminSession = 'ok';
      writeProtected(
        'Admin session verified. Backend scopes remain the authority.'
      );
      dispatchAdminSessionVerified(me);

      if (canManageEvaluationGrants(me)) {
        document.body.dataset.adminEvaluationGrants = 'authorized';
        loadEvaluationGrantControls();
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