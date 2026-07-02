
(function () {
  const preferredKeys = [
    'token',
    'access_token',
    'accessToken',
    'auth_token',
    'authToken',
    'jwt',
    'bearer',
    'maestro_token',
    'maestroToken',
    'maestro_auth_token',
    'maestroAuthToken',
    'pmk_token',
    'pmkToken',
    'pmk_auth_token',
    'pmkAuthToken',
    'admin_token',
    'adminToken',
    'admin_access_token',
    'adminAccessToken',
    'processual_token',
    'processualToken',
    'processual_auth_token',
    'processualAuthToken',
    'processual_session',
    'processualSession',
    'maestro_session',
    'maestroSession',
    'session',
    'auth',
    'user',
  ];

  function fromObject(value) {
    if (!value || typeof value !== 'object') return '';

    return (
      value.access_token ||
      value.accessToken ||
      value.token ||
      value.auth_token ||
      value.authToken ||
      value.jwt ||
      value.bearer ||
      value.api_token ||
      value.apiToken ||
      value.admin_token ||
      value.adminToken ||
      value.admin_access_token ||
      value.adminAccessToken ||
      value?.data?.access_token ||
      value?.data?.accessToken ||
      value?.data?.token ||
      value?.session?.access_token ||
      value?.session?.accessToken ||
      value?.session?.token ||
      value?.user?.access_token ||
      value?.user?.accessToken ||
      value?.user?.token ||
      ''
    );
  }

  function normalizeCandidate(value) {
    if (!value) return '';
    if (typeof value !== 'string') return '';

    const raw = value.trim();

    if (!raw) return '';

    if (raw.startsWith('Bearer ')) {
      return raw.slice('Bearer '.length).trim();
    }

    if (raw.startsWith('{') || raw.startsWith('[') || raw.startsWith('"')) {
      try {
        const parsed = JSON.parse(raw);

        if (typeof parsed === 'string') {
          return normalizeCandidate(parsed);
        }

        return normalizeCandidate(fromObject(parsed));
      } catch (error) {}
    }

    if (raw.split('.').length === 3 || raw.startsWith('eyJ')) {
      return raw;
    }

    if (raw.length > 40 && !raw.includes(' ')) {
      return raw;
    }

    return '';
  }

  function scanStorage(storage) {
    for (const key of preferredKeys) {
      try {
        const found = normalizeCandidate(storage.getItem(key));
        if (found) return { token: found, key };
      } catch (error) {}
    }

    try {
      for (let index = 0; index < storage.length; index += 1) {
        const key = storage.key(index);
        if (!key) continue;

        const lower = key.toLowerCase();

        if (
          !lower.includes('token') &&
          !lower.includes('auth') &&
          !lower.includes('jwt') &&
          !lower.includes('session') &&
          !lower.includes('maestro') &&
          !lower.includes('processual') &&
          !lower.includes('pmk')
        ) {
          continue;
        }

        const found = normalizeCandidate(storage.getItem(key));
        if (found) return { token: found, key };
      }
    } catch (error) {}

    return { token: '', key: '' };
  }

  function bearer() {
    const local = scanStorage(localStorage);
    if (local.token) return local.token;

    const session = scanStorage(sessionStorage);
    if (session.token) return session.token;

    return '';
  }

  function tokenKey() {
    const local = scanStorage(localStorage);
    if (local.token) return 'localStorage:' + local.key;

    const session = scanStorage(sessionStorage);
    if (session.token) return 'sessionStorage:' + session.key;

    return '';
  }

  function apiKey() {
    const keys = ['api_key', 'apiKey', 'x_api_key', 'xApiKey', 'X-API-Key'];

    for (const storage of [localStorage, sessionStorage]) {
      for (const key of keys) {
        try {
          const value = storage.getItem(key);
          if (value) return value;
        } catch (error) {}
      }
    }

    return '';
  }

  function headers(existingHeaders) {
    const result = new Headers(existingHeaders || {});
    const foundBearer = bearer();
    const foundApiKey = apiKey();

    if (!result.has('Content-Type')) {
      result.set('Content-Type', 'application/json');
    }

    if (foundBearer && !result.has('Authorization')) {
      result.set('Authorization', 'Bearer ' + foundBearer);
    }

    if (foundApiKey && !result.has('X-API-Key')) {
      result.set('X-API-Key', foundApiKey);
    }

    return result;
  }

  function diagnostic() {
    return {
      bearerFound: Boolean(bearer()),
      bearerKey: tokenKey(),
      apiKeyFound: Boolean(apiKey()),
      localStorageKeys: Object.keys(localStorage).filter((key) =>
        /token|auth|jwt|session|maestro|processual|pmk/i.test(key)
      ),
      sessionStorageKeys: Object.keys(sessionStorage).filter((key) =>
        /token|auth|jwt|session|maestro|processual|pmk/i.test(key)
      ),
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
        target.pathname.startsWith('/billing') ||
        target.pathname.startsWith('/health/')
      );
    } catch (error) {
      return false;
    }
  }

  function installFetchBridge() {
    if (window.PMK_ADMIN_AUTH_FETCH_BRIDGED) return;

    const originalFetch = window.fetch.bind(window);

    window.fetch = function bridgedFetch(input, init) {
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
    bearer,
    tokenKey,
    apiKey,
    headers,
    diagnostic,
    installFetchBridge,
  };

  installFetchBridge();
})();
