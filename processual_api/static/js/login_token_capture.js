
(function () {
  function firstTokenFromObject(value) {
    if (!value || typeof value !== 'object') return '';

    return (
      value.access_token ||
      value.accessToken ||
      value.token ||
      value.auth_token ||
      value.authToken ||
      value.jwt ||
      value.bearer ||
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

  function normalizeToken(value) {
    if (!value) return '';

    if (typeof value === 'object') {
      return normalizeToken(firstTokenFromObject(value));
    }

    const raw = String(value).trim();

    if (!raw) return '';

    if (raw.startsWith('Bearer ')) {
      return raw.slice('Bearer '.length).trim();
    }

    if (raw.startsWith('{') || raw.startsWith('[') || raw.startsWith('"')) {
      try {
        return normalizeToken(JSON.parse(raw));
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

  function roleFromPayload(payload) {
    return (
      payload?.role ||
      payload?.user_role ||
      payload?.account_role ||
      payload?.data?.role ||
      payload?.user?.role ||
      ''
    );
  }

  function persistAuthPayload(payload) {
    const token = normalizeToken(payload);
    if (!token) return false;

    const role = roleFromPayload(payload);
    const isAdmin =
      role === 'admin' ||
      role === 'administrator' ||
      window.location.search.includes('mode=admin');

    const authRecord = {
      access_token: token,
      token: token,
      role: role || (isAdmin ? 'admin' : 'user'),
      saved_at: new Date().toISOString(),
      source: 'login_token_capture',
    };

    localStorage.setItem('access_token', token);
    localStorage.setItem('auth_token', token);
    localStorage.setItem('maestro_auth_token', token);
    localStorage.setItem('processual_auth_token', token);
    localStorage.setItem('processual_session', JSON.stringify(authRecord));

    if (isAdmin) {
      localStorage.setItem('admin_access_token', token);
      localStorage.setItem('admin_token', token);
      localStorage.setItem('admin_session', JSON.stringify(authRecord));
    }

    return true;
  }

  function shouldCapture(url, init) {
    const method = String(init?.method || 'GET').toUpperCase();

    if (method !== 'POST') return false;

    try {
      const target = new URL(url, window.location.href);
      return (
        target.pathname.includes('/auth/login') ||
        target.pathname.endsWith('/login') ||
        target.pathname.includes('/token')
      );
    } catch (error) {
      return false;
    }
  }

  function installFetchCapture() {
    if (window.PMK_LOGIN_TOKEN_CAPTURE_INSTALLED) return;

    const originalFetch = window.fetch.bind(window);

    window.fetch = async function loginTokenCapturingFetch(input, init) {
      const url = typeof input === 'string' ? input : input?.url || '';
      const response = await originalFetch(input, init);

      if (shouldCapture(url, init)) {
        try {
          const clone = response.clone();
          const payload = await clone.json();
          persistAuthPayload(payload);
        } catch (error) {}
      }

      return response;
    };

    window.PMK_LOGIN_TOKEN_CAPTURE_INSTALLED = true;
  }

  window.PMK_LOGIN_TOKEN_CAPTURE = {
    persistAuthPayload,
    normalizeToken,
    installFetchCapture,
  };

  installFetchCapture();
})();
