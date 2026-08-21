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

  function installViewportSafeLoginLayout() {
    if (document.getElementById('pmk-login-viewport-safety')) return;
    const style = document.createElement('style');
    style.id = 'pmk-login-viewport-safety';
    style.textContent = `
      html,body{min-height:100%;}
      body{overflow-x:hidden!important;overflow-y:auto!important;}
      .login-wrap{margin:auto;}
      .pmk-recovery-form{display:grid;gap:.65rem;margin-top:.8rem;}
      .pmk-recovery-form .inp{font-size:11px;}
      .pmk-recovery-note{font:9px var(--font-data);color:var(--muted);line-height:1.5;}
      .pmk-mfa-enrollment{display:grid;gap:.75rem;}
      .pmk-mfa-secret{overflow-wrap:anywhere;padding:.7rem;border:1px solid var(--rim);border-radius:8px;background:rgba(17,22,32,.7);font:10px var(--font-data);color:var(--soft);}
      .pmk-recovery-codes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.4rem;padding:.7rem;border:1px solid var(--rim);border-radius:8px;background:rgba(17,22,32,.7);font:9px var(--font-data);}
      @media (max-height:900px){body{align-items:flex-start!important;}.login-wrap{margin:0 auto;padding-top:24px;padding-bottom:32px;}}
      @media (max-width:520px){.login-wrap{padding-left:14px;padding-right:14px;}.card{padding-left:20px;padding-right:20px;}.pmk-recovery-codes{grid-template-columns:1fr;}}
    `;
    document.head.appendChild(style);
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

  function installLostAccessRecovery() {
    const panel = document.getElementById('lost-access-panel');
    if (!panel || panel.dataset.recoveryWired === 'true') return;
    panel.dataset.recoveryWired = 'true';
    panel.innerHTML = `
      <p class="login-gateway-panel-title">Recover account access</p>
      <p class="login-gateway-panel-copy">Enter your account email. If the account has a verified recovery address, secure instructions will be sent there. The response never reveals whether an account exists.</p>
      <form id="login-recovery-form" class="pmk-recovery-form" novalidate>
        <input id="login-recovery-identifier" class="inp" type="email" autocomplete="email" placeholder="account@example.com" maxlength="320" required>
        <button id="login-recovery-submit" class="btn primary" type="submit">Send recovery instructions</button>
        <div id="login-recovery-status" class="pmk-recovery-note" role="status" aria-live="polite">No session, password, MFA secret, or account authority will be exposed here.</div>
      </form>
      <p class="login-gateway-panel-copy">Cannot access the verified recovery address? Use your organization's established support channel and ask the administrator or platform supervisor to open an identity-recovery escalation. Do not send passwords, MFA codes, recovery codes, or API keys.</p>`;
    const form = document.getElementById('login-recovery-form');
    const input = document.getElementById('login-recovery-identifier');
    const submit = document.getElementById('login-recovery-submit');
    const recoveryStatus = document.getElementById('login-recovery-status');
    const username = document.getElementById('login-username');
    document.getElementById('login-lost-access-button')?.addEventListener('click', () => {
      if (input && username?.value && !input.value) input.value = username.value.trim();
      window.setTimeout(() => input?.focus({ preventScroll: true }), 0);
    });
    form?.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      submit.disabled = true;
      recoveryStatus.textContent = 'Submitting secure recovery request…';
      try {
        const response = await fetch('/auth/account-recovery/start', {
          method:'POST', credentials:'same-origin',
          headers:{'Content-Type':'application/json','Accept':'application/json'},
          body:JSON.stringify({login:input.value.trim()}),
        });
        if (response.status === 429) throw new Error('Too many recovery requests. Try again later.');
        if (!response.ok) throw new Error('Recovery service is temporarily unavailable.');
        recoveryStatus.textContent = 'If the account is eligible, recovery instructions have been sent to its verified recovery address.';
        input.value = '';
      } catch (error) {
        recoveryStatus.textContent = error?.message || 'Recovery service is temporarily unavailable.';
      } finally {
        submit.disabled = false;
      }
    });
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

  function buildMfaEnrollment() {
    if (document.getElementById('identity-mfa-enrollment')) return;
    const loginButton = document.getElementById('login-btn');
    if (!loginButton) return;
    const enrollment = document.createElement('div');
    enrollment.id = 'identity-mfa-enrollment';
    enrollment.hidden = true;
    enrollment.className = 'pmk-mfa-enrollment';
    loginButton.insertAdjacentElement('beforebegin', enrollment);
  }

  function showMfaChallenge() {
    buildMfaChallenge();
    buildMfaEnrollment();
    const enrollment = document.getElementById('identity-mfa-enrollment');
    if (enrollment) enrollment.hidden = true;
    const challenge = document.getElementById('identity-mfa-challenge');
    if (challenge) challenge.hidden = false;
    setMfaLayout(true);
    syncMfaChallengeLanguage();
    document.getElementById('identity-mfa-code')?.focus({ preventScroll: true });
  }

  async function refreshAfterMfa() {
    const refreshed = await fetch('/auth/session/refresh', {
      method:'POST', credentials:'same-origin', headers:{'X-CSRF-Token':pendingCsrfToken},
    });
    const data = await refreshed.json().catch(() => ({}));
    if (!refreshed.ok || data.mfa_required === true) throw new Error(data.detail || 'Unable to complete MFA login.');
    const token = normalizeToken(data.access_token);
    if (!token) throw new Error('MFA completion did not return a valid token.');
    persistUserSession(token);
    pendingMfaToken = '';
    pendingCsrfToken = '';
    window.location.href = '/console';
  }

  async function showMfaEnrollment() {
    buildMfaChallenge();
    buildMfaEnrollment();
    const challenge = document.getElementById('identity-mfa-challenge');
    if (challenge) challenge.hidden = true;
    const enrollment = document.getElementById('identity-mfa-enrollment');
    if (!enrollment) return;
    setMfaLayout(true);
    enrollment.hidden = false;
    enrollment.innerHTML = '<div class="inp-hint">MFA enrollment is required before normal access can resume.</div><div class="pmk-mfa-secret">Preparing authenticator enrollment…</div>';
    try {
      const response = await fetch('/auth/mfa/totp/enroll', {
        method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json','Authorization':`Bearer ${pendingMfaToken}`},
        body:JSON.stringify({label:'Primary authenticator'}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.secret || !data.provisioning_uri) throw new Error(data.detail || 'MFA enrollment is unavailable.');
      enrollment.innerHTML = `
        <div class="inp-hint">Add this account to your authenticator app. The secret is shown only for this enrollment response.</div>
        <div class="pmk-mfa-secret"><strong>Manual secret</strong><br>${String(data.secret).replace(/[<>&]/g,'')}</div>
        <div class="pmk-mfa-secret"><strong>Provisioning URI</strong><br>${String(data.provisioning_uri).replace(/[<>&]/g,'')}</div>
        <div class="inp-group"><label class="inp-label" for="identity-mfa-enroll-code">Authenticator code</label><input id="identity-mfa-enroll-code" class="inp" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="123456"></div>
        <button id="identity-mfa-enroll-confirm" class="btn primary" type="button">Confirm MFA</button>`;
      document.getElementById('identity-mfa-enroll-confirm')?.addEventListener('click', confirmMfaEnrollment);
      document.getElementById('identity-mfa-enroll-code')?.focus({preventScroll:true});
    } catch (error) {
      enrollment.innerHTML = `<div class="inp-hint">${String(error?.message || 'MFA enrollment is unavailable.')}</div>`;
    }
  }

  async function confirmMfaEnrollment() {
    const input = document.getElementById('identity-mfa-enroll-code');
    const button = document.getElementById('identity-mfa-enroll-confirm');
    const code = input?.value?.trim() || '';
    if (!/^\d{6}$/.test(code)) { showError('Enter the six-digit authenticator code.'); return; }
    clearError();
    if (button) { button.disabled = true; button.textContent = 'Confirming…'; }
    try {
      const response = await fetch('/auth/mfa/totp/confirm', {
        method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json','Authorization':`Bearer ${pendingMfaToken}`},
        body:JSON.stringify({code}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !Array.isArray(data.recovery_codes)) throw new Error(data.detail || 'MFA confirmation failed.');
      const enrollment = document.getElementById('identity-mfa-enrollment');
      if (!enrollment) return;
      const codes = data.recovery_codes.map((item) => `<span>${String(item).replace(/[<>&]/g,'')}</span>`).join('');
      enrollment.innerHTML = `<div class="inp-hint"><strong>Save these recovery codes now.</strong> They are returned once and are required if you lose your authenticator.</div><div class="pmk-recovery-codes">${codes}</div><button id="identity-mfa-enroll-continue" class="btn primary" type="button">I saved the codes — Continue</button>`;
      document.getElementById('identity-mfa-enroll-continue')?.addEventListener('click', async () => {
        const continueButton = document.getElementById('identity-mfa-enroll-continue');
        if (continueButton) { continueButton.disabled = true; continueButton.textContent = 'Completing sign in…'; }
        try { await refreshAfterMfa(); } catch (error) { showError(error?.message || 'Unable to complete MFA login.'); if (continueButton) { continueButton.disabled = false; continueButton.textContent = 'I saved the codes — Continue'; } }
      });
    } catch (error) {
      showError(error?.message || 'MFA confirmation failed.');
      if (button) { button.disabled = false; button.textContent = 'Confirm MFA'; }
    }
  }

  async function startMfaFlow() {
    try {
      const response = await fetch('/auth/mfa/status', {credentials:'same-origin',headers:{'Authorization':`Bearer ${pendingMfaToken}`,'Accept':'application/json'}});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'MFA status is unavailable.');
      if (data.enabled === true) showMfaChallenge();
      else await showMfaEnrollment();
    } catch (error) {
      showError(error?.message || 'MFA status is unavailable.');
    }
  }

  function resetMfaChallenge() {
    pendingMfaToken = '';
    pendingCsrfToken = '';
    recoveryMode = false;
    const challenge = document.getElementById('identity-mfa-challenge');
    if (challenge) challenge.hidden = true;
    const enrollment = document.getElementById('identity-mfa-enrollment');
    if (enrollment) { enrollment.hidden = true; enrollment.innerHTML = ''; }
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
      const response = await fetch('/auth/login', { method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email,password}) });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Invalid credentials');
      if (data.mfa_required === true) {
        pendingMfaToken = normalizeToken(data.access_token);
        pendingCsrfToken = String(data.csrf_token || '');
        if (!pendingMfaToken || !pendingCsrfToken) throw new Error('MFA session could not be established.');
        clearRestrictedTokenCopies();
        await startMfaFlow();
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
      const verification = await fetch('/auth/mfa/verify', { method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json',Authorization:`Bearer ${pendingMfaToken}`}, body:JSON.stringify(recoveryMode ? {recovery_code:credential} : {code:credential}) });
      const verificationData = await verification.json().catch(() => ({}));
      if (!verification.ok) throw new Error(verificationData.detail || 'Invalid MFA credential.');
      await refreshAfterMfa();
    } catch (error) { showError(error?.message || 'MFA verification failed'); }
    finally { if (button) { button.disabled = false; button.textContent = 'Verify'; } }
  }

  function installIdentityMfaLogin() {
    lockLoginToEnglish();
    installViewportSafeLoginLayout();
    buildMfaChallenge();
    buildMfaEnrollment();
    installPasswordVisibilityControl();
    installLostAccessRecovery();
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

  window.PMK_LOGIN_TOKEN_CAPTURE = {
    persistAuthPayload,
    normalizeToken,
    installFetchCapture,
    installIdentityMfaLogin,
    installPasswordVisibilityControl,
    installViewportSafeLoginLayout,
    installLostAccessRecovery,
    startMfaFlow,
  };
  installFetchCapture();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', installIdentityMfaLogin, { once:true });
  else installIdentityMfaLogin();
})();
