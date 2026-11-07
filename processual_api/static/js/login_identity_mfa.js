(function () {
  'use strict';

  let pendingMfaToken = '';
  let pendingCsrfToken = '';
  let pendingEntryMode = 'user';
  let recoveryMode = false;

  function firstTokenFromObject(value) {
    if (!value || typeof value !== 'object') return '';
    return (
      value.access_token || value.accessToken || value.token ||
      value?.data?.access_token || value?.data?.accessToken || value?.data?.token ||
      value?.session?.access_token || value?.session?.accessToken || value?.session?.token || ''
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

  function clearRestrictedTokenCopies() {
    [
      'access_token', 'auth_token', 'maestro_auth_token', 'processual_auth_token',
      'processual_session', 'admin_access_token', 'admin_token', 'admin_session',
      'maestro_token', 'maestro_role'
    ].forEach((key) => {
      try { localStorage.removeItem(key); } catch (error) {}
      try { sessionStorage.removeItem(key); } catch (error) {}
    });
  }

  function persistIdentitySession(token, entryMode) {
    clearRestrictedTokenCopies();
    sessionStorage.setItem('maestro_token', token);
    sessionStorage.setItem('maestro_role', entryMode === 'admin' ? 'admin' : 'user');
    sessionStorage.setItem('maestro_ui_session_started_at', new Date().toISOString());
  }

  const isUserMode = () => document.getElementById('tab-user')?.classList.contains('active') === true;
  const currentEntryMode = () => isUserMode() ? 'user' : 'admin';

  function showError(text) {
    const error = document.getElementById('login-error');
    if (!error) return;
    error.textContent = text;
    error.style.display = 'block';
  }

  function clearError() {
    const error = document.getElementById('login-error');
    if (error) {
      error.textContent = '';
      error.style.display = 'none';
    }
  }

  function authorizationHeaders(extra) {
    return { ...(extra || {}), Authorization: `Bearer ${pendingMfaToken}` };
  }

  function syncMfaChallengeCopy() {
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
      syncMfaChallengeCopy();
      const input = document.getElementById('identity-mfa-code');
      if (input) {
        input.value = '';
        input.focus();
      }
    });
    document.getElementById('identity-mfa-code')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') verifyMfaChallenge();
    });
    syncMfaChallengeCopy();
  }

  function buildMfaEnrollment() {
    if (document.getElementById('identity-mfa-enrollment')) return;
    const loginButton = document.getElementById('login-btn');
    if (!loginButton) return;
    const panel = document.createElement('div');
    panel.id = 'identity-mfa-enrollment';
    panel.hidden = true;
    panel.innerHTML = '<div class="inp-group"><label class="inp-label">Set up authenticator</label><div class="inp-hint">Add the account to your authenticator using the provisioning URI or secret below. These values are shown only for setup and are not stored by this page.</div></div><div class="inp-group"><label class="inp-label" for="identity-mfa-provisioning-uri">Provisioning URI</label><textarea id="identity-mfa-provisioning-uri" class="inp" rows="3" readonly spellcheck="false"></textarea></div><div class="inp-group"><label class="inp-label" for="identity-mfa-secret">Secret</label><input id="identity-mfa-secret" class="inp" type="text" readonly autocomplete="off" spellcheck="false"></div><div class="inp-group"><label class="inp-label" for="identity-mfa-enrollment-code">Authenticator code</label><input id="identity-mfa-enrollment-code" class="inp" inputmode="numeric" autocomplete="one-time-code" maxlength="8" placeholder="123456"><div class="inp-hint">Enter a current code to confirm enrollment.</div></div><button id="identity-mfa-enrollment-confirm" class="btn primary" type="button">Confirm MFA</button>';
    loginButton.insertAdjacentElement('beforebegin', panel);
    document.getElementById('identity-mfa-enrollment-confirm')?.addEventListener('click', confirmMfaEnrollment);
    document.getElementById('identity-mfa-enrollment-code')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') confirmMfaEnrollment();
    });
  }

  function buildRecoveryCodesPanel() {
    if (document.getElementById('identity-mfa-recovery-codes')) return;
    const loginButton = document.getElementById('login-btn');
    if (!loginButton) return;
    const panel = document.createElement('div');
    panel.id = 'identity-mfa-recovery-codes';
    panel.hidden = true;
    panel.innerHTML = '<div class="inp-group"><label class="inp-label">Recovery codes</label><div class="inp-hint">Save these one-time recovery codes now. Maestro does not store a readable copy for later display.</div><pre id="identity-mfa-recovery-code-list" class="inp" style="white-space:pre-wrap;user-select:text"></pre></div><button id="identity-mfa-recovery-continue" class="btn primary" type="button">I saved the codes - Continue</button>';
    loginButton.insertAdjacentElement('beforebegin', panel);
    document.getElementById('identity-mfa-recovery-continue')?.addEventListener('click', completeMfaSession);
  }

  function hideBaseLoginForMfa() {
    const fields = document.getElementById('login-fields');
    const loginButton = document.getElementById('login-btn');
    const tabs = document.querySelector('.tab-row');
    if (fields) fields.hidden = true;
    if (loginButton) loginButton.hidden = true;
    if (tabs) tabs.hidden = true;
  }

  function showOnlyMfaPanel(panelId) {
    hideBaseLoginForMfa();
    ['identity-mfa-challenge', 'identity-mfa-enrollment', 'identity-mfa-recovery-codes'].forEach((id) => {
      const panel = document.getElementById(id);
      if (panel) panel.hidden = id !== panelId;
    });
  }

  function showMfaChallenge() {
    buildMfaChallenge();
    buildMfaEnrollment();
    buildRecoveryCodesPanel();
    showOnlyMfaPanel('identity-mfa-challenge');
    syncMfaChallengeCopy();
    document.getElementById('identity-mfa-code')?.focus();
  }

  function resetMfaChallenge() {
    pendingMfaToken = '';
    pendingCsrfToken = '';
    pendingEntryMode = currentEntryMode();
    recoveryMode = false;
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
    const enrollmentCode = document.getElementById('identity-mfa-enrollment-code');
    const secret = document.getElementById('identity-mfa-secret');
    const uri = document.getElementById('identity-mfa-provisioning-uri');
    const recoveryCodes = document.getElementById('identity-mfa-recovery-code-list');
    if (code) code.value = '';
    if (enrollmentCode) enrollmentCode.value = '';
    if (secret) secret.value = '';
    if (uri) uri.value = '';
    if (recoveryCodes) recoveryCodes.textContent = '';
  }

  async function startMfaEnrollment() {
    buildMfaEnrollment();
    buildRecoveryCodesPanel();
    const response = await fetch('/auth/mfa/totp/enroll', {
      method: 'POST',
      credentials: 'same-origin',
      headers: authorizationHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ label: pendingEntryMode === 'admin' ? 'Maestro Platform Admin' : 'Maestro Authenticator' }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'MFA enrollment could not be started.');
    const secret = document.getElementById('identity-mfa-secret');
    const uri = document.getElementById('identity-mfa-provisioning-uri');
    if (secret) secret.value = String(data.secret || '');
    if (uri) uri.value = String(data.provisioning_uri || '');
    if (!secret?.value || !uri?.value) throw new Error('MFA enrollment material is unavailable.');
    showOnlyMfaPanel('identity-mfa-enrollment');
    document.getElementById('identity-mfa-enrollment-code')?.focus();
  }

  async function prepareMfaFlow() {
    const response = await fetch('/auth/mfa/status', {
      method: 'GET',
      credentials: 'same-origin',
      headers: authorizationHeaders(),
    });
    const status = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(status.detail || 'MFA status is unavailable.');
    if (status.enabled === true) {
      showMfaChallenge();
      return;
    }
    if (status.pending_enrollment === true) {
      throw new Error('MFA enrollment is already pending. Complete it with the authenticator setup previously shown, or use the approved recovery process.');
    }
    await startMfaEnrollment();
  }

  async function identityLogin() {
    const email = document.getElementById('login-username')?.value?.trim() || '';
    const password = document.getElementById('login-password')?.value || '';
    const button = document.getElementById('login-btn');
    if (!email || !password) {
      showError('Enter email and password');
      return;
    }
    pendingEntryMode = currentEntryMode();
    clearError();
    if (button) {
      button.disabled = true;
      button.textContent = 'Signing in...';
    }
    try {
      const response = await fetch('/auth/login', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Invalid credentials');
      if (data.mfa_required === true) {
        pendingMfaToken = normalizeToken(data.access_token);
        pendingCsrfToken = String(data.csrf_token || '');
        if (!pendingMfaToken || !pendingCsrfToken) throw new Error('MFA session could not be established.');
        clearRestrictedTokenCopies();
        await prepareMfaFlow();
        return;
      }
      const token = normalizeToken(data.access_token);
      if (!token) throw new Error('Login response did not contain a valid token.');
      persistIdentitySession(token, pendingEntryMode);
      window.location.href = pendingEntryMode === 'admin' ? '/admin' : '/console';
    } catch (error) {
      showError(error?.message || 'Login failed');
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = 'Sign In';
      }
    }
  }

  async function completeMfaSession() {
    const refreshed = await fetch('/auth/session/refresh', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRF-Token': pendingCsrfToken },
    });
    const refreshedData = await refreshed.json().catch(() => ({}));
    if (!refreshed.ok) throw new Error(refreshedData.detail || 'Unable to complete MFA login.');
    if (refreshedData.mfa_required === true) throw new Error('MFA verification is still required.');
    const token = normalizeToken(refreshedData.access_token);
    if (!token) throw new Error('MFA completion did not return a valid token.');
    persistIdentitySession(token, pendingEntryMode);
    pendingMfaToken = '';
    pendingCsrfToken = '';
    window.location.href = pendingEntryMode === 'admin' ? '/admin' : '/console';
  }

  async function confirmMfaEnrollment() {
    const input = document.getElementById('identity-mfa-enrollment-code');
    const button = document.getElementById('identity-mfa-enrollment-confirm');
    const code = input?.value?.trim() || '';
    if (!code || !pendingMfaToken || !pendingCsrfToken) {
      showError('Enter the authenticator code to confirm MFA.');
      return;
    }
    clearError();
    if (button) {
      button.disabled = true;
      button.textContent = 'Confirming...';
    }
    try {
      const response = await fetch('/auth/mfa/totp/confirm', {
        method: 'POST',
        credentials: 'same-origin',
        headers: authorizationHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ code }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Invalid MFA credential.');
      const codes = Array.isArray(data.recovery_codes) ? data.recovery_codes : [];
      if (!codes.length) throw new Error('Recovery codes were not returned.');
      buildRecoveryCodesPanel();
      const list = document.getElementById('identity-mfa-recovery-code-list');
      if (list) list.textContent = codes.join('\n');
      const secret = document.getElementById('identity-mfa-secret');
      const uri = document.getElementById('identity-mfa-provisioning-uri');
      if (secret) secret.value = '';
      if (uri) uri.value = '';
      showOnlyMfaPanel('identity-mfa-recovery-codes');
      document.getElementById('identity-mfa-recovery-continue')?.focus();
    } catch (error) {
      showError(error?.message || 'MFA enrollment confirmation failed');
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = 'Confirm MFA';
      }
    }
  }

  async function verifyMfaChallenge() {
    const input = document.getElementById('identity-mfa-code');
    const button = document.getElementById('identity-mfa-verify');
    const credential = input?.value?.trim() || '';
    if (!credential || !pendingMfaToken || !pendingCsrfToken) {
      showError('Enter your MFA credential.');
      return;
    }
    clearError();
    if (button) {
      button.disabled = true;
      button.textContent = 'Verifying...';
    }
    try {
      const verification = await fetch('/auth/mfa/verify', {
        method: 'POST',
        credentials: 'same-origin',
        headers: authorizationHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(recoveryMode ? { recovery_code: credential } : { code: credential }),
      });
      const verificationData = await verification.json().catch(() => ({}));
      if (!verification.ok) throw new Error(verificationData.detail || 'Invalid MFA credential.');
      await completeMfaSession();
    } catch (error) {
      showError(error?.message || 'MFA verification failed');
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = 'Verify';
      }
    }
  }

  function installIdentityMfaLogin() {
    buildMfaChallenge();
    buildMfaEnrollment();
    buildRecoveryCodesPanel();
    const loginButton = document.getElementById('login-btn');
    const password = document.getElementById('login-password');
    const userTab = document.getElementById('tab-user');
    const adminTab = document.getElementById('tab-admin');
    const username = document.getElementById('login-username');
    loginButton?.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      identityLogin();
    }, true);
    password?.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      event.stopImmediatePropagation();
      identityLogin();
    }, true);
    userTab?.addEventListener('click', () => {
      resetMfaChallenge();
      if (username) username.placeholder = 'email@example.com';
    });
    adminTab?.addEventListener('click', () => {
      resetMfaChallenge();
      if (username) username.placeholder = 'admin@example.com';
    });
    if (username) {
      username.placeholder = currentEntryMode() === 'admin' ? 'admin@example.com' : 'email@example.com';
    }
  }

  window.PMK_LOGIN_IDENTITY = { normalizeToken, installIdentityMfaLogin };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', installIdentityMfaLogin, { once: true });
  } else {
    installIdentityMfaLogin();
  }
})();
