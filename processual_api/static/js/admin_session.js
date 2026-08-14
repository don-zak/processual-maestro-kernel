document.addEventListener('DOMContentLoaded', () => {
  const EVALUATION_SCRIPT_SELECTOR = 'script[data-admin-evaluation-grants]';
  const EVALUATION_SCRIPT_SRC =
    '/console/js/admin_evaluation_grants.js?v=adminevaltasks02';
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

  function evaluationLoadFailure(message) {
    document.body.dataset.adminEvaluationGrants = 'load-error';
    const page = document.getElementById('page-admin-api-keys');
    if (!page || document.getElementById('admin-evaluation-grants-load-error')) {
      return;
    }
    const note = document.createElement('div');
    note.id = 'admin-evaluation-grants-load-error';
    note.className = 'card admin-note danger';
    note.style.marginTop = 'var(--s-5)';
    note.textContent = message;
    page.appendChild(note);
  }

  function loadEvaluationGrantControls() {
    if (document.querySelector(EVALUATION_SCRIPT_SELECTOR)) return;

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

  async function checkAdminSession() {
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
        writeProtected(
          'Admin auth token missing. Login did not persist a Bearer token for admin API calls.'
        );
        return;
      }

      const response = await fetch('/auth/me', {
        method: 'GET',
        credentials: 'include',
        headers,
      });

      if (!response.ok) {
        document.body.dataset.adminSession = 'error-' + response.status;
        writeProtected('Admin session check failed: HTTP ' + response.status);
        return;
      }

      const me = await response.json();
      if (!isAdminSession(me)) {
        document.body.dataset.adminSession = 'not-admin';
        writeProtected('Session exists, but admin scope was not found.');
        return;
      }

      document.body.dataset.adminSession = 'ok';
      writeProtected(
        'Admin session verified. Backend scopes remain the authority.'
      );

      if (canManageEvaluationGrants(me)) {
        document.body.dataset.adminEvaluationGrants = 'authorized';
        loadEvaluationGrantControls();
      } else {
        document.body.dataset.adminEvaluationGrants = 'not-authorized';
      }
    } catch (error) {
      document.body.dataset.adminSession = 'error';
      writeProtected(
        'Admin session check failed: ' + (error.message || String(error))
      );
    }
  }

  checkAdminSession();
});
