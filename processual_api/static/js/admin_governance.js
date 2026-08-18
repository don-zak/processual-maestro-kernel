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
    ['Last-super-admin guard', 'The final active Super Administrator cannot be frozen or revoked.'],
  ];

  const roadmap = [
    ['1. Governance foundation', 'Permission taxonomy, lifecycle states, invariants and persistence.'],
    ['2. Invitation onboarding', 'Email-bound invitation, password setup, MFA enrollment and activation.'],
    ['3. Authorization engine', 'Server-side roles, granular permissions and MFA step-up enforcement.'],
    ['4. Lifecycle controls', 'Freeze, restore, revoke and immediate session invalidation.'],
    ['5. Audit timeline', 'Actor, action, target, request, session and result correlation.'],
    ['6. Engineering access', 'Code review, PR, CI and release permissions separated from operations.'],
    ['7. Qualification', 'Security, accessibility, responsive UX and end-to-end governance tests.'],
  ];

  let administrators = [];
  let activeFilter = 'all';
  let searchTerm = '';

  function htmlEscape(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
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

  function roadmapMarkup() {
    return roadmap.map(function (item) {
      return '<div class="ag-roadmap-item"><div><strong>' + htmlEscape(item[0]) + '</strong><br><small>' + htmlEscape(item[1]) + '</small></div><span class="ag-status">Planned</span></div>';
    }).join('');
  }

  function pageMarkup() {
    return [
      '<div class="ag-shell">',
      '  <section class="ag-hero">',
      '    <div>',
      '      <p class="ag-eyebrow">Platform governance</p>',
      '      <h1>Administrators &amp; Access</h1>',
      '      <p>Govern trusted administrators, bounded operational and engineering access, MFA readiness, session state and immutable activity review.</p>',
      '    </div>',
      '    <button class="ag-primary" id="ag-invite-admin" type="button" disabled aria-describedby="ag-foundation-note">Invite administrator</button>',
      '  </section>',
      '  <section class="ag-summary" aria-label="Administrator governance summary">',
      '    <div class="ag-metric"><span>Active</span><strong id="ag-count-active">—</strong></div>',
      '    <div class="ag-metric"><span>Pending</span><strong id="ag-count-pending">—</strong></div>',
      '    <div class="ag-metric"><span>Frozen</span><strong id="ag-count-frozen">—</strong></div>',
      '    <div class="ag-metric"><span>Security risks</span><strong id="ag-count-risks">—</strong></div>',
      '  </section>',
      '  <section class="ag-card">',
      '    <div class="ag-toolbar">',
      '      <input class="ag-search" id="ag-search" type="search" placeholder="Search administrators by name or email" aria-label="Search administrators" disabled>',
      '      <div class="ag-tabs" role="tablist" aria-label="Administrator state filters">',
      '        <button class="ag-tab" data-filter="all" role="tab" type="button" aria-selected="true">All</button>',
      '        <button class="ag-tab" data-filter="active" role="tab" type="button" aria-selected="false">Active</button>',
      '        <button class="ag-tab" data-filter="pending" role="tab" type="button" aria-selected="false">Pending</button>',
      '        <button class="ag-tab" data-filter="frozen" role="tab" type="button" aria-selected="false">Frozen</button>',
      '      </div>',
      '    </div>',
      '    <div class="ag-table-wrap">',
      '      <table class="ag-table">',
      '        <thead><tr><th>Administrator</th><th>Role</th><th>Access</th><th>MFA</th><th>Granted</th><th>Status</th></tr></thead>',
      '        <tbody id="ag-table-body"><tr class="ag-empty-row"><td colspan="6">Loading administrator governance data…</td></tr></tbody>',
      '      </table>',
      '    </div>',
      '    <p id="ag-foundation-note" class="ag-note">Read-only governance mode: administrator identity data is loaded from the server. Invitation, permission mutation, freeze and revoke controls remain intentionally disabled until their matching server-side authority, audit and session lifecycle are implemented.</p>',
      '  </section>',
      '  <section class="ag-grid">',
      '    <div class="ag-card">',
      '      <p class="ag-eyebrow">Permission model</p>',
      '      <h2>Bounded access domains</h2>',
      '      <p class="ag-muted">Roles provide safe presets; explicit permissions define the real server-side scope. Wildcard administrative authority is not part of the model.</p>',
      '      <div class="ag-domain-list">' + domainMarkup() + '</div>',
      '    </div>',
      '    <div class="ag-card">',
      '      <p class="ag-eyebrow">Security invariants</p>',
      '      <h2>Non-negotiable controls</h2>',
      '      <div class="ag-security-list">' + securityMarkup() + '</div>',
      '    </div>',
      '  </section>',
      '  <section class="ag-card">',
      '    <p class="ag-eyebrow">Engineering governance</p>',
      '    <h2>Code review and development access</h2>',
      '    <p class="ag-muted">Engineering permissions are separate from commercial operations. A developer may review code, create branches or draft pull requests without receiving production deployment, secrets or billing authority.</p>',
      '    <div class="ag-domain-list">',
      '      <div class="ag-domain"><div><strong>Code Reviewer</strong><br><small>Repository read, pull request review, comments and CI visibility.</small></div><span class="ag-status">Read / review</span></div>',
      '      <div class="ag-domain"><div><strong>Developer</strong><br><small>Branch creation, code changes, tests and draft pull requests; no merge or deploy authority by default.</small></div><span class="ag-status" data-tone="warning">Change bounded</span></div>',
      '      <div class="ag-domain"><div><strong>Lead Developer</strong><br><small>Review and release preparation with separately gated production permissions.</small></div><span class="ag-status">Elevated</span></div>',
      '    </div>',
      '  </section>',
      '  <section class="ag-card">',
      '    <p class="ag-eyebrow">Delivery sequence</p>',
      '    <h2>Governance development roadmap</h2>',
      '    <div class="ag-roadmap">' + roadmapMarkup() + '</div>',
      '    <p class="ag-footnote">Read access is now backed by the identity authority service. Privileged mutations stay inert until the matching server-side controls and tests exist.</p>',
      '  </section>',
      '</div>'
    ].join('');
  }

  function normalizedState(item) {
    if (item.user_status === 'locked' || item.user_status === 'disabled') return 'frozen';
    if (item.user_status === 'pending_verification') return 'pending';
    if (item.user_status === 'active' && item.authority_status === 'active') return 'active';
    return 'other';
  }

  function roleLabel(authority) {
    if (authority === 'platform_admin') return 'Platform Administrator';
    if (authority === 'platform_supervisor') return 'Platform Supervisor';
    return authority || 'Unknown';
  }

  function statusTone(state) {
    if (state === 'active') return 'success';
    if (state === 'pending') return 'warning';
    if (state === 'frozen') return 'danger';
    return '';
  }

  function visibleAdministrators() {
    return administrators.filter(function (item) {
      const state = normalizedState(item);
      if (activeFilter !== 'all' && state !== activeFilter) return false;
      if (!searchTerm) return true;
      const haystack = (item.display_name + ' ' + item.email + ' ' + roleLabel(item.authority)).toLowerCase();
      return haystack.includes(searchTerm);
    });
  }

  function renderSummary() {
    const counts = { active: 0, pending: 0, frozen: 0 };
    administrators.forEach(function (item) {
      const state = normalizedState(item);
      if (Object.prototype.hasOwnProperty.call(counts, state)) counts[state] += 1;
    });
    const active = document.getElementById('ag-count-active');
    const pending = document.getElementById('ag-count-pending');
    const frozen = document.getElementById('ag-count-frozen');
    const risks = document.getElementById('ag-count-risks');
    if (active) active.textContent = String(counts.active);
    if (pending) pending.textContent = String(counts.pending);
    if (frozen) frozen.textContent = String(counts.frozen);
    if (risks) risks.textContent = String(counts.frozen);
  }

  function renderTable() {
    const body = document.getElementById('ag-table-body');
    if (!body) return;
    const items = visibleAdministrators();
    if (!items.length) {
      body.innerHTML = '<tr class="ag-empty-row"><td colspan="6">No administrators match the current filters.</td></tr>';
      return;
    }
    body.innerHTML = items.map(function (item) {
      const state = normalizedState(item);
      const granted = item.granted_at ? new Date(item.granted_at).toLocaleString() : '—';
      return [
        '<tr>',
        '<td><strong>' + htmlEscape(item.display_name) + '</strong><br><small class="ag-muted">' + htmlEscape(item.email) + '</small></td>',
        '<td>' + htmlEscape(roleLabel(item.authority)) + '</td>',
        '<td>Identity authority</td>',
        '<td>Required</td>',
        '<td>' + htmlEscape(granted) + '</td>',
        '<td><span class="ag-status" data-tone="' + htmlEscape(statusTone(state)) + '">' + htmlEscape(state) + '</span></td>',
        '</tr>'
      ].join('');
    }).join('');
  }

  function setLoadFailure(message) {
    const body = document.getElementById('ag-table-body');
    if (body) body.innerHTML = '<tr class="ag-empty-row"><td colspan="6">' + htmlEscape(message) + '</td></tr>';
  }

  async function loadAdministrators() {
    try {
      const response = await fetch('/governance/administrators', { method: 'GET' });
      if (!response.ok) {
        if (response.status === 401) throw new Error('Authentication is required to load administrator governance data.');
        if (response.status === 403) throw new Error('A recent Platform Administrator MFA verification is required.');
        throw new Error('Administrator governance data is temporarily unavailable.');
      }
      const payload = await response.json();
      administrators = Array.isArray(payload.administrators) ? payload.administrators : [];
      renderSummary();
      renderTable();
      const search = document.getElementById('ag-search');
      if (search) search.disabled = false;
    } catch (error) {
      administrators = [];
      renderSummary();
      setLoadFailure(error && error.message ? error.message : 'Administrator governance data is temporarily unavailable.');
    }
  }

  function bindReadControls() {
    const search = document.getElementById('ag-search');
    if (search) {
      search.addEventListener('input', function () {
        searchTerm = search.value.trim().toLowerCase();
        renderTable();
      });
    }
    document.querySelectorAll('.ag-tab[data-filter]').forEach(function (tab) {
      tab.addEventListener('click', function () {
        activeFilter = tab.dataset.filter || 'all';
        document.querySelectorAll('.ag-tab[data-filter]').forEach(function (candidate) {
          candidate.setAttribute('aria-selected', candidate === tab ? 'true' : 'false');
        });
        renderTable();
      });
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
      const settings = nav.querySelector('[data-admin-page="system-settings"]');
      const button = document.createElement('button');
      button.className = 'nav-btn';
      button.type = 'button';
      button.dataset.adminPage = 'governance';
      button.innerHTML = '<span class="nav-ind"></span><span class="nav-ico">G</span><span>Administrators</span>';
      nav.insertBefore(button, settings || null);
    }

    const main = document.querySelector('main');
    if (main && !document.getElementById('page-admin-governance')) {
      const page = document.createElement('div');
      page.id = 'page-admin-governance';
      page.className = 'admin-page admin-governance-page';
      page.innerHTML = pageMarkup();
      const settingsPage = document.getElementById('page-admin-system-settings');
      main.insertBefore(page, settingsPage || null);
      bindReadControls();
      loadAdministrators();
    }

    navApi.bindNavButtons();
    if (window.location.hash === '#governance') {
      navApi.setActivePage('governance');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install);
  } else {
    install();
  }
})();
