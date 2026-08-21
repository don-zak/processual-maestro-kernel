(function () {
  let pendingMfaToken = '';
  let pendingCsrfToken = '';
  let recoveryMode = false;

  function firstTokenFromObject(value) {
    if (!value || typeof value !== 'object') return '';
    return (
      value.access_token || value.accessToken || value.token || value.auth_token || value.authToken ||
      value.jwt || value.bearer || value.admin_token || value.adminToken || value.admin_access_token ||
      value.adminAccessToken || value?.data?.access_token || value?.data?.accessToken || value?.data?.token ||
      value?.session?.access_token || value?.session?.accessToken || value?.session?.token ||
      value?.user?.access_token || value?.user?.accessToken || value?.user?.token || ''
    );
  }

  function normalizeToken(value) {
    if (!value) return '';
    if (typeof value === 'object') return normalizeToken(firstTokenFromObject(value));
    const raw = String(value).trim();
    if (!raw) return '';
    if (raw.startsWith('Bearer ')) return raw.slice('Bearer '.length).trim();
    if (raw.startsWith('{') || raw.startsWith('[') || raw.startsWith('"')) {
      try { return normalizeToken(JSON.parse(raw)); } catch (error) {}
    }
    if (raw.split('.').length === 3 || raw.startsWith('eyJ')) return raw;
    if (raw.length > 40 && !raw.includes(' ')) return raw;
    return '';
  }

  function roleFromPayload(payload) {
    return payload?.role || payload?.user_role || payload?.account_role || payload?.data?.role || payload?.user?.role || '';
  }

  function persistAuthPayload(payload) {
    if (payload?.mfa_required === true) return false;
    const token = normalizeToken(payload);
    if (!token) return false;
    const role = roleFromPayload(payload);
    const isAdmin = role === 'admin' || role === 'administrator' || window.location.search.includes('mode=admin');
    const authRecord = { access_token: token, token, role: role || (isAdmin ? 'admin' : 'user'), saved_at: new Date().toISOString(), source: 'login_token_capture' };
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

  function clearRestrictedTokenCopies() {
    ['access_token','auth_token','maestro_auth_token','processual_auth_token','processual_session','maestro_token','maestro_role'].forEach((key) => {
      localStorage.removeItem(key);
      sessionStorage.removeItem(key);
    });
  }

  function persistUserSession(token) {
    clearRestrictedTokenCopies();
    sessionStorage.setItem('maestro_token', token);
    sessionStorage.setItem('maestro_role', 'user');
    sessionStorage.setItem('maestro_ui_session_started_at', new Date().toISOString());
  }

  function shouldCapture(url, init) {
    const method = String(init?.method || 'GET').toUpperCase();
    if (method !== 'POST') return false;
    try {
      const target = new URL(url, window.location.href);
      return target.pathname.includes('/auth/login') || target.pathname.includes('/auth/session/refresh') || target.pathname.endsWith('/login') || target.pathname.includes('/token');
    } catch (error) { return false; }
  }

  function installFetchCapture() {
    if (window.PMK_LOGIN_TOKEN_CAPTURE_INSTALLED) return;
    const originalFetch = window.fetch.bind(window);
    window.fetch = async function loginTokenCapturingFetch(input, init) {
      const url = typeof input === 'string' ? input : input?.url || '';
      const response = await originalFetch(input, init);
      if (shouldCapture(url, init)) {
        try { persistAuthPayload(await response.clone().json()); } catch (error) {}
      }
      return response;
    };
    window.PMK_LOGIN_TOKEN_CAPTURE_INSTALLED = true;
  }

  const currentLanguage = () => document.documentElement.lang === 'ar' ? 'ar' : 'en';
  const message = (en, ar) => currentLanguage() === 'ar' ? ar : en;
  const isUserMode = () => document.getElementById('tab-user')?.classList.contains('active') === true;

  function lockLoginToEnglish() {
    document.documentElement.lang = 'en';
    document.documentElement.dir = 'ltr';
    if (document.body) document.body.dir = 'ltr';
    const bar = document.querySelector('.lang-bar');
    if (bar) {
      bar.hidden = true;
      bar.setAttribute('aria-hidden', 'true');
    }
  }

  function showError(text) {
    const error = document.getElementById('login-error');
    if (!error) return;
    error.textContent = text;
    error.style.display = 'block';
  }

  function clearError() {
    const error = document.getElementById('login-error');
    if (error) error.style.display = 'none';
  }

  function installPasswordVisibilityControl() {
    const password = document.getElementById('login-password');
    if (!password || document.getElementById('login-password-visibility')) return;
    const group = password.closest('.inp-group');
    if (!group) return;

    const shell = document.createElement('div');
    shell.id = 'login-password-shell';
    shell.style.cssText = 'position:relative;width:100%';
    group.insertBefore(shell, password);
    shell.appendChild(password);
    password.style.paddingInlineEnd = '76px';

    const button = document.createElement('button');
    button.id = 'login-password-visibility';
    button.type = 'button';
    button.textContent = 'Show';
    button.setAttribute('aria-label', 'Show password');
    button.setAttribute('aria-pressed', 'false');
    button.style.cssText = 'position:absolute;inset-inline-end:8px;top:50%;transform:translateY(-50%);z-index:2;border:1px solid var(--rim);border-radius:6px;background:rgba(17,22,32,.96);color:var(--soft);font:10px var(--font-data);line-height:1;padding:6px 8px;cursor:pointer';
    button.addEventListener('click', () => {
      const visible = password.type === 'text';
      password.type = visible ? 'password' : 'text';
      button.textContent = visible ? 'Show' : 'Hide';
      button.setAttribute('aria-label', visible ? 'Show password' : 'Hide password');
      button.setAttribute('aria-pressed', visible ? 'false' : 'true');
      password.focus({ preventScroll: true });
    });
    shell.appendChild(button);
  }

  function syncMfaChallengeLanguage() {
    const label = document.getElementById('identity-mfa-label');
    const hint = document.getElementById('identity-mfa-hint');
    const verify = document.getElementById('identity-mfa-verify');
    const toggle = document.getElementById('identity-mfa-recovery-toggle');
    const input = document.getElementById('identity-mfa-code');
    if (!label || !hint || !verify || !toggle || !input) return;
    if (recoveryMode) {
      label.textContent = 'Recovery code';
      hint.textContent = 'Enter one unused recovery code.';
      toggle.textContent = 'Use authenticator code instead';
      input.placeholder = 'XXXX-XXXX';
      input.inputMode = 'text';
    } else {
      label.textContent = 'Authenticator code';
      hint.textContent = 'Enter the code from your authenticator app.';
      toggle.textContent = 'Use a recovery code instead';
      input.placeholder = '123456';
      input.inputMode = 'numeric';
    }
    verify.textContent = 'Verify';
  }

  function setMfaLayout(active) {
    const card = document.querySelector('.card');
    const fields = document.getElementById('login-fields');
    const loginButton = document.getElementById('login-btn');
    const tabs = document.querySelector('.tab-row');
    const commercialActions = document.getElementById('login-commercial-actions');
    const commercialPanel = document.getElementById('commercial-offers-panel');
    const lostAccessPanel = document.getElementById('lost-access-panel');

    if (card) card.dataset.mfaActive = active ? 'true' : 'false';
    if (fields) fields.hidden = active;
    if (loginButton) loginButton.hidden = active;
    if (tabs) tabs.hidden = active;
    if (commercialActions) commercialActions.hidden = active;
    if (commercialPanel) commercialPanel.hidden = true;
    if (lostAccessPanel) lostAccessPanel.hidden = true;
  }

  function buildMfaChallenge() {
    if (document.getElementById('identity-mfa-challenge')) return;
    const loginButton = document.getElementById('login-btn');
    if (!loginButton) return;
    const challenge = document.createElement('div');
    challenge.id = 'identity-mfa-challenge';
    challenge.hidden = true;
    challenge.style.cssText = 'width:100%;margin:0';
    challenge.innerHTML = '<div class="inp-group"><label class="inp-label" id="identity-mfa-label">Authenticator code</label><input id="identity-mfa-code" class="inp" inputmode="numeric" autocomplete="one-time-code" maxlength="64" placeholder="123456"><div class="inp-hint" id="identity-mfa-hint">Enter the code from your authenticator app.</div></div><button id="identity-mfa-verify" class="btn primary" type="button">Verify</button><button id="identity-mfa-recovery-toggle" class="btn-text" type="button" style="border:0;background:transparent;width:100%;cursor:pointer">Use a recovery code instead</button>';
    loginButton.insertAdjacentElement('beforebegin', challenge);
    document.getElementById('identity-mfa-verify')?.addEventListener('click', verifyMfaChallenge);
    document.getElementById('identity-mfa-recovery-toggle')?.addEventListener('click', () => {
      recoveryMode = !recoveryMode;
      syncMfaChallengeLanguage();
      const input = document.getElementById('identity-mfa-code');
      if (input) { input.value = ''; input.focus(); }
    });
    document.getElementById('identity-mfa-code')?.addEventListener('keydown', (event) => { if (event.key === 'Enter') verifyMfaChallenge(); });
    syncMfaChallengeLanguage();
  }

  function showMfaChallenge() {
    buildMfaChallenge();
    const challenge = document.getElementById('identity-mfa-challenge');
    if (challenge) challenge.hidden = false;
    setMfaLayout(true);
    syncMfaChallengeLanguage();
    document.getElementById('identity-mfa-code')?.focus({ preventScroll: true });
  }

  function resetMfaChallenge() {
    pendingMfaToken = '';
    pendingCsrfToken = '';
    recoveryMode = false;
    const challenge = document.getElementById('identity-mfa-challenge');
    if (challenge) challenge.hidden = true;
    setMfaLayout(false);
    const input = document.getElementById('identity-mfa-code');
    if (input) input.value = '';
  }

  async function identityLogin() {
    const email = document.getElementById('login-username')?.value?.trim() || '';
    const password = document.getElementById('login-password')?.value || '';
    const button = document.getElementById('login-btn');
    if (!email || !password) { showError('Enter email and password'); return; }
    clearError();
    if (button) { button.disabled = true; button.textContent = 'Signing in...'; }
    try {
      const response = await fetch('/auth/login', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Invalid credentials');
      if (data.mfa_required === true) {
        pendingMfaToken = normalizeToken(data.access_token);
        pendingCsrfToken = String(data.csrf_token || '');
        if (!pendingMfaToken || !pendingCsrfToken) throw new Error('MFA session could not be established.');
        clearRestrictedTokenCopies();
        showMfaChallenge();
        return;
      }
      const token = normalizeToken(data.access_token);
      if (!token) throw new Error('Login response did not contain a valid token.');
      persistUserSession(token);
      window.location.href = '/console';
    } catch (error) { showError(error?.message || 'Login failed'); }
    finally { if (button) { button.disabled = false; button.textContent = 'Sign In'; } }
  }

  async function verifyMfaChallenge() {
    const input = document.getElementById('identity-mfa-code');
    const button = document.getElementById('identity-mfa-verify');
    const credential = input?.value?.trim() || '';
    if (!credential || !pendingMfaToken || !pendingCsrfToken) { showError('Enter your MFA credential.'); return; }
    clearError();
    if (button) { button.disabled = true; button.textContent = 'Verifying...'; }
    try {
      const verification = await fetch('/auth/mfa/verify', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${pendingMfaToken}` }, body: JSON.stringify(recoveryMode ? { recovery_code: credential } : { code: credential }) });
      const verificationData = await verification.json().catch(() => ({}));
      if (!verification.ok) throw new Error(verificationData.detail || 'Invalid MFA credential.');
      const refreshed = await fetch('/auth/session/refresh', { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': pendingCsrfToken } });
      const refreshedData = await refreshed.json().catch(() => ({}));
      if (!refreshed.ok) throw new Error(refreshedData.detail || 'Unable to complete MFA login.');
      if (refreshedData.mfa_required === true) throw new Error('MFA verification is still required.');
      const token = normalizeToken(refreshedData.access_token);
      if (!token) throw new Error('MFA completion did not return a valid token.');
      persistUserSession(token);
      pendingMfaToken = '';
      pendingCsrfToken = '';
      window.location.href = '/console';
    } catch (error) { showError(error?.message || 'MFA verification failed'); }
    finally { if (button) { button.disabled = false; button.textContent = 'Verify'; } }
  }

  function installIdentityMfaLogin() {
    lockLoginToEnglish();
    buildMfaChallenge();
    installPasswordVisibilityControl();
    const loginButton = document.getElementById('login-btn');
    const password = document.getElementById('login-password');
    const userTab = document.getElementById('tab-user');
    const adminTab = document.getElementById('tab-admin');
    const username = document.getElementById('login-username');
    loginButton?.addEventListener('click', (event) => { if (!isUserMode()) return; event.preventDefault(); event.stopImmediatePropagation(); identityLogin(); }, true);
    password?.addEventListener('keydown', (event) => { if (event.key !== 'Enter' || !isUserMode()) return; event.preventDefault(); event.stopImmediatePropagation(); identityLogin(); }, true);
    userTab?.addEventListener('click', () => { resetMfaChallenge(); if (username) username.placeholder = 'email@example.com'; });
    adminTab?.addEventListener('click', resetMfaChallenge);
    if (isUserMode() && username) username.placeholder = 'email@example.com';
  }

  window.PMK_LOGIN_TOKEN_CAPTURE = { persistAuthPayload, normalizeToken, installFetchCapture, installIdentityMfaLogin, installPasswordVisibilityControl };
  installFetchCapture();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', installIdentityMfaLogin, { once: true });
  else installIdentityMfaLogin();
})();
