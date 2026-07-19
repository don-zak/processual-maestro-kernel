(function () {
  const pageIds = {
    home: 'page-admin-home',
    adapters: 'page-admin-adapters',
    'api-keys': 'page-admin-api-keys',
    'operator-pilot-handoff': 'page-operator-pilot-handoff',
    clients: 'page-admin-clients',
    usage: 'page-admin-usage',
    'program-progress': 'page-admin-program-progress',
    'system-health': 'page-admin-system-health',
    'system-settings': 'page-admin-system-settings',
  };

  const labelToPage = {
    'admin home': 'home',
    home: 'home',
    adapters: 'adapters',
    'api keys': 'api-keys',
    clients: 'clients',
    'usage monitor': 'usage',
    usage: 'usage',
    'program progress': 'program-progress',
    'system health': 'system-health',
    'system settings': 'system-settings',
  };

  function installStyle() {
    if (document.getElementById('admin-nav-runtime-style')) return;

    const style = document.createElement('style');
    style.id = 'admin-nav-runtime-style';
    style.textContent = [
      '.admin-page { display: none; }',
      '.admin-page.active { display: block; }',
      '[data-admin-page] { cursor: pointer; }',
    ].join('\n');

    document.head.appendChild(style);
  }

  function normalizeText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
  }

  function mainContainer() {
    return document.querySelector('main') || document.getElementById('content') || document.body;
  }

  function pageFromButton(button) {
    if (button.dataset.adminPage && pageIds[button.dataset.adminPage]) {
      return button.dataset.adminPage;
    }

    const text = normalizeText(button.textContent);

    if (labelToPage[text]) return labelToPage[text];
    if (text.includes('admin home')) return 'home';
    if (text.includes('adapters')) return 'adapters';
    if (text.includes('api keys')) return 'api-keys';
    if (text.includes('clients')) return 'clients';
    if (text.includes('usage')) return 'usage';
    if (text.includes('program progress')) return 'program-progress';
    if (text.includes('system health')) return 'system-health';
    if (text.includes('system settings')) return 'system-settings';

    return '';
  }

  function ensurePage(id, title, subtitle, body) {
    let page = document.getElementById(id);

    if (page) {
      page.classList.add('admin-page');
      return page;
    }

    page = document.createElement('div');
    page.id = id;
    page.className = 'admin-page';
    page.innerHTML = [
      '<div>',
      '<div class="sec-hdr">',
      '<div class="sh-title">' + title + '</div>',
      '<div class="sh-sub">' + subtitle + '</div>',
      '</div>',
      '<div class="card">',
      '<div class="mono-block" style="font-size:11px;white-space:pre-wrap">' + body + '</div>',
      '</div>',
      '</div>',
    ].join('');

    mainContainer().appendChild(page);
    return page;
  }

  function ensureHomeWrapper() {
    const main = mainContainer();

    let home = document.getElementById(pageIds.home);
    if (!home) {
      const firstKnownPage = main.querySelector(
        '#page-admin-adapters, #page-admin-api-keys, #page-admin-clients, #page-admin-usage, #page-admin-program-progress, #page-admin-system-health, #page-admin-system-settings'
      );

      home = document.createElement('div');
      home.id = pageIds.home;
      home.className = 'admin-page active';

      const children = Array.from(main.childNodes);
      for (const child of children) {
        if (child === firstKnownPage) break;

        if (
          child.nodeType === Node.ELEMENT_NODE &&
          Object.values(pageIds).includes(child.id)
        ) {
          break;
        }

        home.appendChild(child);
      }

      main.insertBefore(home, firstKnownPage || main.firstChild);
    }

    home.classList.add('admin-page');

    Object.entries(pageIds).forEach(([name, id]) => {
      if (name === 'home') return;

      const page = document.getElementById(id);
      if (!page) return;

      if (home.contains(page)) {
        main.appendChild(page);
      }

      page.classList.add('admin-page');
    });
  }

  function ensurePages() {
    ensureHomeWrapper();

    ensurePage(
      pageIds.adapters,
      'Adapter Manager',
      'Provider configuration and testing',
      'Provider configuration and testing are available in this admin page.'
    );

    ensurePage(
      pageIds['api-keys'],
      'API Keys',
      'Admin-only API key controls',
      'Generate New Key and Refresh Keys controls are available in this admin page.'
    );

    ensurePage(
      pageIds.clients,
      'Clients',
      'Customers, pilots, subscriptions, and Bridge to Client Console',
      'Planned controls: Pending Applications, Approved Applications, Active Pilots, Clients, subscriptions, and Bridge to Client Console.'
    );

    ensurePage(
      pageIds.usage,
      'Usage Monitor',
      'Usage, quota, reports, errors, and latency',
      'Planned usage view: evaluations used, evaluations remaining, requests today, requests this month, reports generated, errors, average latency, API key last used, and provider connection status.'
    );

    ensurePage(
      pageIds['program-progress'],
      'Program Progress',
      'Productization and deployment readiness',
      'Tracks admin/client separation, onboarding, API keys, quota, provider configuration, support workflow, security review, and Cloud Run readiness.'
    );

    ensurePage(
      pageIds['system-health'],
      'System Health',
      'Health, readiness, telemetry, and operational checks',
      'Tracks health/live, health/ready, provider readiness, telemetry state, usage logging state, audit storage, backup state, and production warning status.'
    );

    ensurePage(
      pageIds['system-settings'],
      'System Settings',
      'Admin-only system settings',
      'System-level provider settings, notification routing, production configuration checks, and deployment controls will be moved here in later admin phases.'
    );
  }

  function bindNavButtons() {
    document.querySelectorAll('.nav-btn').forEach((button) => {
      const page = pageFromButton(button);
      if (!page || !pageIds[page]) return;

      button.dataset.adminPage = page;
      button.setAttribute('type', 'button');

      button.onclick = function (event) {
        if (event) {
          event.preventDefault();
          event.stopPropagation();
        }

        setActivePage(page);
        return false;
      };
    });
  }

  function normalizePage(page) {
    return pageIds[page] && document.getElementById(pageIds[page]) ? page : 'home';
  }

  function setActivePage(page) {
    const activePage = normalizePage(page);
    document.body.dataset.adminActivePage = activePage;

    document.querySelectorAll('[data-admin-page], .nav-btn').forEach((button) => {
      const buttonPage = pageFromButton(button);
      if (!buttonPage) return;

      button.dataset.adminPage = buttonPage;
      button.classList.toggle('active', buttonPage === activePage);
    });

    Object.entries(pageIds).forEach(([name, id]) => {
      const page = document.getElementById(id);
      if (!page) return;

      const isActive = name === activePage;
      page.classList.toggle('active', isActive);
      page.style.display = isActive ? 'block' : 'none';
    });

    const nextHash = '#' + activePage;
    if (window.location.hash !== nextHash) {
      window.history.replaceState(null, '', nextHash);
    }
  }

  function boot() {
    installStyle();
    ensurePages();
    bindNavButtons();

    document.addEventListener(
      'click',
      (event) => {
        const button = event.target.closest('[data-admin-page], .nav-btn');
        if (!button) return;

        const page = pageFromButton(button);
        if (!page) return;

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        setActivePage(page);
      },
      true
    );

    window.addEventListener('hashchange', () => {
      setActivePage(window.location.hash.replace('#', ''));
    });

    setActivePage(window.location.hash.replace('#', '') || 'home');
  }

  window.PMK_ADMIN_NAV = {
    setActivePage,
    bindNavButtons,
    pageIds,
    labelToPage,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();

(function bootstrapIntegrationCenter18() {
  function install() {
    const api = window.PMK_ADMIN_NAV;
    if (!api) return;

    api.pageIds['integration-center'] = 'page-admin-integration-center';
    api.labelToPage['integration center'] = 'integration-center';

    const nav = document.getElementById('nav');
    if (nav && !nav.querySelector('[data-admin-page="integration-center"]')) {
      const pilot = nav.querySelector('[data-admin-page="operator-pilot-handoff"]');
      const button = document.createElement('button');
      button.className = 'nav-btn';
      button.type = 'button';
      button.dataset.adminPage = 'integration-center';
      button.innerHTML = '<span class="nav-ind"></span><span class="nav-ico">I</span><span>Integration Center</span>';
      nav.insertBefore(button, pilot || null);
    }

    const main = document.querySelector('main');
    if (main && !document.getElementById('page-admin-integration-center')) {
      const page = document.createElement('div');
      page.id = 'page-admin-integration-center';
      page.className = 'admin-page';
      page.innerHTML = '<div id="admin-integration-center-root"><div class="ic18-empty">Loading integration center…</div></div>';
      const pilotPage = document.getElementById('page-operator-pilot-handoff');
      main.insertBefore(page, pilotPage || null);
    }

    if (!document.querySelector('link[data-ic18-style]')) {
      const style = document.createElement('link');
      style.rel = 'stylesheet';
      style.href = '/console/css/admin_integration_center_18.css?v=stage18r1';
      style.dataset.ic18Style = 'true';
      document.head.appendChild(style);
    }

    if (!document.querySelector('script[data-ic18-script]')) {
      const script = document.createElement('script');
      script.src = '/console/js/admin_integration_center_18.js?v=stage18r1';
      script.dataset.ic18Script = 'true';
      document.body.appendChild(script);
    }

    api.bindNavButtons();
    if (window.location.hash === '#integration-center') {
      api.setActivePage('integration-center');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install);
  } else {
    install();
  }
})();
