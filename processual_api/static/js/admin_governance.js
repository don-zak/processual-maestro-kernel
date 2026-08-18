(function () {
  const permissionDomains = [
    ['Administration', 'Invite administrators, manage roles, freeze and revoke access.'],
    ['Marketplace', 'Catalog, offers, payments, reconciliation and subscriptions.'],
    ['Billing', 'Billing visibility, reconciliation and controlled financial actions.'],
    ['Customers', 'Customer support and account visibility.'],
    ['Audit', 'Read immutable administrative activity and security evidence.'],
    ['Engineering', 'Repository review, pull requests, CI and development workflows.'],
    ['Releases', 'Release preparation and gated deployment actions.'],
    ['Infrastructure', 'Cloud configuration and secrets remain separately privileged.'],
  ];

  const securityControls = [
    ['Invitation allow-list', 'Only an exact invited email can enter administrator onboarding.'],
    ['Self-managed credentials', 'Administrators create their own password and enroll their own MFA factor.'],
    ['Recent MFA step-up', 'Sensitive governance operations require a recent authenticator verification.'],
    ['Session revocation', 'Freeze or revoke immediately terminates active administrator sessions.'],
    ['No self-escalation', 'Administrators cannot increase their own role or permission scope.'],
    ['Last-super-admin guard', 'Platform Administrator authority is not a delegated lifecycle target.'],
  ];

  let administrators = [];
  let activeFilter = 'all';
  let searchTerm = '';
  let selectedSessionUserId = '';
  let selectedSessionCanRevoke = false;

  function htmlEscape(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function normalizedState(item) {
    if (item.user_status === 'locked' || item.user_status === 'disabled') return 'frozen';
    if (item.user_status === 'pending_verification') return 'pending';
    if (item.user_status === 'active' && item.authority_status === 'active') return 'active';
    return 'other';
  }

  function visibleAdministrators() {
    return administrators.filter(function (item) {
      const state = normalizedState(item);
      if (activeFilter !== 'all' && state !== activeFilter) return false;
      if (!searchTerm) return true;
      return (item.display_name + ' ' + item.email + ' ' + item.authority)
        .toLowerCase()
        .includes(searchTerm);
    });
  }

  function domainMarkup() {
    return permissionDomains.map(function (item) {
      return '<div class="ag-domain"><div><strong>' + htmlEscape(item[0]) + '</strong><br><small>' + htmlEscape(item[1]) + '</small></div><span class="ag-status">Policy domain</span></div>';
    }).join('');
  }

  function securityMarkup() {
    return securityControls.map(function (item) {
      return '<div class="ag-security-item"><div><strong>' + htmlEscape(item[0]) + '</strong><br><small>' + htmlEscape(item[1]) + '</small></div><span class="ag-status" data-tone="success">Required</span></div>';
    }).join('');
  }

  function pageMarkup() {
    return [
      '<div class="ag-shell">',
      '<section class="ag-hero"><div><p class="ag-eyebrow">Platform governance</p><h1>Administrators &amp; Access</h1><p>Govern trusted administrators, bounded access, MFA readiness, sessions and immutable activity review.</p></div>',
      '<button class="ag-primary" id="ag-invite-admin" type="button" aria-describedby="ag-foundation-note">Invite administrator</button></section>',
      '<section class="ag-summary" aria-label="Administrator governance summary">',
      '<div class="ag-metric"><span>Active</span><strong id="ag-count-active">—</strong></div>',
      '<div class="ag-metric"><span>Pending</span><strong id="ag-count-pending">—</strong></div>',
      '<div class="ag-metric"><span>Frozen</span><strong id="ag-count-frozen">—</strong></div>',
      '<div class="ag-metric"><span>Security risks</span><strong id="ag-count-risks">—</strong></div></section>',
      '<section class="ag-card"><div class="ag-toolbar">',
      '<input class="ag-search" id="ag-search" type="search" placeholder="Search administrators by name or email" aria-label="Search administrators" disabled>',
      '<div class="ag-tabs" role="tablist" aria-label="Administrator state filters">',
      '<button class="ag-tab" data-filter="all" role="tab" type="button" aria-selected="true">All</button>',
      '<button class="ag-tab" data-filter="active" role="tab" type="button" aria-selected="false">Active</button>',
      '<button class="ag-tab" data-filter="pending" role="tab" type="button" aria-selected="false">Pending</button>',
      '<button class="ag-tab" data-filter="frozen" role="tab" type="button" aria-selected="false">Frozen</button>',
      '</div></div><div class="ag-table-wrap"><table class="ag-table">',
      '<thead><tr><th>Administrator</th><th>Role</th><th>Granted</th><th>Status</th><th>Actions</th></tr></thead>',
      '<tbody id="ag-table-body"><tr class="ag-empty-row"><td colspan="5">Loading administrator governance data…</td></tr></tbody>',
      '</table></div><p id="ag-foundation-note" class="ag-note">Governance mutations are server-authorized and require the matching recent MFA step-up and exact permission.</p></section>',
      '<section class="ag-grid">',
      '<div class="ag-card"><p class="ag-eyebrow">Sessions</p><h2>Administrator sessions</h2><p class="ag-muted">Select an administrator to inspect sessions. Session revocation is available only for delegated Platform Supervisors.</p><div id="ag-sessions"><div class="ag-empty-row">No administrator selected.</div></div></div>',
      '<div class="ag-card"><p class="ag-eyebrow">Audit timeline</p><h2>Immutable governance activity</h2><div id="ag-activity"><div class="ag-empty-row">Loading governance activity…</div></div></div>',
      '</section>',
      '<section class="ag-grid"><div class="ag-card"><p class="ag-eyebrow">Permission model</p><h2>Bounded access domains</h2><div class="ag-domain-list">' + domainMarkup() + '</div></div>',
      '<div class="ag-card"><p class="ag-eyebrow">Security invariants</p><h2>Non-negotiable controls</h2><div class="ag-security-list">' + securityMarkup() + '</div></div></section>',
      '<section class="ag-card"><p class="ag-eyebrow">Engineering governance</p><h2>Code review and development access</h2>',
      '<div class="ag-domain-list"><div class="ag-domain"><div><strong>Code Reviewer</strong><br><small>Repository read, pull request review, comments and CI visibility.</small></div><span class="ag-status">Read / review</span></div>',
      '<div class="ag-domain"><div><strong>Developer</strong><br><small>Branches, tests and draft pull requests without deploy authority.</small></div><span class="ag-status">Change bounded</span></div>',
      '<div class="ag-domain"><div><strong>Lead Developer</strong><br><small>Review and release preparation with separately gated production permissions.</small></div><span class="ag-status">Elevated</span></div></div></section>',
      '</div>'
    ].join('');
  }

  async function requestJson(url, options) {
    const response = await fetch(url, options);
    let payload = null;
    try { payload = await response.json(); } catch (_error) { payload = null; }
    if (!response.ok) {
      const detail = payload && payload.detail ? payload.detail : 'Administrator governance request failed.';
      throw new Error(detail);
    }
    return payload;
  }

  function renderSummary() {
    const counts = { active: 0, pending: 0, frozen: 0 };
    administrators.forEach(function (item) {
      const state = normalizedState(item);
      if (Object.prototype.hasOwnProperty.call(counts, state)) counts[state] += 1;
    });
    document.getElementById('ag-count-active').textContent = String(counts.active);
    document.getElementById('ag-count-pending').textContent = String(counts.pending);
    document.getElementById('ag-count-frozen').textContent = String(counts.frozen);
    document.getElementById('ag-count-risks').textContent = String(counts.frozen);
  }

  function actionMarkup(item) {
    const sessions = '<button type="button" class="ag-tab" data-governance-action="sessions" data-user-id="' + htmlEscape(item.user_id) + '">sessions</button>';
    if (item.authority !== 'platform_supervisor') return sessions;
    const state = normalizedState(item);
    const lifecycle = state === 'frozen' ? 'restore' : 'freeze';
    return '<button type="button" class="ag-tab" data-governance-action="' + lifecycle + '" data-user-id="' + htmlEscape(item.user_id) + '">' + lifecycle + '</button> ' + sessions;
  }

  function renderTable() {
    const body = document.getElementById('ag-table-body');
    if (!body) return;
    const items = visibleAdministrators();
    if (!items.length) {
      body.innerHTML = '<tr class="ag-empty-row"><td colspan="5">No administrators match the current filters.</td></tr>';
      return;
    }
    body.innerHTML = items.map(function (item) {
      const state = normalizedState(item);
      const granted = item.granted_at ? new Date(item.granted_at).toLocaleString() : '—';
      return '<tr><td><strong>' + htmlEscape(item.display_name) + '</strong><br><small class="ag-muted">' + htmlEscape(item.email) + '</small></td>' +
        '<td>' + htmlEscape(item.authority) + '</td><td>' + htmlEscape(granted) + '</td>' +
        '<td><span class="ag-status">' + htmlEscape(state) + '</span></td><td>' + actionMarkup(item) + '</td></tr>';
    }).join('');
  }

  async function loadAdministrators() {
    try {
      const response = await fetch('/governance/administrators', { method: 'GET' });
      if (!response.ok) throw new Error('Administrator governance data is temporarily unavailable.');
      const payload = await response.json();
      administrators = Array.isArray(payload.administrators) ? payload.administrators : [];
      renderSummary();
      renderTable();
      document.getElementById('ag-search').disabled = false;
    } catch (error) {
      administrators = [];
      renderSummary();
      const body = document.getElementById('ag-table-body');
      if (body) body.innerHTML = '<tr class="ag-empty-row"><td colspan="5">' + htmlEscape(error.message) + '</td></tr>';
    }
  }

  function renderActivity(events) {
    const root = document.getElementById('ag-activity');
    if (!root) return;
    if (!events.length) {
      root.innerHTML = '<div class="ag-empty-row">No governance activity recorded.</div>';
      return;
    }
    root.innerHTML = events.map(function (item) {
      const occurred = item.occurred_at ? new Date(item.occurred_at).toLocaleString() : '—';
      return '<div class="ag-security-item"><div><strong>' + htmlEscape(item.event_type) + '</strong><br><small>' + htmlEscape(item.reason) + '</small><br><small class="ag-muted">subject ' + htmlEscape(item.subject_user_id) + ' · ' + htmlEscape(occurred) + '</small></div><span class="ag-status">audit</span></div>';
    }).join('');
  }

  async function loadActivity() {
    try {
      const payload = await requestJson('/governance/activity?limit=50', { method: 'GET' });
      renderActivity(Array.isArray(payload.events) ? payload.events : []);
    } catch (error) {
      const root = document.getElementById('ag-activity');
      if (root) root.innerHTML = '<div class="ag-empty-row">' + htmlEscape(error.message) + '</div>';
    }
  }

  function renderSessions(sessions) {
    const root = document.getElementById('ag-sessions');
    if (!root) return;
    if (!sessions.length) {
      root.innerHTML = '<div class="ag-empty-row">No sessions found for this administrator.</div>';
      return;
    }
    root.innerHTML = sessions.map(function (item) {
      const active = !item.revoked_at && new Date(item.expires_at).getTime() > Date.now();
      const statusLabel = active ? 'active' : (item.revoked_at ? 'revoked' : 'expired');
      const button = active && selectedSessionCanRevoke
        ? '<button class="ag-tab" type="button" data-session-revoke="' + htmlEscape(item.session_id) + '">revoke</button>'
        : '';
      return '<div class="ag-security-item"><div><strong>' + htmlEscape(item.session_id) + '</strong><br><small>authenticated ' + htmlEscape(new Date(item.authenticated_at).toLocaleString()) + '</small></div><span><span class="ag-status">' + statusLabel + '</span> ' + button + '</span></div>';
    }).join('');
  }

  async function loadSessions(userId) {
    selectedSessionUserId = userId;
    const selected = administrators.find(function (item) { return item.user_id === userId; });
    selectedSessionCanRevoke = Boolean(selected && selected.authority === 'platform_supervisor');
    const payload = await requestJson(
      '/governance/administrators/' + encodeURIComponent(userId) + '/sessions',
      { method: 'GET' }
    );
    renderSessions(Array.isArray(payload.sessions) ? payload.sessions : []);
  }

  async function inviteAdministrator() {
    const email = window.prompt('Administrator email');
    if (!email) return;
    const level = window.prompt('Supervision level: operations_supervisor or review_supervisor', 'operations_supervisor');
    if (!level) return;
    const reason = window.prompt('Reason for invitation');
    if (!reason) return;
    await requestJson('/governance/administrator-invitations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, supervision_level: level, reason: reason, expires_in_hours: 48 })
    });
    window.alert('Administrator invitation queued for delivery.');
    await loadActivity();
  }

  async function lifecycleAction(action, userId) {
    if (action === 'sessions') {
      await loadSessions(userId);
      return;
    }
    const target = administrators.find(function (item) { return item.user_id === userId; });
    if (!target || target.authority !== 'platform_supervisor') {
      throw new Error('Platform Administrator authority is not a delegated lifecycle target.');
    }
    const reason = window.prompt('Reason for ' + action);
    if (!reason) return;
    const url = '/governance/administrators/' + encodeURIComponent(userId) + '/' + action;
    await requestJson(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: reason })
    });
    await Promise.all([loadAdministrators(), loadActivity()]);
    if (selectedSessionUserId === userId) await loadSessions(userId);
  }

  async function revokeSelectedSession(sessionId) {
    if (!selectedSessionUserId || !selectedSessionCanRevoke) return;
    const reason = window.prompt('Reason for revoke session');
    if (!reason) return;
    await requestJson(
      '/governance/administrators/' + encodeURIComponent(selectedSessionUserId) + '/sessions/' + encodeURIComponent(sessionId) + '/revoke',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason })
      }
    );
    await Promise.all([loadSessions(selectedSessionUserId), loadActivity()]);
  }

  function bindControls() {
    document.getElementById('ag-invite-admin').addEventListener('click', function () {
      inviteAdministrator().catch(function (error) { window.alert(error.message); });
    });
    const search = document.getElementById('ag-search');
    search.addEventListener('input', function () {
      searchTerm = search.value.trim().toLowerCase();
      renderTable();
    });
    document.querySelectorAll('.ag-tab[data-filter]').forEach(function (tab) {
      tab.addEventListener('click', function () {
        activeFilter = tab.dataset.filter || 'all';
        document.querySelectorAll('.ag-tab[data-filter]').forEach(function (candidate) {
          candidate.setAttribute('aria-selected', candidate === tab ? 'true' : 'false');
        });
        renderTable();
      });
    });
    document.getElementById('ag-table-body').addEventListener('click', function (event) {
      const button = event.target.closest('[data-governance-action]');
      if (!button) return;
      lifecycleAction(button.dataset.governanceAction, button.dataset.userId)
        .catch(function (error) { window.alert(error.message); });
    });
    document.getElementById('ag-sessions').addEventListener('click', function (event) {
      const button = event.target.closest('[data-session-revoke]');
      if (!button) return;
      revokeSelectedSession(button.dataset.sessionRevoke)
        .catch(function (error) { window.alert(error.message); });
    });
  }

  function install() {
    const navApi = window.PMK_ADMIN_NAV;
    if (!navApi) return;
    navApi.pageIds.governance = 'page-admin-governance';
    navApi.labelToPage.governance = 'governance';
    navApi.labelToPage.administrators = 'governance';
    navApi.labelToPage['administrators & access'] = 'governance';

    const nav = document.getElementById('nav');
    if (nav && !nav.querySelector('[data-admin-page="governance"]')) {
      const button = document.createElement('button');
      button.className = 'nav-btn';
      button.type = 'button';
      button.dataset.adminPage = 'governance';
      button.innerHTML = '<span class="nav-ind"></span><span class="nav-ico">G</span><span>Administrators</span>';
      nav.appendChild(button);
    }

    const main = document.querySelector('main');
    if (main && !document.getElementById('page-admin-governance')) {
      const page = document.createElement('div');
      page.id = 'page-admin-governance';
      page.className = 'admin-page admin-governance-page';
      page.innerHTML = pageMarkup();
      main.appendChild(page);
      bindControls();
      Promise.all([loadAdministrators(), loadActivity()]);
    }
    navApi.bindNavButtons();
    if (window.location.hash === '#governance') navApi.setActivePage('governance');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install);
  else install();
})();
