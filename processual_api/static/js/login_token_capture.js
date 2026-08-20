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
    group.style.position = 'relative';
    password.style.paddingInlineEnd = '72px';
    const button = document.createElement('button');
    button.id = 'login-password-visibility';
    button.type = 'button';
    button.textContent = message('Show', 'إظهار');
    button.setAttribute('aria-label', message('Show password', 'إظهار كلمة المرور'));
    button.setAttribute('aria-pressed', 'false');
    button.style.cssText = 'position:absolute;inset-inline-end:8px;bottom:7px;border:1px solid var(--rim);border-radius:6px;background:rgba(17,22,32,.92);color:var(--soft);font:10px var(--font-data);padding:5px 8px;cursor:pointer';
    button.addEventListener('click', () => {
      const visible = password.type === 'text';
      password.type = visible ? 'password' : 'text';
      button.textContent = visible ? message('Show', 'إظهار') : message('Hide', 'إخفاء');
      button.setAttribute('aria-label', visible ? message('Show password', 'إظهار كلمة المرور') : message('Hide password', 'إخفاء كلمة المرور'));
      button.setAttribute('aria-pressed', visible ? 'false' : 'true');
    });
    group.appendChild(button);
  }

  function syncMfaChallengeLanguage() {
    const label = document.getElementById('identity-mfa-label');
    const hint = document.getElementById('identity-mfa-hint');
    const verify = document.getElementById('identity-mfa-verify');
    const toggle = document.getElementById('identity-mfa-recovery-toggle');
    const input = document.getElementById('identity-mfa-code');
    if (!label || !hint || !verify || !toggle || !input) return;
    if (recoveryMode) {
      label.textContent = message('Recovery code', 'رمز الاسترداد');
      hint.textContent = message('Enter one unused recovery code.', 'أدخل رمز استرداد غير مستخدم.');
      toggle.textContent = message('Use authenticator code instead', 'استخدم رمز تطبيق المصادقة');
      input.placeholder = 'XXXX-XXXX';
      input.inputMode = 'text';
    } else {
      label.textContent = message('Authenticator code', 'رمز تطبيق المصادقة');
      hint.textContent = message('Enter the code from your authenticator app.', 'أدخل الرمز من تطبيق المصادقة.');
      toggle.textContent = message('Use a recovery code instead', 'استخدم رمز الاسترداد بدلًا من ذلك');
      input.placeholder = '123456';
      input.inputMode = 'numeric';
    }
    verify.textContent = message('Verify', 'تحقق');
  }

  function buildMfaChallenge() {
    if (document.getElementById('identity-mfa-challenge')) return;
    const loginButton = document.getElementById('login-btn');
    if (!loginButton) return;
    const challenge = document.createElement('div');
    challenge.id = 'identity-mfa-challenge';
    challenge.hidden = true;
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
    const fields = document.getElementById('login-fields');
    const loginButton = document.getElementById('login-btn');
    const tabs = document.querySelector('.tab-row');
    if (challenge) challenge.hidden = false;
    if (fields) fields.hidden = true;
    if (loginButton) loginButton.hidden = true;
    if (tabs) tabs.hidden = true;
    syncMfaChallengeLanguage();
    document.getElementById('identity-mfa-code')?.focus();
  }

  function resetMfaChallenge() {
    pendingMfaToken = '';
    pendingCsrfToken = '';
    recoveryMode = false;
    const challenge = document.getElementById('identity-mfa-challenge');
    const fields = document.getElementById('login-fields');
    const loginButton = document.getElementById('login-btn');
    const tabs = document.querySelector('.tab-row');
    if (challenge) challenge.hidden = true;
    if (fields) fields.hidden = false;
    if (loginButton) loginButton.hidden = false;
    if (tabs) tabs.hidden = false;
    const input = document.getElementById('identity-mfa-code');
    if (input) input.value = '';
  }

  async function identityLogin() {
    const email = document.getElementById('login-username')?.value?.trim() || '';
    const password = document.getElementById('login-password')?.value || '';
    const button = document.getElementById('login-btn');
    if (!email || !password) { showError(message('Enter email and password', 'أدخل البريد الإلكتروني وكلمة المرور')); return; }
    clearError();
    if (button) { button.disabled = true; button.textContent = message('Signing in...', 'جار تسجيل الدخول...'); }
    try {
      const response = await fetch('/auth/login', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || message('Invalid credentials', 'بيانات الدخول غير صحيحة'));
      if (data.mfa_required === true) {
        pendingMfaToken = normalizeToken(data.access_token);
        pendingCsrfToken = String(data.csrf_token || '');
        if (!pendingMfaToken || !pendingCsrfToken) throw new Error(message('MFA session could not be established.', 'تعذر إنشاء جلسة المصادقة متعددة العوامل.'));
        clearRestrictedTokenCopies();
        showMfaChallenge();
        return;
      }
      const token = normalizeToken(data.access_token);
      if (!token) throw new Error(message('Login response did not contain a valid token.', 'استجابة الدخول لا تحتوي على رمز صالح.'));
      persistUserSession(token);
      window.location.href = '/console';
    } catch (error) { showError(error?.message || message('Login failed', 'فشل تسجيل الدخول')); }
    finally { if (button) { button.disabled = false; button.textContent = message('Sign In', 'تسجيل الدخول'); } }
  }

  async function verifyMfaChallenge() {
    const input = document.getElementById('identity-mfa-code');
    const button = document.getElementById('identity-mfa-verify');
    const credential = input?.value?.trim() || '';
    if (!credential || !pendingMfaToken || !pendingCsrfToken) { showError(message('Enter your MFA credential.', 'أدخل رمز المصادقة متعددة العوامل.')); return; }
    clearError();
    if (button) { button.disabled = true; button.textContent = message('Verifying...', 'جار التحقق...'); }
    try {
      const verification = await fetch('/auth/mfa/verify', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${pendingMfaToken}` }, body: JSON.stringify(recoveryMode ? { recovery_code: credential } : { code: credential }) });
      const verificationData = await verification.json().catch(() => ({}));
      if (!verification.ok) throw new Error(verificationData.detail || message('Invalid MFA credential.', 'رمز المصادقة غير صالح.'));
      const refreshed = await fetch('/auth/session/refresh', { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': pendingCsrfToken } });
      const refreshedData = await refreshed.json().catch(() => ({}));
      if (!refreshed.ok) throw new Error(refreshedData.detail || message('Unable to complete MFA login.', 'تعذر إكمال تسجيل الدخول بالمصادقة متعددة العوامل.'));
      if (refreshedData.mfa_required === true) throw new Error(message('MFA verification is still required.', 'لا يزال التحقق متعدد العوامل مطلوبًا.'));
      const token = normalizeToken(refreshedData.access_token);
      if (!token) throw new Error(message('MFA completion did not return a valid token.', 'إكمال المصادقة لم يُرجع رمز دخول صالحًا.'));
      persistUserSession(token);
      pendingMfaToken = '';
      pendingCsrfToken = '';
      window.location.href = '/console';
    } catch (error) { showError(error?.message || message('MFA verification failed', 'فشل التحقق متعدد العوامل')); }
    finally { if (button) { button.disabled = false; button.textContent = message('Verify', 'تحقق'); } }
  }

  function installIdentityMfaLogin() {
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
    document.getElementById('lang-en')?.addEventListener('click', syncMfaChallengeLanguage);
    document.getElementById('lang-ar')?.addEventListener('click', syncMfaChallengeLanguage);
    if (isUserMode() && username) username.placeholder = 'email@example.com';
  }

  window.PMK_LOGIN_TOKEN_CAPTURE = { persistAuthPayload, normalizeToken, installFetchCapture, installIdentityMfaLogin, installPasswordVisibilityControl };
  installFetchCapture();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', installIdentityMfaLogin, { once: true });
  else installIdentityMfaLogin();
})();
