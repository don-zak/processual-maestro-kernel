(function () {
  const ROOT_ID = 'admin-evaluation-grants';
  const GRANTS_ENDPOINT = '/settings/admin/evaluation-grants';

  function text(value) { return String(value ?? '').trim(); }

  function authHeaders(extra = {}) {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') return auth.headers(extra);
    return new Headers(extra);
  }

  async function request(path, method = 'GET') {
    const response = await fetch(path, {
      method,
      credentials: 'include',
      cache: 'no-store',
      headers: authHeaders({ Accept: 'application/json' }),
    });
    const raw = await response.text();
    let data = {};
    if (raw) {
      try { data = JSON.parse(raw); } catch { data = { detail: raw }; }
    }
    if (!response.ok) {
      const detail = data?.detail || data?.message || `HTTP ${response.status}`;
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function resultTarget() {
    return document.getElementById('admin-eval-result');
  }

  function setResult(message, danger = false) {
    const target = resultTarget();
    if (!target) return;
    target.className = danger ? 'admin-note danger' : 'admin-note ok';
    target.textContent = message;
  }

  function ensureDeleteButton(card) {
    if (!card || card.querySelector('[data-eval-archive]')) return;
    const grantId = text(card.dataset.evalGrantId);
    if (!grantId) return;
    const actions = [...card.querySelectorAll('div')].find((node) =>
      node.querySelector('[data-eval-issue], [data-eval-revoke]')
    ) || card.lastElementChild;
    if (!actions) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn secondary';
    button.dataset.evalArchive = grantId;
    button.style.marginLeft = 'var(--s-2)';
    button.textContent = 'Delete Grant';
    button.title = 'Revoke any remaining authority and remove this grant from the default list while preserving historical audit evidence.';
    actions.appendChild(button);
  }

  function decorate() {
    const root = document.getElementById(ROOT_ID);
    if (!root) return;
    root.querySelectorAll('[data-eval-grant-card="true"]').forEach(ensureDeleteButton);
  }

  async function archiveGrant(grantId, card) {
    const confirmed = window.confirm(
      `Delete grant ${grantId} from the Admin list?\n\n` +
      'Any remaining active Evaluation authority will be revoked first. Historical execution and audit evidence will be preserved.'
    );
    if (!confirmed) return;

    const button = card?.querySelector(`[data-eval-archive="${CSS.escape(grantId)}"]`);
    if (button) {
      button.disabled = true;
      button.textContent = 'Deleting…';
    }

    try {
      const result = await request(
        `${GRANTS_ENDPOINT}/${encodeURIComponent(grantId)}/archive`,
        'POST'
      );
      card?.remove();
      setResult(
        `Grant removed from the default list. ${Number(result.revoked_key_count || 0)} linked active key(s) revoked; historical audit evidence preserved.`
      );
      window.dispatchEvent(new CustomEvent('pmk-evaluation-grant-updated'));
      window.PMK_ADMIN_EVALUATION_GRANTS?.refresh?.();
    } catch (error) {
      if (button) {
        button.disabled = false;
        button.textContent = 'Delete Grant';
      }
      setResult(`Unable to delete grant from the list: ${error.message || error}`, true);
    }
  }

  function bind() {
    const root = document.getElementById(ROOT_ID);
    if (!root || root.dataset.evaluationGrantArchiveBound === 'true') return;
    root.dataset.evaluationGrantArchiveBound = 'true';
    root.addEventListener('click', (event) => {
      const target = event.target instanceof Element ? event.target : null;
      const button = target?.closest('[data-eval-archive]');
      if (!button || !root.contains(button)) return;
      event.preventDefault();
      event.stopPropagation();
      const grantId = text(button.dataset.evalArchive);
      const card = button.closest('[data-eval-grant-card="true"]');
      if (grantId) archiveGrant(grantId, card);
    });
  }

  function initialize() {
    bind();
    decorate();
  }

  window.addEventListener('pmk-evaluation-grants-rendered', decorate);
  window.PMK_ADMIN_EVALUATION_GRANT_ARCHIVE = { initialize, decorate };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
  } else {
    initialize();
  }
})();
