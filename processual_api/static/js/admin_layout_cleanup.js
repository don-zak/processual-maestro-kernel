(function () {
  const OWNED_ADMIN_SURFACES = {
    'admin-integration-readiness-tracking-summary-host': 'page-admin-home',
    'admin-integration-readiness-case-management-host': 'page-admin-clients',
    'admin-integration-claim-keys-host': 'page-admin-clients',
    'admin-integration-readiness-operator-package-host': 'page-operator-pilot-handoff',
  };

  function installStyle() {
    if (document.getElementById('admin-layout-cleanup-style')) return;

    const style = document.createElement('style');
    style.id = 'admin-layout-cleanup-style';
    style.textContent = [
      'main{height:calc(100vh - 76px);overflow:auto!important;padding-bottom:72px}',
      '.admin-page:not(.active){display:none!important}',
      '.admin-page.active{display:block!important}',
      '.admin-runtime-grid,[data-admin-runtime-grid]{position:relative;z-index:20}',
      '.admin-runtime-grid .card,[data-admin-runtime-grid] .card{max-height:440px;overflow:auto}',
      '#admin-api-key-create-result,#admin-api-key-list{max-height:440px;overflow:auto!important;white-space:pre-wrap}',
      '.mono-block{max-width:100%;overflow:auto}',
      '.card{box-sizing:border-box}',
    ].join('\n');

    document.head.appendChild(style);
  }

  function markRuntimeGrids() {
    document.querySelectorAll('.admin-runtime-grid').forEach((grid) => {
      grid.setAttribute('data-admin-runtime-grid', '1');
    });
  }

  function resolveOwnerContainer(ownerPage, surfaceId) {
    if (surfaceId === 'admin-integration-readiness-operator-package-host') {
      const pilotRoot = ownerPage.querySelector('#operator-pilot-handoff-root');
      return pilotRoot?.parentElement || ownerPage.firstElementChild || ownerPage;
    }
    return ownerPage.firstElementChild || ownerPage;
  }

  function containOwnedAdminSurfaces() {
    Object.entries(OWNED_ADMIN_SURFACES).forEach(([surfaceId, ownerPageId]) => {
      const surface = document.getElementById(surfaceId);
      const ownerPage = document.getElementById(ownerPageId);
      if (!surface || !ownerPage) return;

      surface.dataset.adminOwnerPage = ownerPageId;
      if (ownerPage.contains(surface)) return;

      resolveOwnerContainer(ownerPage, surfaceId).appendChild(surface);
    });
  }

  function containOwnedPilotSurfaces() {
    containOwnedAdminSurfaces();
  }

  function pruneLegacyPlaceholders() {
    const phrases = [
      'Checking admin session',
      'Protected Area',
      'PROTECTED AREA',
      'Planned usage view',
      'Planned system view',
      'Planned supervisor controls',
      'Tracks the program readiness path',
      'System-level provider settings',
      'Admin auth token missing',
      'Admin session verified',
      'Backend scopes remain the authority',
    ];

    document.querySelectorAll('.card').forEach((card) => {
      if (card.querySelector('[data-admin-runtime-body]')) return;
      if (card.id === 'admin-operations-overview-card') return;

      const text = card.textContent || '';

      if (phrases.some((phrase) => text.includes(phrase))) {
        card.remove();
      }
    });
  }

  function normalizeActivePage() {
    const navApi = window.PMK_ADMIN_NAV;
    const activeKey = document.body?.dataset?.adminActivePage || '';
    const expectedId = activeKey && navApi?.pageIds ? navApi.pageIds[activeKey] : '';
    const expectedPage = expectedId ? document.getElementById(expectedId) : null;

    document.querySelectorAll('.admin-page').forEach((page) => {
      const isActive = expectedPage ? page === expectedPage : page.classList.contains('active');
      page.classList.toggle('active', isActive);
      page.style.display = isActive ? 'block' : 'none';
    });
  }

  function clean() {
    installStyle();
    markRuntimeGrids();
    containOwnedAdminSurfaces();
    pruneLegacyPlaceholders();
    normalizeActivePage();
  }

  window.PMK_ADMIN_LAYOUT = {
    clean,
    markRuntimeGrids,
    containOwnedAdminSurfaces,
    containOwnedPilotSurfaces,
    pruneLegacyPlaceholders,
    normalizeActivePage,
    ownedAdminSurfaces: { ...OWNED_ADMIN_SURFACES },
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      clean();
      setTimeout(clean, 250);
      setTimeout(clean, 1000);
      setTimeout(clean, 2500);
    });
  } else {
    clean();
    setTimeout(clean, 250);
    setTimeout(clean, 1000);
    setTimeout(clean, 2500);
  }
})();
