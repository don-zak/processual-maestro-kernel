(function () {
  function installStyle() {
    if (document.getElementById('admin-home-layout-style')) return;

    const style = document.createElement('style');
    style.id = 'admin-home-layout-style';
    style.textContent = [
      '#page-admin-home{padding:24px 28px 96px!important;overflow:visible!important;overflow-x:hidden!important}',
      '#page-admin-home .card{box-sizing:border-box;max-width:100%!important}',
      '#page-admin-home > section.page{display:flex!important;flex-direction:column!important;gap:24px!important;position:static!important;float:none!important;height:auto!important;min-height:0!important;min-width:0!important;max-width:100%!important;overflow:visible!important;transform:none!important}',
      '#page-admin-home > section.page > *{position:static!important;float:none!important;transform:none!important;inset:auto!important;left:auto!important;right:auto!important;top:auto!important;bottom:auto!important;min-width:0!important;max-width:100%!important;flex:none!important}',
      '#page-admin-home .grid-2-eq{display:grid!important;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))!important;gap:24px!important;position:static!important;float:none!important;height:auto!important;min-height:0!important;min-width:0!important;max-width:100%!important;overflow:visible!important;transform:none!important}',
      '#page-admin-home .grid-2-eq > .card,#admin-program-supervision-readiness,#admin-supervisor-overview-counters{position:static!important;transform:none!important;float:none!important;inset:auto!important;left:auto!important;right:auto!important;top:auto!important;bottom:auto!important;width:auto!important;max-width:100%!important;clear:both!important;margin:0!important;height:auto!important}',
      '#page-admin-home .mono-block,#page-admin-home .admin-note{max-width:100%;overflow-wrap:anywhere}',
      '#admin-program-supervision-readiness,#admin-supervisor-overview-counters{overflow:auto!important}',
      '#admin-home-runtime-surface{display:grid!important;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:24px;margin:0 0 72px!important;align-items:start;clear:both;position:static!important;float:none!important;z-index:auto!important;min-width:0;max-width:100%;height:auto!important;transform:none!important}',
      '#admin-home-runtime-surface .card{position:static!important;transform:none!important;margin:0!important;width:auto!important;max-width:100%!important;max-height:560px;min-height:260px;overflow:auto!important}',
      '#admin-home-runtime-surface .admin-data-table{min-width:520px}',
      '#admin-home-runtime-surface .admin-kpi-grid{grid-template-columns:repeat(auto-fit,minmax(140px,1fr))}',
      '#page-admin-home [data-admin-runtime-grid]:not(#admin-home-runtime-surface){display:contents}',
      'main{height:calc(100vh - 76px);overflow:auto!important;overflow-x:hidden!important;padding-bottom:96px!important}',
      '@media (max-width:980px){#page-admin-home .grid-2-eq,#admin-home-runtime-surface{grid-template-columns:1fr!important}}',
      '@media (max-width:600px){#page-admin-home{padding:12px 8px 72px!important;overflow-x:hidden!important}#page-admin-home > section.page{gap:14px!important}#page-admin-home .grid-2-eq{grid-template-columns:minmax(0,1fr)!important;gap:14px!important}#admin-home-runtime-surface{grid-template-columns:minmax(0,1fr)!important;gap:14px;margin:0 0 72px!important;max-width:100%;overflow:hidden}#admin-home-runtime-surface .card{min-width:0!important;width:100%!important;max-width:100%!important;min-height:0}#admin-home-runtime-surface .admin-data-table{min-width:0;width:100%;display:block;overflow-x:auto}#admin-home-runtime-surface .admin-kpi-grid{grid-template-columns:minmax(0,1fr)}#page-admin-home #topbar{margin:0;max-width:100%}}',
    ].join('\n');

    document.head.appendChild(style);
  }

  function homePage() {
    return document.getElementById('page-admin-home');
  }

  function findOverviewAnchor(home) {
    const explicit = document.getElementById('admin-operations-overview-card');
    if (explicit && home.contains(explicit)) return explicit;

    const cards = Array.from(home.querySelectorAll('.card'));
    return (
      cards.find((card) => (card.textContent || '').includes('ADMIN OPERATIONS OVERVIEW')) ||
      cards.find((card) => (card.textContent || '').includes('Admin overview aligned')) ||
      null
    );
  }

  function ensureSurface() {
    const home = homePage();
    if (!home) return null;

    let surface = document.getElementById('admin-home-runtime-surface');
    if (surface) return surface;

    surface = document.createElement('div');
    surface.id = 'admin-home-runtime-surface';
    surface.className = 'admin-runtime-grid';
    surface.setAttribute('data-admin-runtime-grid', '1');

    const section = home.querySelector(':scope > section.page');
    if (section) {
      section.appendChild(surface);
    } else {
      home.appendChild(surface);
    }

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

  function observeMarketplaceNavigationVisibility() {
    const nav = document.getElementById('admin-marketplace-nav');
    if (!nav || window.PMK_ADMIN_MARKETPLACE_NAV_VISIBILITY_OBSERVER) return;

    const observer = new MutationObserver(() => {
      if (nav.hidden || nav.hasAttribute('hidden')) {
        ensureMarketplaceNavigationVisible();
      }
    });
    observer.observe(nav, { attributes: true, attributeFilter: ['hidden'] });
    window.PMK_ADMIN_MARKETPLACE_NAV_VISIBILITY_OBSERVER = observer;
  }

  function isWantedHomeRuntimeCard(card) {
    return card.id === 'admin-runtime-home-summary' || card.id === 'admin-runtime-auth-state';
  }

  function moveHomeRuntimeCards() {
    const home = homePage();
    const surface = ensureSurface();
    if (!home || !surface) return;

    Array.from(home.querySelectorAll('#admin-runtime-home-summary,#admin-runtime-auth-state')).forEach((card) => {
      if (card.parentElement !== surface) {
        surface.appendChild(card);
      }

      card.style.position = 'static';
      card.style.transform = 'none';
      card.style.margin = '0';
      card.style.width = 'auto';
      card.style.maxHeight = '560px';
      card.style.overflow = 'auto';
    });
  }

  function removeLegacyReadinessSurfaces() {
    const integrationCenter = document.getElementById('page-admin-integration-center');
    if (!integrationCenter) return;

    [
      'admin-integration-readiness-card',
      'admin-integration-readiness-case-management-host',
    ].forEach((id) => {
      const duplicate = document.getElementById(id);
      if (duplicate && !integrationCenter.contains(duplicate)) {
        duplicate.remove();
      }
    });
  }

  function removeLegacyUsagePlaceholder() {
    const usagePage = document.getElementById('page-admin-usage');
    const analyticsHost = document.getElementById('admin-subscription-analytics-host');
    if (!usagePage || !analyticsHost || !usagePage.contains(analyticsHost)) return;

    usagePage.querySelectorAll('.card').forEach((card) => {
      const text = card.textContent || '';
      if (
        text.includes('Planned usage view:') ||
        text.includes('evaluations used, evaluations remaining')
      ) {
        const wrapper = card.parentElement;
        card.remove();
        if (wrapper && wrapper !== usagePage && !wrapper.querySelector('.card')) {
          const heading = wrapper.querySelector('.sec-hdr');
          if (heading) heading.remove();
          if (!wrapper.textContent.trim()) wrapper.remove();
        }
      }
    });
  }

  function removeHomeDuplicatesAndEmptyGrids() {
    const home = homePage();
    const surface = document.getElementById('admin-home-runtime-surface');
    if (!home || !surface) return;

    home.querySelectorAll('.card').forEach((card) => {
      if (isWantedHomeRuntimeCard(card)) return;

      const text = card.textContent || '';
      const isLegacyAuthCard =
        text.includes('PROTECTED AREA') ||
        text.includes('Protected Area') ||
        text.includes('Checking admin session') ||
        text.includes('Admin auth token missing') ||
        text.includes('Backend scopes remain the authority');
      const isDuplicateNavigationCard =
        card.id === 'admin-supervisor-home-console' ||
        text.includes('Supervisor Operations Center');

      if (isLegacyAuthCard || isDuplicateNavigationCard) {
        card.remove();
      }
    });

    home.querySelectorAll('[data-admin-runtime-grid]').forEach((grid) => {
      if (grid.id === 'admin-home-runtime-surface') return;
      if (!grid.querySelector('.card')) {
        grid.remove();
      }
    });
  }

  function cleanHomeLayout() {
    installStyle();
    ensureMarketplaceNavigationVisible();
    observeMarketplaceNavigationVisibility();
    removeHomeDuplicatesAndEmptyGrids();
    moveHomeRuntimeCards();
    removeLegacyReadinessSurfaces();
    removeLegacyUsagePlaceholder();
  }

  function observeLegacySurfaceRecreation() {
    if (!document.body || window.PMK_ADMIN_SURFACE_OWNERSHIP_OBSERVER) return;

    const observer = new MutationObserver(() => {
      ensureMarketplaceNavigationVisible();
      removeLegacyReadinessSurfaces();
      removeLegacyUsagePlaceholder();
    });
    observer.observe(document.body, { childList: true, subtree: true });
    window.PMK_ADMIN_SURFACE_OWNERSHIP_OBSERVER = observer;
  }

  window.PMK_ADMIN_HOME_LAYOUT = {
    cleanHomeLayout,
    ensureSurface,
    ensureMarketplaceNavigationVisible,
    moveHomeRuntimeCards,
    removeLegacyReadinessSurfaces,
    removeLegacyUsagePlaceholder,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      cleanHomeLayout();
      observeLegacySurfaceRecreation();
      setTimeout(cleanHomeLayout, 200);
      setTimeout(cleanHomeLayout, 800);
      setTimeout(cleanHomeLayout, 2000);
      setTimeout(cleanHomeLayout, 4000);
    });
  } else {
    cleanHomeLayout();
    observeLegacySurfaceRecreation();
    setTimeout(cleanHomeLayout, 200);
    setTimeout(cleanHomeLayout, 800);
    setTimeout(cleanHomeLayout, 2000);
    setTimeout(cleanHomeLayout, 4000);
  }
})();
