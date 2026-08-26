(() => {
  function escapeText(value) {
    return String(value || '').trim();
  }

  function install() {
    const panel = document.getElementById('lost-access-panel');
    if (!panel || panel.dataset.escalationWired === 'true') return;
    panel.dataset.escalationWired = 'true';

    const separator = document.createElement('div');
    separator.style.cssText = 'border-top:1px solid var(--rim);margin:1rem 0 .8rem';
    const button = document.createElement('button');
    button.id = 'login-contact-administrator-button';
    button.type = 'button';
    button.className = 'login-secondary-action';
    button.style.width = '100%';
    button.setAttribute('aria-expanded', 'false');
    button.textContent = 'Contact administrator';

    const host = document.createElement('div');
    host.id = 'login-recovery-escalation-host';
    host.hidden = true;
    host.innerHTML = `
      <form id="login-recovery-escalation-form" class="pmk-recovery-form" novalidate>
        <div class="inp-hint">Use this only if you cannot access the verified recovery address. The request opens a supervisor review; it never resets a password or bypasses MFA.</div>
        <input id="login-escalation-account" class="inp" type="email" autocomplete="username" maxlength="320" placeholder="Account email" required>
        <input id="login-escalation-contact" class="inp" type="email" autocomplete="email" maxlength="320" placeholder="Safe contact email" required>
        <input id="login-escalation-organization" class="inp" type="text" maxlength="160" placeholder="Organization reference (optional)">
        <select id="login-escalation-reason" class="inp" required>
          <option value="lost_recovery_email">Lost access to recovery email</option>
          <option value="lost_authenticator">Lost authenticator device</option>
          <option value="recovery_codes_unavailable">Recovery codes unavailable</option>
          <option value="account_locked">Account locked</option>
          <option value="other">Other identity-recovery issue</option>
        </select>
        <button id="login-escalation-submit" class="btn primary" type="submit">Request administrator review</button>
        <div id="login-escalation-status" class="pmk-recovery-note" role="status" aria-live="polite">Do not enter passwords, MFA codes, recovery codes, API keys, or other secrets.</div>
      </form>`;

    panel.appendChild(separator);
    panel.appendChild(button);
    panel.appendChild(host);

    button.addEventListener('click', () => {
      const opening = host.hidden;
      host.hidden = !opening;
      button.setAttribute('aria-expanded', opening ? 'true' : 'false');
      if (opening) {
        const account = document.getElementById('login-escalation-account');
        const username = document.getElementById('login-username');
        const recovery = document.getElementById('login-recovery-identifier');
        if (account && !account.value) account.value = escapeText(recovery?.value || username?.value);
        window.setTimeout(() => account?.focus({preventScroll:true}), 0);
      }
    });

    const form = document.getElementById('login-recovery-escalation-form');
    form?.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const submit = document.getElementById('login-escalation-submit');
      const status = document.getElementById('login-escalation-status');
      const payload = {
        claimed_login: escapeText(document.getElementById('login-escalation-account')?.value),
        contact_email: escapeText(document.getElementById('login-escalation-contact')?.value),
        organization_ref: escapeText(document.getElementById('login-escalation-organization')?.value) || null,
        reason: escapeText(document.getElementById('login-escalation-reason')?.value),
      };
      submit.disabled = true;
      status.textContent = 'Submitting administrator review request…';
      try {
        const response = await fetch('/auth/account-recovery/escalations', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {'Content-Type':'application/json','Accept':'application/json'},
          body: JSON.stringify(payload),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || result.authority_granted !== false) {
          throw new Error(result.detail || 'Administrator review request is unavailable.');
        }
        status.textContent = `Recovery review request ${result.request_id} was queued. An administrator must review identity evidence. This request grants no account authority.`;
        form.reset();
      } catch (error) {
        status.textContent = error?.message || 'Administrator review request is unavailable.';
      } finally {
        submit.disabled = false;
      }
    });
  }

  function waitForRecoveryPanel() {
    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      const panel = document.getElementById('lost-access-panel');
      if (panel && panel.dataset.recoveryWired === 'true') {
        window.clearInterval(timer);
        install();
      } else if (attempts >= 40) {
        window.clearInterval(timer);
        install();
      }
    }, 50);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', waitForRecoveryPanel, {once:true});
  } else {
    waitForRecoveryPanel();
  }
})();
