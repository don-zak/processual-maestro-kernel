(function () {
  const CANONICAL_CARD_IDS = [
    'admin-program-supervision-readiness',
    'admin-supervisor-overview-counters',
    'admin-integration-readiness-tracking-summary-host',
    'admin-runtime-home-summary',
    'admin-runtime-auth-state',
  ];

  function installStyle() {
    if (document.getElementById('admin-home-layout-style')) return;

    const style = document.createElement('style');
    style.id = 'admin-home-layout-style';
    style.textContent = [
      '#page-admin-home{padding:24px 28px 96px!important;overflow:visible!important;overflow-x:hidden!important}',
      '#page-admin-home .card{box-sizing:border-box;max-width:100%!important;position:static!important;float:none!important;transform:none!important;inset:auto!important;isolation:isolate;contain:layout paint;overflow:auto!important}',
      '#page-admin-home > section.page{display:flex!important;flex-direction:column!important;gap:24px!important;position:static!important;float:none!important;height:auto!important;min-height:0!important;min-width:0!important;max-width:100%!important;overflow:visible!important;transform:none!important}',
      '#page-admin-home > section.page > *{position:static!important;float:none!important;transform:none!important;inset:auto!important;left:auto!important;right:auto!important;top:auto!important;bottom:auto!important;min-width:0!important;max-width:100%!important;flex:none!important}',
      '#admin-home-canonical-surface{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:24px!important;width:100%!important;max-width:100%!important;min-width:0!important;height:auto!important;position:static!important;float:none!important;transform:none!important;overflow:visible!important;margin:0 0 72px!important}',
      '#admin-home-canonical-surface>.card,#admin-home-canonical-surface>[id$="-host"]{position:static!important;float:none!important;transform:none!important;inset:auto!important;left:auto!important;right:auto!important;top:auto!important;bottom:auto!important;width:100%!important;max-width:100%!important;min-width:0!important;height:auto!important;margin:0!important;overflow:auto!important;z-index:auto!important}',
      '#admin-program-supervision-readiness,#admin-supervisor-overview-counters,#admin-integration-readiness-tracking-summary-host{grid-column:1/-1!important}',
      '#admin-home-canonical-surface .mono-block,#admin-home-canonical-surface .admin-note{max-width:100%!important;overflow-wrap:anywhere!important;white-space:pre-wrap}',
      '#admin-home-canonical-surface .admin-data-table{max-width:100%;display:block;overflow-x:auto}',
      '#admin-home-canonical-surface .admin-kpi-grid{grid-template-columns:repeat(auto-fit,minmax(140px,1fr))}',
      '#page-admin-home [data-admin-runtime-grid]:not(#admin-home-canonical-surface){display:contents!important}',
      '#main{height:100vh!important;min-height:0!important;max-height:100vh!important;overflow:auto!important;overflow-x:hidden!important;padding-bottom:0!important}',
      '@media (max-width:980px){#admin-home-canonical-surface{grid-template-columns:1fr!important}}',
      '@media (max-width:600px){#brand{justify-content:center!important;padding:12px 4px!important;min-height:56px}#brand>div:last-child{display:none!important}#brand-mark{margin:0 auto!important}#page-admin-home{padding:12px 8px 72px!important}#page-admin-home>section.page{gap:14px!important}#admin-home-canonical-surface{grid-template-columns:minmax(0,1fr)!important;gap:14px!important;margin:0 0 72px!important}#admin-home-canonical-surface>.card,#admin-home-canonical-surface>[id$="-host"]{min-width:0!important;width:100%!important;max-width:100%!important}#page-admin-home #topbar{margin:0;max-width:100%}}',
    ].join('\n');

    document.head.appendChild(style);
  }

  function homePage() {
    return document.getElementById('page-admin-home');
  }

  function ensureSurface() {
    const home = homePage();
    if (!home) return null;

    let surface = document.getElementById('admin-home-canonical-surface');
    if (surface) return surface;

    surface = document.createElement('div');
    surface.id = 'admin-home-canonical-surface';
    surface.className = 'admin-runtime-grid';
    surface.setAttribute('data-admin-runtime-grid', '1');

    const section = home.querySelector(':scope > section.page');
    (section || home).appendChild(surface);
    return surface;
  }

  function ensureMarketplaceNavigationVisible() {
    const nav = document.getElementById('admin-marketplace-nav');
    if (!nav) return;
    nav.hidden = false;
    nav.removeAttribute('hidden');
    nav.dataset.authorityPresentation = 'visible-fail-closed';
    nav.title = 'Admin Market remains visible; backend platform-administrator authority is required for protected operations.';
  }

  function canonicalizeHomeCards() {
    const home = homePage();
    const surface = ensureSurface();
    if (!home || !surface) return;

    CANONICAL_CARD_IDS.forEach((id) => {
      const node = document.getElementById(id);
      if (!node || !home.contains(node) || node === surface) return;
      if (node.parentElement !== surface) surface.appendChild(node);
      node.style.position = 'static';
      node.style.transform = 'none';
      node.style.float = 'none';
      node.style.margin = '0';
      node.style.width = '100%';
      node.style.maxWidth = '100%';
      node.style.height = 'auto';
      node.style.overflow = 'auto';
    });

    home.querySelectorAll('.card').forEach((card) => {
      if (surface.contains(card)) return;
      const text = card.textContent || '';
      const legacy =
        card.id === 'admin-supervisor-home-console' ||
        text.includes('Protected Area') ||
        text.includes('PROTECTED AREA') ||
        text.includes('Checking admin session') ||
        text.includes('Supervisor Operations Center');
      if (legacy) card.remove();
    });

    home.querySelectorAll('[data-admin-runtime-grid]').forEach((grid) => {
      if (grid === surface) return;
      if (!grid.querySelector('.card,[id$="-host"]')) grid.remove();
    });
  }

  function removeLegacyReadinessSurfaces() {
    const integrationCenter = document.getElementById('page-admin-integration-center');
    if (!integrationCenter) return;
    ['admin-integration-readiness-card','admin-integration-readiness-case-management-host'].forEach((id) => {
      const duplicate = document.getElementById(id);
      if (duplicate && !integrationCenter.contains(duplicate)) duplicate.remove();
    });
  }

  function removeLegacyUsagePlaceholder() {
    const usagePage = document.getElementById('page-admin-usage');
    const analyticsHost = document.getElementById('admin-subscription-analytics-host');
    if (!usagePage || !analyticsHost || !usagePage.contains(analyticsHost)) return;
    usagePage.querySelectorAll('.card').forEach((card) => {
      const text = card.textContent || '';
      if (text.includes('Planned usage view:') || text.includes('evaluations used, evaluations remaining')) card.remove();
    });
  }

  function cleanHomeLayout() {
    installStyle();
    ensureMarketplaceNavigationVisible();
    canonicalizeHomeCards();
    removeLegacyReadinessSurfaces();
    removeLegacyUsagePlaceholder();
  }

  function observeDynamicSurfaces() {
    if (!document.body || window.PMK_ADMIN_HOME_CANONICAL_OBSERVER) return;
    const observer = new MutationObserver(() => {
      ensureMarketplaceNavigationVisible();
      canonicalizeHomeCards();
      removeLegacyReadinessSurfaces();
      removeLegacyUsagePlaceholder();
    });
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden'] });
    window.PMK_ADMIN_HOME_CANONICAL_OBSERVER = observer;
  }

  window.PMK_ADMIN_HOME_LAYOUT = {
    cleanHomeLayout,
    ensureSurface,
    ensureMarketplaceNavigationVisible,
    canonicalizeHomeCards,
    removeLegacyReadinessSurfaces,
    removeLegacyUsagePlaceholder,
  };

  function start() {
    cleanHomeLayout();
    observeDynamicSurfaces();
    [200, 800, 2000, 4000].forEach((delay) => setTimeout(cleanHomeLayout, delay));
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
