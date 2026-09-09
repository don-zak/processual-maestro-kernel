(function () {
  const IDENTITY_TOKEN_KEY = 'maestro_token';
  const SUPERVISOR_SESSION_KEY = 'pmk_supervisor_session_key';
  const LOCAL_DEV_API_KEY = 'api_key';
  const LOCAL_DEVELOPMENT_HOSTS = new Set(['127.0.0.1', 'localhost', '::1']);

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

  window.PMK_ADMIN_AUTH = {
    mode: 'identity_session_v2',
    bearer,
    tokenKey,
    apiKey,
    supervisorSessionKey,
    headers,
    diagnostic,
    clearIdentitySession,
    installFetchBridge,
  };

  installFetchBridge();
})();
