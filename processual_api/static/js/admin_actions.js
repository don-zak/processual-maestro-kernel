(function () {
  function clearAuthState() {
    const keys = [
      'token',
      'access_token',
      'auth_token',
      'maestro_token',
      'maestro_auth_token',
      'pmk_token',
      'pmk_auth_token',
      'user',
      'role',
    ];

    keys.forEach((key) => {
      try { localStorage.removeItem(key); } catch (error) {}
      try { sessionStorage.removeItem(key); } catch (error) {}
    });

    try {
      document.cookie.split(';').forEach((cookie) => {
        const name = cookie.split('=')[0].trim();
        if (!name) return;
        document.cookie = name + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/';
      });
    } catch (error) {}
  }

  function openClientConsole() {
    window.location.assign('/console');
  }

  async function logout() {
    try {
      if (window.CLIENT && typeof CLIENT.post === 'function') {
        await CLIENT.post('/auth/logout', {});
      }
    } catch (error) {
      // Backend logout route is optional; client-side cleanup still runs.
    }

    clearAuthState();
    window.location.replace('/login?mode=admin');
  }

  function loadAdminMarketplaceCatalog() {
    if (document.querySelector('script[data-admin-marketplace-catalog]')) return;
    const script = document.createElement('script');
    script.src = '/console/js/admin_marketplace_catalog.js?v=a3-original-offers-1';
    script.defer = true;
    script.dataset.adminMarketplaceCatalog = 'true';
    document.head.appendChild(script);
  }

  function loadEnterpriseFailureReview() {
    if (!document.querySelector('link[data-admin-enterprise-failure-review-style]')) {
      const style = document.createElement('link');
      style.rel = 'stylesheet';
      style.href = '/console/css/admin_enterprise_failure_review.css?v=enterprise-failure-review1';
      style.dataset.adminEnterpriseFailureReviewStyle = 'true';
      document.head.appendChild(style);
    }

    if (!document.querySelector('script[data-admin-enterprise-failure-review-script]')) {
      const script = document.createElement('script');
      script.src = '/console/js/admin_enterprise_failure_review.js?v=enterprise-failure-review1';
      script.defer = true;
      script.dataset.adminEnterpriseFailureReviewScript = 'true';
      document.body.appendChild(script);
    }
  }

  function loadScriptOnce(src, datasetKey) {
    return new Promise((resolve, reject) => {
      const selector = `script[data-${datasetKey.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}]`;
      const existing = document.querySelector(selector);
      if (existing) {
        if (existing.dataset.loaded === 'true') resolve(existing);
        else {
          existing.addEventListener('load', () => resolve(existing), { once: true });
          existing.addEventListener('error', () => reject(new Error(`Failed to load ${src}`)), { once: true });
        }
        return;
      }

      const script = document.createElement('script');
      script.src = src;
      script.defer = true;
      script.dataset[datasetKey] = 'true';
      script.addEventListener('load', () => {
        script.dataset.loaded = 'true';
        resolve(script);
      }, { once: true });
      script.addEventListener('error', () => reject(new Error(`Failed to load ${src}`)), { once: true });
      document.body.appendChild(script);
    });
  }

  async function loadExternalEvaluationAccess() {
    if (document.body.dataset.adminExternalEvaluationAssets === 'loaded') return;
    if (document.body.dataset.adminExternalEvaluationAssets === 'loading') return;
    document.body.dataset.adminExternalEvaluationAssets = 'loading';

    try {
      await loadScriptOnce(
        '/console/js/admin_api_key_provisioning_workspace.js?v=admin-eval-wire-r1',
        'adminApiKeyProvisioningWorkspace',
      );
      await loadScriptOnce(
        '/console/js/admin_external_evaluation_dom_contract.js?v=admin-eval-wire-r1',
        'adminExternalEvaluationDomContract',
      );
      await loadScriptOnce(
        '/console/js/admin_evaluation_grants.js?v=admin-eval-wire-r1',
        'adminEvaluationGrants',
      );
      await loadScriptOnce(
        '/console/js/admin_api_key_evaluation_lifecycle.js?v=admin-eval-wire-r1',
        'adminApiKeyEvaluationLifecycle',
      );
      document.body.dataset.adminExternalEvaluationAssets = 'loaded';
      window.PMK_ADMIN_EXTERNAL_EVALUATION_DOM_CONTRACT?.reconcile?.();
      window.PMK_ADMIN_API_KEY_EVALUATION_LIFECYCLE?.initialize?.();
    } catch (error) {
      document.body.dataset.adminExternalEvaluationAssets = 'load-failed';
      console.error('Unable to load External Evaluation Access assets.', error);
    }
  }

  async function loadAccountRecoveryEscalations() {
    try {
      await loadScriptOnce(
        '/console/js/admin_account_recovery_escalations.js?v=account-recovery-escalation-r1',
        'adminAccountRecoveryEscalations',
      );
      window.PMK_ADMIN_ACCOUNT_RECOVERY_ESCALATIONS?.initialize?.();
    } catch (error) {
      console.error('Unable to load account recovery escalation queue.', error);
    }
  }

  function bindAdminActions() {
    const clientButton = document.getElementById('admin-client-console-btn');
    const logoutButton = document.getElementById('admin-logout-btn');

    if (clientButton) {
      clientButton.addEventListener('click', (event) => {
        event.preventDefault();
        openClientConsole();
      });
    }

    if (logoutButton) {
      logoutButton.addEventListener('click', (event) => {
        event.preventDefault();
        logout();
      });
    }

    loadAdminMarketplaceCatalog();
    loadEnterpriseFailureReview();
    loadExternalEvaluationAccess();
    loadAccountRecoveryEscalations();
  }

  window.PMK_ADMIN_ACTIONS = {
    bindAdminActions,
    clearAuthState,
    loadAdminMarketplaceCatalog,
    loadEnterpriseFailureReview,
    loadExternalEvaluationAccess,
    loadAccountRecoveryEscalations,
    logout,
    openClientConsole,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindAdminActions);
  } else {
    bindAdminActions();
  }
})();