(function () {
  let pendingMfaToken = '';
  let pendingCsrfToken = '';
  let recoveryMode = false;
  let completedIdentityToken = '';

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
    [
      'access_token', 'auth_token', 'maestro_auth_token', 'processual_auth_token',
      'processual_session', 'maestro_token', 'maestro_role', 'admin_access_token',
      'admin_token', 'admin_session',
    ].forEach((key) => {
      localStorage.removeItem(key);
      sessionStorage.removeItem(key);
    });
  }

  function explicitSuperAdminMode() {
    const params = new URLSearchParams(window.location.search);
    return params.get('identity') === '1' && params.get('mode') === 'admin';
  }

  function safeIdentityDestination() {
    const requested = new URLSearchParams(window.location.search).get('next') || '';
    if (!requested.startsWith('/')) {
      return explicitSuperAdminMode() ? '/admin#api-keys' : '/console';
    }
    try {
      const target = new URL(requested, window.location.origin);
      if (target.origin !== window.location.origin) return '/console';
      if (target.pathname !== '/admin' && target.pathname !== '/console') return '/console';
      return `${target.pathname}${target.search}${target.hash}`;
    } catch (error) {
      return '/console';
    }
  }

  function persistIdentitySession(token) {
    clearRestrictedTokenCopies();
    const destination = safeIdentityDestination();
    sessionStorage.setItem('maestro_token', token);
    sessionStorage.setItem('maestro_role', destination.startsWith('/admin') ? 'admin' : 'user');
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
  const isIdentityMode = () => isUserMode() || explicitSuperAdminMode();

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

  function buildPasswordVisibilityToggle() {
    const input = document.getElementById('login-password');
    if (!input || document.getElementById('login-password-visibility')) return;

    const parent = input.parentElement;
    if (!parent) return;

    const wrapper = document.createElement('div');
    wrapper.style.position = 'relative';
    parent.insertBefore(wrapper, input);
    wrapper.appendChild(input);
    input.style.paddingRight = '4.75rem';

    const toggle = document.createElement('button');
    toggle.id = 'login-password-visibility';
    toggle.type = 'button';
    toggle.setAttribute('aria-label', 'Show password');
    toggle.setAttribute('aria-pressed', 'false');
    toggle.textContent = 'Show';
    Object.assign(toggle.style, {
      position: 'absolute',
      right: '0.8rem',
      top: '50%',
      transform: 'translateY(-50%)',
      border: '0',
      background: 'transparent',
      color: 'var(--amber)',
      fontFamily: 'var(--font-data)',
      fontSize: '10px',
      cursor: 'pointer',
      padding: '0.25rem',
    });
    toggle.addEventListener('click', () => {
      const reveal = input.type === 'password';
      input.type = reveal ? 'text' : 'password';
      toggle.setAttribute('aria-pressed', String(reveal));
      toggle.setAttribute('aria-label', reveal ? 'Hide password' : 'Show password');
      toggle.textContent = reveal ? 'Hide' : 'Show';
      input.focus();
    });
    wrapper.appendChild(toggle);
  }

  function syncIdentityModePresentation() {
    const username = document.getElementById('login-username');
    const usernameLabel = username?.closest('.inp-group')?.querySelector('.inp-label');
    if (isIdentityMode()) {
      if (username) username.placeholder = 'email@example.com';
      if (usernameLabel) usernameLabel.textContent = message('Email', 'البريد الإلكتروني');
      return;
    }
    if (username) username.placeholder = 'admin';
    if (usernameLabel) usernameLabel.textContent = message('Username', 'اسم المستخدم');
  }

  function pendingAuthHeaders(extra = {}) {
    return {
      ...extra,
      Authorization: `Bearer ${pendingMfaToken}`,
    };
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

  function buildMfaEnrollment() {
    if (document.getElementById('identity-mfa-enrollment')) return;
    const loginButton = document.getElementById('login-btn');
    if (!loginButton) return;
    const panel = document.createElement('div');
    panel.id = 'identity-mfa-enrollment';
    panel.hidden = true;
    panel.innerHTML = `
      <div class="inp-group">
        <label class="inp-label">Set up authenticator</label>
        <div class="inp-hint">Add this secret to your authenticator app. The secret is shown only for this enrollment response.</div>
        <div id="identity-mfa-enrollment-secret" class="inp" style="height:auto;word-break:break-all;margin-top:8px"></div>
        <div id="identity-mfa-enrollment-uri" class="inp-hint" style="word-break:break-all;margin-top:6px"></div>
      </div>
      <div class="inp-group">
        <label class="inp-label">Authenticator code</label>
        <input id="identity-mfa-enrollment-code" class="inp" inputmode="numeric" autocomplete="one-time-code" maxlength="8" placeholder="123456">
        <div class="inp-hint">Enter the current code to activate MFA and complete this identity session.</div>
      </div>
      <button id="identity-mfa-enrollment-confirm" class="btn primary" type="button">Confirm MFA</button>
    `;
    loginButton.insertAdjacentElement('beforebegin', panel);
    document.getElementById('identity-mfa-enrollment-confirm')?.addEventListener('click', confirmMfaEnrollment);
    document.getElementById('identity-mfa-enrollment-code')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') confirmMfaEnrollment();
    });
  }

  function buildRecoveryCodes() {
    if (document.getElementById('identity-mfa-recovery-codes')) return;
    const loginButton = document.getElementById('login-btn');
    if (!loginButton) return;
    const panel = document.createElement('div');
    panel.id = 'identity-mfa-recovery-codes';
    panel.hidden = true;
    panel.innerHTML = `
      <div class="inp-group">
        <label class="inp-label">Recovery codes — shown once</label>
        <div class="inp-hint">Store these codes securely before continuing. They are not saved in browser storage.</div>
        <pre id="identity-mfa-recovery-code-list" class="inp" style="height:auto;white-space:pre-wrap;margin-top:8px"></pre>
      </div>
      <button id="identity-mfa-recovery-continue" class="btn primary" type="button">I saved the codes — Continue</button>
    `;
    loginButton.insertAdjacentElement('beforebegin', panel);
    document.getElementById('identity-mfa-recovery-continue')?.addEventListener('click', continueAfterRecoveryCodes);
  }

  function hideLoginInputs() {
    const fields = document.getElementById('login-fields');
    const loginButton = document.getElementById('login-btn');
    const tabs = document.querySelector('.tab-row');
    if (fields) fields.hidden = true;
    if (loginButton) loginButton.hidden = true;
    if (tabs) tabs.hidden = true;
  }

  function clearMfaEnrollmentMaterial() {
    const secret = document.getElementById('identity-mfa-enrollment-secret');
    const uri = document.getElementById('identity-mfa-enrollment-uri');
    const code = document.getElementById('identity-mfa-enrollment-code');
    if (secret) secret.textContent = '';
    if (uri) uri.textContent = '';
    if (code) code.value = '';
  }

  function showMfaChallenge() {
    buildMfaChallenge();
    hideLoginInputs();
    const challenge = document.getElementById('identity-mfa-challenge');
    const enrollment = document.getElementById('identity-mfa-enrollment');
    const recovery = document.getElementById('identity-mfa-recovery-codes');
    if (challenge) challenge.hidden = false;
    if (enrollment) enrollment.hidden = true;
    if (recovery) recovery.hidden = true;
    syncMfaChallengeLanguage();
    document.getElementById('identity-mfa-code')?.focus();
  }

  function showMfaEnrollment(enrollment) {
    buildMfaEnrollment();
    hideLoginInputs();
    const challenge = document.getElementById('identity-mfa-challenge');
    const panel = document.getElementById('identity-mfa-enrollment');
    const recovery = document.getElementById('identity-mfa-recovery-codes');
    if (challenge) challenge.hidden = true;
    if (panel) panel.hidden = false;
    if (recovery) recovery.hidden = true;
    const secret = document.getElementById('identity-mfa-enrollment-secret');
    const uri = document.getElementById('identity-mfa-enrollment-uri');
    if (secret) secret.textContent = String(enrollment.secret || '');
    if (uri) uri.textContent = String(enrollment.provisioning_uri || '');
    document.getElementById('identity-mfa-enrollment-code')?.focus();
  }

  function showRecoveryCodes(codes) {
    clearMfaEnrollmentMaterial();
    buildRecoveryCodes();
    hideLoginInputs();
    const challenge = document.getElementById('identity-mfa-challenge');
    const enrollment = document.getElementById('identity-mfa-enrollment');
    const recovery = document.getElementById('identity-mfa-recovery-codes');
    if (challenge) challenge.hidden = true;
    if (enrollment) enrollment.hidden = true;
    if (recovery) recovery.hidden = false;
    const list = document.getElementById('identity-mfa-recovery-code-list');
    if (list) list.textContent = Array.isArray(codes) ? codes.join('\n') : '';
  }

  function resetMfaChallenge() {
    pendingMfaToken = '';
    pendingCsrfToken = '';
    completedIdentityToken = '';
    recoveryMode = false;
    clearMfaEnrollmentMaterial();
    ['identity-mfa-challenge', 'identity-mfa-enrollment', 'identity-mfa-recovery-codes'].forEach((id) => {
      const panel = document.getElementById(id);
      if (panel) panel.hidden = true;
    });
    const fields = document.getElementById('login-fields');
    const loginButton = document.getElementById('login-btn');
    const tabs = document.querySelector('.tab-row');
    if (fields) fields.hidden = false;
    if (loginButton) loginButton.hidden = false;
    if (tabs) tabs.hidden = false;
    const code = document.getElementById('identity-mfa-code');
    const recoveryList = document.getElementById('identity-mfa-recovery-code-list');
    if (code) code.value = '';
    if (recoveryList) recoveryList.textContent = '';
  }

  async function refreshCompletedIdentitySession() {
    const refreshed = await fetch('/auth/session/refresh', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRF-Token': pendingCsrfToken },
    });
    const data = await refreshed.json().catch(() => ({}));
    if (!refreshed.ok) throw new Error(data.detail || message('Unable to complete MFA login.', 'تعذر إكمال تسجيل الدخول بالمصادقة متعددة العوامل.'));
    if (data.mfa_required === true) throw new Error(message('MFA verification is still required.', 'لا يزال التحقق متعدد العوامل مطلوبًا.'));
    const token = normalizeToken(data.access_token);
    if (!token) throw new Error(message('MFA completion did not return a valid token.', 'إكمال المصادقة لم يُرجع رمز دخول صالحًا.'));
    return token;
  }

  async function beginMfaEnrollment() {
    const response = await fetch('/auth/mfa/totp/enroll', {
      method: 'POST',
      credentials: 'same-origin',
      headers: pendingAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ label: 'Primary authenticator' }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || message('Unable to start MFA enrollment.', 'تعذر بدء إعداد المصادقة متعددة العوامل.'));
    showMfaEnrollment(data);
  }

  async function continueMfaRequirement() {
    const status = await fetch('/auth/mfa/status', {
      method: 'GET',
      credentials: 'same-origin',
      headers: pendingAuthHeaders(),
    });
    const data = await status.json().catch(() => ({}));
    if (!status.ok) throw new Error(data.detail || message('Unable to read MFA status.', 'تعذر قراءة حالة المصادقة متعددة العوامل.'));
    if (data.enabled === true) {
      showMfaChallenge();
      return;
    }
    await beginMfaEnrollment();
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
        await continueMfaRequirement();
        return;
      }
      const token = normalizeToken(data.access_token);
      if (!token) throw new Error(message('Login response did not contain a valid token.', 'استجابة الدخول لا تحتوي على رمز صالح.'));
      persistIdentitySession(token);
      window.location.href = safeIdentityDestination();
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
      const verification = await fetch('/auth/mfa/verify', { method: 'POST', credentials: 'same-origin', headers: pendingAuthHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify(recoveryMode ? { recovery_code: credential } : { code: credential }) });
      const verificationData = await verification.json().catch(() => ({}));
      if (!verification.ok) throw new Error(verificationData.detail || message('Invalid MFA credential.', 'رمز المصادقة غير صالح.'));
      const token = await refreshCompletedIdentitySession();
      persistIdentitySession(token);
      pendingMfaToken = '';
      pendingCsrfToken = '';
      window.location.href = safeIdentityDestination();
    } catch (error) { showError(error?.message || message('MFA verification failed', 'فشل التحقق متعدد العوامل')); }
    finally { if (button) { button.disabled = false; button.textContent = message('Verify', 'تحقق'); } }
  }

  async function confirmMfaEnrollment() {
    const input = document.getElementById('identity-mfa-enrollment-code');
    const button = document.getElementById('identity-mfa-enrollment-confirm');
    const code = input?.value?.trim() || '';
    if (!code || !pendingMfaToken || !pendingCsrfToken) { showError(message('Enter the authenticator code.', 'أدخل رمز تطبيق المصادقة.')); return; }
    clearError();
    if (button) { button.disabled = true; button.textContent = message('Confirming...', 'جار التأكيد...'); }
    try {
      const confirmation = await fetch('/auth/mfa/totp/confirm', {
        method: 'POST',
        credentials: 'same-origin',
        headers: pendingAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ code }),
      });
      const data = await confirmation.json().catch(() => ({}));
      if (!confirmation.ok) throw new Error(data.detail || message('Unable to confirm MFA enrollment.', 'تعذر تأكيد إعداد المصادقة متعددة العوامل.'));
      completedIdentityToken = await refreshCompletedIdentitySession();
      showRecoveryCodes(data.recovery_codes || []);
    } catch (error) { showError(error?.message || message('MFA enrollment failed', 'فشل إعداد المصادقة متعددة العوامل')); }
    finally { if (button) { button.disabled = false; button.textContent = message('Confirm MFA', 'تأكيد المصادقة'); } }
  }

  function continueAfterRecoveryCodes() {
    if (!completedIdentityToken) {
      showError(message('Completed identity session is unavailable.', 'جلسة الهوية المكتملة غير متاحة.'));
      return;
    }
    const list = document.getElementById('identity-mfa-recovery-code-list');
    if (list) list.textContent = '';
    persistIdentitySession(completedIdentityToken);
    completedIdentityToken = '';
    pendingMfaToken = '';
    pendingCsrfToken = '';
    window.location.href = safeIdentityDestination();
  }

  function installIdentityMfaLogin() {
    buildMfaChallenge();
    buildMfaEnrollment();
    buildRecoveryCodes();
    buildPasswordVisibilityToggle();

    const loginButton = document.getElementById('login-btn');
    const password = document.getElementById('login-password');
    const userTab = document.getElementById('tab-user');
    const adminTab = document.getElementById('tab-admin');

    loginButton?.addEventListener('click', (event) => {
      if (!isIdentityMode()) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      identityLogin();
    }, true);
    password?.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' || !isIdentityMode()) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      identityLogin();
    }, true);

    userTab?.addEventListener('click', () => {
      resetMfaChallenge();
      syncIdentityModePresentation();
    });
    adminTab?.addEventListener('click', () => {
      resetMfaChallenge();
      syncIdentityModePresentation();
    });
    document.getElementById('lang-en')?.addEventListener('click', () => {
      syncMfaChallengeLanguage();
      syncIdentityModePresentation();
    });
    document.getElementById('lang-ar')?.addEventListener('click', () => {
      syncMfaChallengeLanguage();
      syncIdentityModePresentation();
    });

    syncIdentityModePresentation();
  }

  window.PMK_LOGIN_TOKEN_CAPTURE = {
    persistAuthPayload,
    normalizeToken,
    installFetchCapture,
    installIdentityMfaLogin,
    safeIdentityDestination,
    explicitSuperAdminMode,
  };
  installFetchCapture();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', installIdentityMfaLogin, { once: true });
  else installIdentityMfaLogin();
})();