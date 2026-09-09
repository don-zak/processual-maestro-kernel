(function () {
  const IDENTITY_TOKEN_KEY = 'maestro_token';
  const SUPERVISOR_SESSION_KEY = 'pmk_supervisor_session_key';
  const LOCAL_DEV_API_KEY = 'api_key';
  const LOCAL_DEVELOPMENT_HOSTS = new Set(['127.0.0.1', 'localhost', '::1']);
  const LEGACY_AUTH_KEYS = [
    'access_token',
    'auth_token',
    'admin_token',
    'admin_access_token',
    'maestro_auth_token',
    'processual_auth_token',
    'processual_session',
    'admin_session',
    'pmk_token',
    'pmkToken',
    'pmk_auth_token',
    'pmkAuthToken',
    'maestroToken',
    'processualToken',
  ];
  const LEGACY_SUPERVISOR_KEYS = [
    'admin_supervisor_session_key',
    'supervisor_session_key',
    'pmk_sup_session_key',
    'pmk_admin_supervisor_session',
  ];

  function removeStorageKey(storage, key) {
    try {
      storage.removeItem(key);
    } catch (error) {}
  }

  function purgeLegacyCredentialStorage() {
    LEGACY_AUTH_KEYS.forEach((key) => {
      removeStorageKey(localStorage, key);
      removeStorageKey(sessionStorage, key);
    });
    LEGACY_SUPERVISOR_KEYS.forEach((key) => {
      removeStorageKey(localStorage, key);
      removeStorageKey(sessionStorage, key);
    });
    removeStorageKey(localStorage, IDENTITY_TOKEN_KEY);
    removeStorageKey(localStorage, 'maestro_role');
    removeStorageKey(localStorage, SUPERVISOR_SESSION_KEY);
  }

  function sessionValue(key) {
    try {
      return String(sessionStorage.getItem(key) || '').trim();
    } catch (error) {
      return '';
    }
  }

  function bearer() {
    return sessionValue(IDENTITY_TOKEN_KEY);
  }

  function tokenKey() {
    return bearer() ? `sessionStorage:${IDENTITY_TOKEN_KEY}` : '';
  }

  function apiKey() {
    if (!LOCAL_DEVELOPMENT_HOSTS.has(window.location.hostname)) return '';
    return sessionValue(LOCAL_DEV_API_KEY);
  }

  function supervisorSessionKey() {
    return sessionValue(SUPERVISOR_SESSION_KEY);
  }

  function headers(existingHeaders) {
    const result = new Headers(existingHeaders || {});
    const identityToken = bearer();
    const localApiKey = apiKey();
    const supervisorKey = supervisorSessionKey();

    if (!result.has('Content-Type')) {
      result.set('Content-Type', 'application/json');
    }
    if (identityToken && !result.has('Authorization')) {
      result.set('Authorization', `Bearer ${identityToken}`);
    }
    if (localApiKey && !result.has('X-API-Key')) {
      result.set('X-API-Key', localApiKey);
    }
    if (supervisorKey && !result.has('X-Supervisor-Session-Key')) {
      result.set('X-Supervisor-Session-Key', supervisorKey);
    }
    return result;
  }

  function clearIdentitySession() {
    try {
      sessionStorage.removeItem(IDENTITY_TOKEN_KEY);
      sessionStorage.removeItem('maestro_role');
      sessionStorage.removeItem('maestro_ui_session_started_at');
      sessionStorage.removeItem('maestro_ui_session_refreshed_at');
    } catch (error) {}
  }

  function diagnostic() {
    return {
      authMode: 'identity_session_v2',
      bearerFound: Boolean(bearer()),
      bearerKey: tokenKey(),
      supervisorSessionKeyFound: Boolean(supervisorSessionKey()),
      localDevelopmentApiKeyFound: Boolean(apiKey()),
      legacyStorageScanEnabled: false,
      legacyCredentialStoragePurged: true,
      localStorageUsedForAuth: false,
    };
  }

  function shouldAttachHeaders(url) {
    try {
      const target = new URL(url, window.location.href);
      if (target.origin !== window.location.origin) return false;
      if (target.pathname.startsWith('/console/')) return false;
      if (target.pathname === '/admin') return false;
      return (
        target.pathname.startsWith('/auth/') ||
        target.pathname.startsWith('/settings/') ||
        target.pathname.startsWith('/adapters/') ||
        target.pathname.startsWith('/applications') ||
        target.pathname.startsWith('/admin-marketplace') ||
        target.pathname.startsWith('/billing') ||
        target.pathname.startsWith('/health/') ||
        target.pathname.startsWith('/evaluation/')
      );
    } catch (error) {
      return false;
    }
  }

  function installFetchBridge() {
    if (window.PMK_ADMIN_AUTH_FETCH_BRIDGED) return;
    const originalFetch = window.fetch.bind(window);

    window.fetch = function identitySessionFetch(input, init) {
      const url = typeof input === 'string' ? input : input?.url || '';
      const nextInit = Object.assign({}, init || {});
      if (shouldAttachHeaders(url)) {
        const sourceHeaders =
          nextInit.headers ||
          (typeof input !== 'string' && input && input.headers ? input.headers : undefined);
        nextInit.headers = headers(sourceHeaders);
        nextInit.credentials = nextInit.credentials || 'include';
      }
      return originalFetch(input, nextInit);
    };

    window.PMK_ADMIN_AUTH_FETCH_BRIDGED = true;
  }

  purgeLegacyCredentialStorage();

  window.PMK_ADMIN_AUTH = {
    mode: 'identity_session_v2',
    bearer,
    tokenKey,
    apiKey,
    supervisorSessionKey,
    headers,
    diagnostic,
    clearIdentitySession,
    purgeLegacyCredentialStorage,
    installFetchBridge,
  };

  installFetchBridge();
})();
