(() => {
  const PAGE_ID = 'page-admin-api-keys';
  const CARD_ID = 'admin-account-recovery-escalations-card';
  const LIST_ID = 'admin-account-recovery-escalations-list';

  function authHeaders(extra = {}) {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') return { ...auth.headers(), ...extra };
    const token =
      localStorage.getItem('access_token') ||
      localStorage.getItem('auth_token') ||
      localStorage.getItem('admin_token') ||
      sessionStorage.getItem('access_token') ||
      sessionStorage.getItem('auth_token') ||
      sessionStorage.getItem('admin_token');
    return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra };
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function ensureCard() {
    if (document.getElementById(CARD_ID)) return document.getElementById(CARD_ID);
    const page = document.getElementById(PAGE_ID);
    if (!page) return null;
    const card = document.createElement('section');
    card.id = CARD_ID;
    card.className = 'admin-card';
    card.dataset.accountRecoveryEscalations = 'true';
    card.innerHTML = `
      <div class="admin-card-header">
        <div>
          <h3>Account Recovery Requests</h3>
          <p>Platform-admin review queue for customers who cannot use their verified recovery channel.</p>
        </div>
        <button id="admin-account-recovery-refresh" class="btn ghost sm" type="button">Refresh</button>
      </div>
      <div class="admin-card-body">
        <p class="admin-help-text">Recent platform-admin MFA step-up is required. Approval changes only the governed recovery channel and sends verification to the safe contact. It never resets a password, reveals an MFA secret, bypasses MFA, creates a session, or grants account authority.</p>
        <div id="${LIST_ID}" data-state="idle">Load pending requests after completing platform-admin MFA step-up.</div>
      </div>`;
    page.appendChild(card);
    document.getElementById('admin-account-recovery-refresh')?.addEventListener('click', refresh);
    return card;
  }

  async function api(method, path, payload) {
    const response = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers: authHeaders({ 'Content-Type': 'application/json', Accept: 'application/json' }),
      ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    return data;
  }

  function render(payload) {
    const host = document.getElementById(LIST_ID);
    if (!host) return;
    const requests = Array.isArray(payload?.requests) ? payload.requests : [];
    if (!requests.length) {
      host.dataset.state = 'empty';
      host.innerHTML = '<p class="admin-help-text">No pending account-recovery escalation requests.</p>';
      return;
    }
    host.dataset.state = 'ready';
    host.innerHTML = requests.map((item) => `
      <article class="admin-card" data-recovery-escalation-id="${escapeHtml(item.id)}" style="margin-top:.75rem">
        <div class="admin-card-body">
          <div><strong>Claimed account:</strong> ${escapeHtml(item.claimed_login)}</div>
          <div><strong>Proposed recovery contact:</strong> ${escapeHtml(item.contact_email)}</div>
          <div><strong>Organization:</strong> ${escapeHtml(item.organization_ref || 'Not supplied')}</div>
          <div><strong>Reason:</strong> ${escapeHtml(item.reason)}</div>
          <div><strong>Created:</strong> ${escapeHtml(item.created_at)}</div>
          <p class="admin-help-text" style="margin-top:.6rem">Approve only after identity evidence has been reviewed through the established support procedure. Approval sends a verification message to the proposed recovery contact. The customer must verify it, restart Lost Access, change the password, and complete MFA.</p>
          <div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.75rem">
            <button class="btn ghost sm" type="button" data-recovery-action="approve-channel" data-request-id="${escapeHtml(item.id)}">Approve recovery channel &amp; send verification</button>
            <button class="btn ghost sm" type="button" data-recovery-action="reject" data-request-id="${escapeHtml(item.id)}">Reject: insufficient evidence</button>
          </div>
        </div>
      </article>`).join('');
    host.querySelectorAll('[data-recovery-action]').forEach((button) => {
      button.addEventListener('click', () => decide(button));
    });
  }

  async function decide(button) {
    const requestId = button.dataset.requestId;
    const action = button.dataset.recoveryAction;
    if (!requestId || !action) return;
    button.disabled = true;
    try {
      const result = action === 'approve-channel'
        ? await api('POST', `/auth/account-recovery/escalations/${encodeURIComponent(requestId)}/approve-recovery-channel`)
        : await api(
            'POST',
            `/auth/account-recovery/escalations/${encodeURIComponent(requestId)}/decision`,
            { state: 'rejected', resolution: 'identity_evidence_insufficient' },
          );
      if (
        result.authority_granted !== false ||
        result.password_reset_performed !== false ||
        result.mfa_bypassed !== false ||
        result.session_created === true
      ) {
        throw new Error('Recovery escalation returned an unsafe authority result.');
      }
      if (action === 'approve-channel' && result.next_action !== 'verify_recovery_email_then_restart_recovery') {
        throw new Error('Recovery channel approval returned an invalid next action.');
      }
      await refresh();
    } catch (error) {
      const host = document.getElementById(LIST_ID);
      if (host) {
        host.dataset.state = 'error';
        host.textContent = error?.message || 'Account recovery review is unavailable.';
      }
    } finally {
      button.disabled = false;
    }
  }

  async function refresh() {
    ensureCard();
    const host = document.getElementById(LIST_ID);
    if (!host) return;
    host.dataset.state = 'loading';
    host.textContent = 'Loading pending account recovery requests…';
    try {
      const payload = await api('GET', '/auth/account-recovery/escalations?state=pending');
      if (payload.authority_granted !== false) throw new Error('Unsafe recovery escalation authority response.');
      render(payload);
    } catch (error) {
      host.dataset.state = 'error';
      host.textContent = `${error?.message || 'Account recovery review is unavailable.'} Recent platform-admin MFA step-up is required.`;
    }
  }

  function initialize() {
    const card = ensureCard();
    if (!card) return;
    refresh();
  }

  window.PMK_ADMIN_ACCOUNT_RECOVERY_ESCALATIONS = { initialize, refresh };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => window.setTimeout(initialize, 0), { once: true });
  } else {
    window.setTimeout(initialize, 0);
  }
})();
