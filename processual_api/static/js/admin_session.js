document.addEventListener('DOMContentLoaded', () => {
  const EVALUATION_SCRIPT_SELECTOR = 'script[data-admin-evaluation-grants]';
  const EVALUATION_SCRIPT_SRC =
    '/console/js/admin_evaluation_grants.js?v=adminevaltasks08-super-admin';
  const API_KEY_WORKSPACE_SCRIPT_SELECTOR =
    'script[data-admin-api-key-provisioning-workspace]';
  const API_KEY_WORKSPACE_SCRIPT_SRC =
    '/console/js/admin_api_key_provisioning_workspace.js?v=adminapikeyworkspace05-super-admin';
  const VERIFICATION_HOST_ID = 'admin-evaluation-verification-controls';
  const EXTERNAL_CATEGORY = 'external_evaluation';
  const AUTHORITY_ENDPOINT = '/settings/admin/evaluation-grants/authority';
  const SESSION_RETRY_DELAYS_MS = [400, 1200, 2500];

  function externalEvaluationSelected() {
    return document.getElementById('admin-api-key-category')?.value === EXTERNAL_CATEGORY;
  }

  function evaluationHost() {
    return document.getElementById(VERIFICATION_HOST_ID);
  }

  function setEvaluationAccessStatus(message, danger = false) {
    const host = evaluationHost();
    if (!host) return;
    const target = host.querySelector('[data-evaluation-access-status]');
    if (!target) return;
    target.className = danger ? 'admin-note danger' : 'admin-note';
    target.textContent = message;
  }

  function loadEvaluationGrantControls() {
    if (document.querySelector(EVALUATION_SCRIPT_SELECTOR)) return;
    const script = document.createElement('script');
    script.src = EVALUATION_SCRIPT_SRC;
    script.dataset.adminEvaluationGrants = 'true';
    script.addEventListener('load', () => {
      document.body.dataset.adminEvaluationUi = 'loaded';
    });
    script.addEventListener('error', () => {
      document.body.dataset.adminEvaluationUi = 'load-error';
      setEvaluationAccessStatus('Evaluation UI assets could not be loaded.', true);
    });
    document.body.appendChild(script);
  }

  function loadApiKeyProvisioningWorkspace() {
    if (document.querySelector(API_KEY_WORKSPACE_SCRIPT_SELECTOR)) return;
    const script = document.createElement('script');
    script.src = API_KEY_WORKSPACE_SCRIPT_SRC;
    script.dataset.adminApiKeyProvisioningWorkspace = 'true';
    script.addEventListener('error', () => {
      document.body.dataset.adminApiKeyProvisioningWorkspace = 'load-error';
    });
    document.body.appendChild(script);
  }

  function authHeaders() {
    if (window.PMK_ADMIN_AUTH && typeof PMK_ADMIN_AUTH.headers === 'function') {
      return PMK_ADMIN_AUTH.headers();
    }
    return new Headers({ 'Content-Type': 'application/json' });
  }

  function wait(delayMs) {
    return new Promise((resolve) => window.setTimeout(resolve, delayMs));
  }

  async function fetchSuperAdminAuthority(headers) {
    const request = () => fetch(AUTHORITY_ENDPOINT, {
      method: 'GET',
      credentials: 'include',
      headers,
    });

    let response = await request();
    if (response.ok || response.status !== 503) return response;

    for (const delayMs of SESSION_RETRY_DELAYS_MS) {
      document.body.dataset.adminSession = 'retrying-503';
      document.body.dataset.adminEvaluationGrants = 'authority-retrying';
      setEvaluationAccessStatus(
        'Super Administrator authority verification is temporarily unavailable. Retrying safely...'
      );
      await wait(delayMs);
      response = await request();
      if (response.ok || response.status !== 503) return response;
    }
    return response;
  }

  function dispatchSuperAdminVerified(authority) {
    try {
      window.dispatchEvent(new CustomEvent('pmk-admin-session-verified', {
        detail: {
          authority: authority.authority || 'platform_admin',
          exclusiveSuperAdministrator: true,
        },
      }));
    } catch {
      window.dispatchEvent(new Event('pmk-admin-session-verified'));
    }
  }

  async function checkAdminSession() {
    if (!externalEvaluationSelected()) return;

    try {
      document.body.dataset.adminEvaluationGrants = 'verifying-authority';
      setEvaluationAccessStatus(
        'Verifying exclusive Super Administrator authority (platform_admin)...'
      );

      const response = await fetchSuperAdminAuthority(authHeaders());
      if (!response.ok) {
        document.body.dataset.adminSession = response.status === 401 ? 'auth-missing' : 'not-super-admin';
        document.body.dataset.adminEvaluationGrants = 'not-authorized';
        if (response.status === 401) {
          setEvaluationAccessStatus(
            'Super Administrator identity session is required. API keys and legacy admin sessions cannot unlock External Evaluation.',
            true
          );
        } else if (response.status === 403) {
          setEvaluationAccessStatus(
            'Access denied. External Evaluation is exclusive to an active Super Administrator (platform_admin). owner_admin, security_admin, billing_admin, wildcard scopes, and API keys are not sufficient.',
            true
          );
        } else {
          setEvaluationAccessStatus(
            `Super Administrator authority verification failed: HTTP ${response.status}`,
            true
          );
        }
        return;
      }

      const authority = await response.json();
      if (
        authority.authorized !== true ||
        authority.authority !== 'platform_admin' ||
        authority.exclusive_super_administrator !== true
      ) {
        document.body.dataset.adminSession = 'not-super-admin';
        document.body.dataset.adminEvaluationGrants = 'not-authorized';
        setEvaluationAccessStatus(
          'Access denied. Backend did not confirm exclusive Super Administrator authority.',
          true
        );
        return;
      }

      document.body.dataset.adminSession = 'ok';
      document.body.dataset.adminEvaluationGrants = 'authorized';
      document.body.dataset.adminEvaluationAuthority = 'platform_admin';
      setEvaluationAccessStatus(
        'Super Administrator verified. External Evaluation lifecycle controls are unlocked.'
      );
      dispatchSuperAdminVerified(authority);
    } catch (error) {
      document.body.dataset.adminSession = 'error';
      document.body.dataset.adminEvaluationGrants = 'auth-error';
      setEvaluationAccessStatus(
        'Super Administrator authority verification failed: ' + (error.message || String(error)),
        true
      );
    }
  }

  window.PMK_ADMIN_SESSION = { check: checkAdminSession };

  window.addEventListener('pmk-api-key-category-changed', () => {
    if (!externalEvaluationSelected()) {
      document.body.dataset.adminEvaluationGrants = 'inactive';
    }
  });

  // Render the complete lifecycle immediately. Privileged catalogs and actions
  // hydrate only after the backend confirms exclusive platform_admin authority.
  loadApiKeyProvisioningWorkspace();
  loadEvaluationGrantControls();

  if (externalEvaluationSelected()) checkAdminSession();
});
