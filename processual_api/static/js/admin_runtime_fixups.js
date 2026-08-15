(function () {
  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function table(headersList, rows) {
    if (!rows || rows.length === 0) {
      return '<div class="admin-note">No rows returned.</div>';
    }

    return [
      '<table class="admin-data-table">',
      '<thead><tr>' + headersList.map((h) => '<th>' + escapeHtml(h) + '</th>').join('') + '</tr></thead>',
      '<tbody>',
      rows.map((row) =>
        '<tr>' + headersList.map((h) => '<td>' + escapeHtml(row[h] ?? '') + '</td>').join('') + '</tr>'
      ).join(''),
      '</tbody></table>',
    ].join('');
  }

  function ensureStyle() {
    if (document.getElementById('admin-runtime-fixups-style')) return;

    const style = document.createElement('style');
    style.id = 'admin-runtime-fixups-style';
    style.textContent = [
      '#page-admin-home{overflow:visible}',
      '#page-admin-home .admin-runtime-grid{grid-template-columns:repeat(auto-fit,minmax(360px,1fr));align-items:start}',
      '#page-admin-home .card{max-height:460px;overflow:auto}',
      '.admin-page.active{overflow:visible}',
      'main{height:calc(100vh - 76px);overflow:auto!important}',
      '#admin-api-key-create-result,#admin-api-key-list{max-height:460px;overflow:auto!important;white-space:pre-wrap}',
    ].join('\n');

    document.head.appendChild(style);
  }

  function pruneAdminHome() {
    const home = document.getElementById('page-admin-home');
    if (!home) return;

    const keepIds = new Set([
      'admin-operations-overview-card',
      'admin-runtime-home-summary',
      'admin-runtime-auth-state',
    ]);

    home.querySelectorAll('.card').forEach((card) => {
      if (keepIds.has(card.id)) return;
      if (card.querySelector('[data-admin-runtime-body]') && card.id && keepIds.has(card.id)) return;

      const text = card.textContent || '';
      const shouldRemove =
        text.includes('Protected Area') ||
        text.includes('PROTECTED AREA') ||
        text.includes('Checking admin session') ||
        text.includes('Administrative controls') ||
        text.includes('Planned') ||
        text.includes('System-level provider settings') ||
        text.includes('Tracks the program readiness path') ||
        !card.querySelector('[data-admin-runtime-body]');

      if (shouldRemove) card.remove();
    });

    home.querySelectorAll('[data-admin-runtime-grid]').forEach((grid) => {
      grid.querySelectorAll('.card').forEach((card) => {
        if (!keepIds.has(card.id)) card.remove();
      });
      if (!grid.querySelector('.card')) grid.remove();
    });
  }

  function refreshAuthCard() {
    const card = document.getElementById('admin-runtime-auth-state');
    if (!card) return;

    const body = card.querySelector('[data-admin-runtime-body]');
    if (!body) return;

    const diagnostic =
      window.PMK_ADMIN_AUTH && typeof PMK_ADMIN_AUTH.diagnostic === 'function'
        ? PMK_ADMIN_AUTH.diagnostic()
        : {};

    const authHeaders =
      window.PMK_ADMIN_AUTH && typeof PMK_ADMIN_AUTH.headers === 'function'
        ? PMK_ADMIN_AUTH.headers()
        : new Headers();

    body.innerHTML = table(['Field', 'Value'], [
      { Field: 'Bearer token found', Value: diagnostic.bearerFound ? 'yes' : 'no' },
      { Field: 'Bearer storage key', Value: diagnostic.bearerKey || 'missing' },
      { Field: 'Authorization header', Value: authHeaders.has('Authorization') ? 'present' : 'missing' },
      { Field: 'X-API-Key header', Value: authHeaders.has('X-API-Key') ? 'present' : 'missing' },
      { Field: 'Local token keys', Value: JSON.stringify(diagnostic.localStorageKeys || []) },
      { Field: 'Session token keys', Value: JSON.stringify(diagnostic.sessionStorageKeys || []) },
    ]);
  }

  function fix() {
    ensureStyle();
    pruneAdminHome();
    refreshAuthCard();

    if (window.PMK_ADMIN_LAYOUT && typeof PMK_ADMIN_LAYOUT.clean === 'function') {
      PMK_ADMIN_LAYOUT.clean();
    }
  }

  window.PMK_ADMIN_RUNTIME_FIXUPS = {
    fix,
    pruneAdminHome,
    refreshAuthCard,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      fix();
      setTimeout(fix, 250);
      setTimeout(fix, 1000);
      setTimeout(fix, 2500);
    });
  } else {
    fix();
    setTimeout(fix, 250);
    setTimeout(fix, 1000);
    setTimeout(fix, 2500);
  }
})();
