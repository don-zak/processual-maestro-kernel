(function () {
  const HOST_ID = 'admin-evaluation-grants';
  const PANEL_ATTR = 'data-eval-launch-handoff-panel';
  const BASE = '/settings/admin/evaluation-grants';
  let observer = null;

  function text(value) {
    return String(value ?? '').trim();
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function authHeaders(extra = {}) {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') return auth.headers(extra);
    return new Headers(extra);
  }

  async function request(path, method = 'POST') {
    const response = await fetch(path, {
      method,
      credentials: 'include',
      headers: authHeaders({ Accept: 'application/json' }),
    });
    const raw = await response.text();
    let data = {};
    if (raw) {
      try { data = JSON.parse(raw); } catch { data = { message: raw }; }
    }
    if (!response.ok) {
      const detail = data?.detail || data?.message || `HTTP ${response.status}`;
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function grantIdFromCard(card) {
    const direct = text(card.dataset.evalGrantId);
    if (direct) return direct;
    const action = card.querySelector('[data-eval-issue], [data-eval-revoke]');
    const grantId = text(action?.dataset?.evalIssue || action?.dataset?.evalRevoke);
    if (grantId) return grantId;
    const muted = text(card.querySelector(':scope > .muted')?.textContent);
    const candidate = muted.split(' · ')[0];
    return /^eval_[A-Za-z0-9]+$/.test(candidate) ? candidate : '';
  }

  function isActiveGrantCard(card) {
    return Boolean(card.querySelector('[data-eval-issue]'));
  }

  function launchPanel(card, grantId) {
    let panel = card.querySelector(`[${PANEL_ATTR}]`);
    if (panel) return panel;
    panel = document.createElement('section');
    panel.setAttribute(PANEL_ATTR, 'true');
    panel.className = 'card flat';
    panel.style.marginTop = 'var(--s-3)';
    panel.innerHTML = `
      <div class="sec-hdr">
        <div class="sh-title">ZAXAM Workspace Launch</div>
        <div class="sh-sub">one-time browser handoff; execution still requires the separately delivered Evaluation API key</div>
      </div>
      <div class="admin-note">
        Issue this only after the Evaluation grant is active and the API key has been delivered through the approved secret channel. The launch link opens only through <strong>zaxam.net</strong>, expires in 30 minutes, creates a 2-hour workspace session, never grants production authority, and does not replace the API key.
      </div>
      <div style="margin-top:var(--s-2)">
        <button class="btn secondary" type="button" data-eval-launch-issue="${escapeHtml(grantId)}">Issue one-time ZAXAM launch</button>
      </div>
      <div data-eval-launch-result style="margin-top:var(--s-2)"></div>
    `;
    card.appendChild(panel);
    bindPanel(panel);
    return panel;
  }

  function renderIssued(result, payload) {
    const url = text(payload.handoff_url);
    const ticketSeconds = Number(payload.launch_ticket_expires_in_seconds || 0);
    const sessionSeconds = Number(payload.workspace_session_seconds || 0);
    if (!url) throw new Error('Launch handoff URL was not returned by the backend.');
    result.innerHTML = `
      <div class="admin-note ok">
        One-time launch issued. Send this URL separately from the Evaluation API key. Do not paste either credential into tickets, logs, chat, or shared documents.
      </div>
      <label style="display:block;margin-top:var(--s-2)">
        <span class="muted">ZAXAM one-time launch URL</span>
        <input data-eval-launch-url type="text" readonly value="${escapeHtml(url)}" style="width:100%" />
      </label>
      <div class="admin-actions" style="margin-top:var(--s-2)">
        <button class="btn secondary" type="button" data-eval-launch-copy>Copy launch URL</button>
        <button class="btn secondary" type="button" data-eval-launch-clear>Clear from screen</button>
      </div>
      <div class="muted" style="margin-top:var(--s-2)">launch TTL ${ticketSeconds || 1800}s · workspace session ${sessionSeconds || 7200}s · API key still required · production disabled</div>
    `;
    const input = result.querySelector('[data-eval-launch-url]');
    result.querySelector('[data-eval-launch-copy]')?.addEventListener('click', async (event) => {
      const button = event.currentTarget;
      try {
        await navigator.clipboard.writeText(input?.value || '');
        button.textContent = 'Copied';
        window.setTimeout(() => { button.textContent = 'Copy launch URL'; }, 1500);
      } catch {
        if (input) {
          input.focus();
          input.select();
        }
      }
    });
    result.querySelector('[data-eval-launch-clear]')?.addEventListener('click', () => {
      if (input) input.value = '';
      result.innerHTML = '<div class="muted">Launch URL cleared from this Admin screen. Issue a new one-time launch when another browser handoff is required.</div>';
    });
  }

  function bindPanel(panel) {
    const button = panel.querySelector('[data-eval-launch-issue]');
    if (!button || button.dataset.bound === 'true') return;
    button.dataset.bound = 'true';
    button.addEventListener('click', async () => {
      const grantId = text(button.dataset.evalLaunchIssue);
      const result = panel.querySelector('[data-eval-launch-result]');
      if (!grantId || !result) return;
      button.disabled = true;
      result.innerHTML = '<div class="muted">Issuing one-time ZAXAM launch…</div>';
      try {
        const payload = await request(`${BASE}/${encodeURIComponent(grantId)}/issue-launch`, 'POST');
        renderIssued(result, payload);
      } catch (error) {
        result.innerHTML = `<div class="admin-note danger">Unable to issue workspace launch: ${escapeHtml(error.message || error)}</div>`;
      } finally {
        button.disabled = false;
      }
    });
  }

  function decorate() {
    const host = document.getElementById(HOST_ID);
    if (!host) return;
    const list = host.querySelector('#admin-eval-list');
    if (!list) return;
    [...list.querySelectorAll(':scope > .card.flat')].forEach((card) => {
      const grantId = grantIdFromCard(card);
      if (!grantId || !isActiveGrantCard(card)) return;
      launchPanel(card, grantId);
    });
  }

  function initialize() {
    const host = document.getElementById(HOST_ID);
    if (!host) {
      window.setTimeout(initialize, 100);
      return;
    }
    if (!observer) {
      observer = new MutationObserver(() => decorate());
      observer.observe(host, { childList: true, subtree: true });
    }
    decorate();
    document.body.dataset.adminEvaluationLaunchHandoff = 'loaded';
  }

  window.PMK_ADMIN_EVALUATION_LAUNCH_HANDOFF = { initialize, decorate };
  initialize();
})();
