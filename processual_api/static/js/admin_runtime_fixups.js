
(function () {
  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function headers() {
    if (window.PMK_ADMIN_AUTH && typeof PMK_ADMIN_AUTH.headers === 'function') {
      return PMK_ADMIN_AUTH.headers();
    }

    return new Headers({ 'Content-Type': 'application/json' });
  }

  async function request(method, path, body) {
    const response = await fetch(path, {
      method,
      credentials: 'include',
      headers: headers(),
      body: method === 'GET' ? undefined : JSON.stringify(body || {}),
    });

    const text = await response.text();
    let data = text;

    try {
      data = text ? JSON.parse(text) : {};
    } catch (error) {}

    if (!response.ok) {
      const failure = new Error(
        data && typeof data === 'object'
          ? data.detail || data.message || JSON.stringify(data)
          : text || response.statusText
      );
      failure.status = response.status;
      failure.data = data;
      throw failure;
    }

    return data;
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
      '.admin-profile-controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:var(--s-3);margin-top:var(--s-3);align-items:end}',
      '.admin-profile-controls label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}',
      '.admin-profile-controls input,.admin-profile-controls select{width:100%}',
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
      if (card.querySelector('[data-admin-runtime-body]') && card.id) {
        if (keepIds.has(card.id)) return;
      }

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

      if (shouldRemove) {
        card.remove();
      }
    });

    home.querySelectorAll('[data-admin-runtime-grid]').forEach((grid) => {
      grid.querySelectorAll('.card').forEach((card) => {
        if (!keepIds.has(card.id)) {
          card.remove();
        }
      });

      if (!grid.querySelector('.card')) {
        grid.remove();
      }
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

  function keyProfile(profile) {
    const profiles = {
      client_api: {
        label: 'Client API',
        role: 'client',
        category: 'client_api',
        plan: 'free',
        scopes: ['cgt:govern', 'reports:read'],
      },
      pilot_client: {
        label: 'Pilot Client',
        role: 'client',
        category: 'pilot_client',
        plan: 'pilot',
        scopes: ['cgt:govern', 'reports:read'],
      },
      support_viewer: {
        label: 'Support Viewer',
        role: 'support_admin',
        category: 'support_viewer',
        plan: 'internal',
        scopes: ['reports:read'],
      },
      ops_admin: {
        label: 'Ops Admin',
        role: 'ops_admin',
        category: 'ops_admin',
        plan: 'internal',
        scopes: ['adapters:read', 'usage:read', 'reports:read'],
      },
      security_admin: {
        label: 'Security Admin',
        role: 'security_admin',
        category: 'security_admin',
        plan: 'internal',
        scopes: ['admin:settings'],
      },
      owner_admin: {
        label: 'Owner Admin',
        role: 'owner_admin',
        category: 'owner_admin',
        plan: 'internal',
        scopes: ['admin:settings', 'cgt:govern', 'reports:read'],
      },
    };

    return profiles[profile] || profiles.client_api;
  }

  function ensureApiKeyProfileControls() {
    const page = document.getElementById('page-admin-api-keys');
    if (!page) return;

    if (document.getElementById('admin-api-key-profile')) return;

    const generateButton = document.getElementById('admin-api-key-generate-btn');
    const targetCard = generateButton ? generateButton.closest('.card') : null;
    const target = targetCard || page.querySelector('.card') || page;

    const controls = document.createElement('div');
    controls.className = 'admin-profile-controls';
    controls.id = 'admin-api-key-profile-controls';
    controls.innerHTML = [
      '<div>',
      '<label for="admin-api-key-profile">Key category / team role</label>',
      '<select id="admin-api-key-profile" class="inp-sel">',
      '<option value="client_api">Client API — client console access</option>',
      '<option value="pilot_client">Pilot Client — trial/onboarding</option>',
      '<option value="support_viewer">Support Viewer — read reports</option>',
      '<option value="ops_admin">Ops Admin — providers and usage</option>',
      '<option value="security_admin">Security Admin — API keys/settings</option>',
      '<option value="owner_admin">Owner Admin — full internal admin</option>',
      '</select>',
      '</div>',
      '<div>',
      '<label for="admin-api-key-label">Label</label>',
      '<input id="admin-api-key-label" class="inp" placeholder="client-or-team-name" />',
      '</div>',
    ].join('');

    const result = document.getElementById('admin-api-key-create-result');
    if (result && result.parentElement === target) {
      target.insertBefore(controls, result);
    } else {
      target.appendChild(controls);
    }
  }

  async function refreshApiKeysTable() {
    try {
      const data = await request('GET', '/settings/api-keys');
      const output = document.getElementById('admin-api-key-list');

      if (output) {
        output.textContent = JSON.stringify(data, null, 2);
      }

      if (window.PMK_ADMIN_RUNTIME && typeof PMK_ADMIN_RUNTIME.refreshDashboard === 'function') {
        setTimeout(() => PMK_ADMIN_RUNTIME.refreshDashboard(), 100);
      }
    } catch (error) {
      const output = document.getElementById('admin-api-key-list');
      if (output) {
        output.textContent = JSON.stringify({
          error: error.message,
          status: error.status || 'error',
          data: error.data,
        }, null, 2);
      }
    }
  }

  async function generateProfiledApiKey() {
    const profileName = document.getElementById('admin-api-key-profile')?.value || 'client_api';
    const profile = keyProfile(profileName);
    const labelInput = document.getElementById('admin-api-key-label')?.value || '';
    const label =
      labelInput.trim() ||
      profile.category + '-' + new Date().toISOString().replaceAll(':', '-').slice(0, 19);

    const button = document.getElementById('admin-api-key-generate-btn');
    const output = document.getElementById('admin-api-key-create-result');

    if (button) button.disabled = true;
    if (output) output.textContent = 'Generating ' + profile.label + ' key...';

    const payloads = [
      {
        name: label,
        label,
        category: profile.category,
        role: profile.role,
        plan: profile.plan,
        scopes: profile.scopes,
      },
      {
        name: label,
        label,
        scopes: profile.scopes,
      },
      {
        name: label,
        scopes: profile.scopes,
      },
      {
        label,
      },
      {},
    ];

    const attempts = [];

    for (const payload of payloads) {
      try {
        const data = await request('POST', '/settings/api-keys', payload);

        if (output) {
          output.textContent = JSON.stringify({
            requestedProfile: profile,
            endpoint: '/settings/api-keys',
            payload,
            response: data,
          }, null, 2);
        }

        await refreshApiKeysTable();

        if (button) button.disabled = false;
        return;
      } catch (error) {
        attempts.push({
          endpoint: '/settings/api-keys',
          payload,
          status: error.status || 'error',
          error: error.message,
          data: error.data,
        });
      }
    }

    try {
      const data = await request('POST', '/settings/api-keys/generate', {
        name: label,
        label,
        category: profile.category,
        role: profile.role,
        scopes: profile.scopes,
      });

      if (output) {
        output.textContent = JSON.stringify({
          requestedProfile: profile,
          endpoint: '/settings/api-keys/generate',
          response: data,
        }, null, 2);
      }

      await refreshApiKeysTable();
    } catch (error) {
      attempts.push({
        endpoint: '/settings/api-keys/generate',
        status: error.status || 'error',
        error: error.message,
        data: error.data,
      });

      if (output) {
        output.textContent = JSON.stringify({
          error: 'API key generation failed',
          requestedProfile: profile,
          attempts,
        }, null, 2);
      }
    }

    if (button) button.disabled = false;
  }

  function bindApiKeyButtons() {
    ensureApiKeyProfileControls();

    const generateButton = document.getElementById('admin-api-key-generate-btn');
    const refreshButton = document.getElementById('admin-api-key-refresh-btn');

    if (generateButton) {
      generateButton.onclick = function (event) {
        event.preventDefault();
        generateProfiledApiKey();
        return false;
      };
    }

    if (refreshButton) {
      refreshButton.onclick = function (event) {
        event.preventDefault();
        refreshApiKeysTable();
        return false;
      };
    }
  }

  function fix() {
    ensureStyle();
    pruneAdminHome();
    refreshAuthCard();
    bindApiKeyButtons();

    if (window.PMK_ADMIN_LAYOUT && typeof PMK_ADMIN_LAYOUT.clean === 'function') {
      PMK_ADMIN_LAYOUT.clean();
    }
  }

  window.PMK_ADMIN_RUNTIME_FIXUPS = {
    fix,
    pruneAdminHome,
    refreshAuthCard,
    generateProfiledApiKey,
    keyProfile,
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
