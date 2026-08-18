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
      '    <div class="ag-metric"><span>Active</span><strong>—</strong></div>',
      '    <div class="ag-metric"><span>Pending</span><strong>—</strong></div>',
      '    <div class="ag-metric"><span>Frozen</span><strong>—</strong></div>',
      '    <div class="ag-metric"><span>Security risks</span><strong>—</strong></div>',
      '  </section>',
      '  <section class="ag-card">',
      '    <div class="ag-toolbar">',
      '      <input class="ag-search" type="search" placeholder="Search administrators by name or email" aria-label="Search administrators" disabled>',
      '      <div class="ag-tabs" role="tablist" aria-label="Administrator state filters">',
      '        <button class="ag-tab" role="tab" type="button" aria-selected="true">All</button>',
      '        <button class="ag-tab" role="tab" type="button" aria-selected="false">Active</button>',
      '        <button class="ag-tab" role="tab" type="button" aria-selected="false">Pending</button>',
      '        <button class="ag-tab" role="tab" type="button" aria-selected="false">Frozen</button>',
      '      </div>',
      '    </div>',
      '    <div class="ag-table-wrap">',
      '      <table class="ag-table">',
      '        <thead><tr><th>Administrator</th><th>Role</th><th>Access</th><th>MFA</th><th>Last active</th><th>Status</th></tr></thead>',
      '        <tbody><tr class="ag-empty-row"><td colspan="6">Governance read API is not connected yet. No administrator data is fabricated in this foundation phase.</td></tr></tbody>',
      '      </table>',
      '    </div>',
      '    <p id="ag-foundation-note" class="ag-note">Foundation mode: invitation, permission mutation, freeze and revoke controls remain intentionally disabled until server-side authority checks, audit persistence and session invalidation are implemented.</p>',
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
      '    <p class="ag-footnote">This page is deliberately honest about readiness: visual structure is live in the branch, while privileged controls stay inert until the matching backend and tests exist.</p>',
      '  </section>',
      '</div>'
    ].join('');
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
