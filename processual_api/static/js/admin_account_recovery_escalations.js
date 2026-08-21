(() => {
  const PAGE_ID = 'page-admin-api-keys';
  const CARD_ID = 'admin-account-recovery-escalations-card';
  const LIST_ID = 'admin-account-recovery-escalations-list';

  function authHeaders(extra = {}) {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') {
      return { ...auth.headers(), ...extra };
    }
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
          <p>Supervisor review queue for people who cannot use their verified recovery channel.</p>
        </div>
        <button id="admin-account-recovery-refresh" class="btn ghost sm" type="button">Refresh</button>
      </div>
      <div class="admin-card-body">
        <p class="admin-help-text">Review only. These controls never reset a password, reveal an MFA secret, bypass MFA, create a session, or grant account authority. After identity evidence is reviewed, the user must return to the normal recovery and MFA flow.</p>
        <div id="${LIST_ID}" data-state="idle">Open this card after a recent platform-admin MFA step-up to load pending requests.</div>
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
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }
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
          <div><strong>Safe contact:</strong> ${escapeHtml(item.contact_email)}</div>
          <div><strong>Organization:</strong> ${escapeHtml(item.organization_ref || 'Not supplied')}</div>
          <div><strong>Reason:</strong> ${escapeHtml(item.reason)}</div>
          <div><strong>Created:</strong> ${escapeHtml(item.created_at)}</div>
          <div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.75rem">
            <button class="btn ghost sm" type="button" data-recovery-decision="reviewed" data-request-id="${escapeHtml(item.id)}">Identity/recovery channel reviewed</button>
            <button class="btn ghost sm" type="button" data-recovery-decision="reject" data-request-id="${escapeHtml(item.id)}">Reject: insufficient evidence</button>
          </div>
        </div>
      </article>`).join('');
    host.querySelectorAll('[data-recovery-decision]').forEach((button) => {
      button.addEventListener('click', () => decide(button));
    });
  }

  async function decide(button) {
    const requestId = button.dataset.requestId;
    const action = button.dataset.recoveryDecision;
    if (!requestId || !action) return;
    button.disabled = true;
    try {
      const result = await api(
        'POST',
        `/auth/account-recovery/escalations/${encodeURIComponent(requestId)}/decision`,
        action === 'reviewed'
          ? { state: 'resolved', resolution: 'recovery_channel_reviewed' }
          : { state: 'rejected', resolution: 'identity_evidence_insufficient' },
      );
      if (result.authority_granted !== false || result.password_reset_performed !== false || result.mfa_bypassed !== false) {
        throw new Error('Recovery escalation returned an unsafe authority result.');
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
