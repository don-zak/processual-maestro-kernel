
(function () {
  function installStyle() {
    if (document.getElementById('admin-home-layout-style')) return;

    const style = document.createElement('style');
    style.id = 'admin-home-layout-style';
    style.textContent = [
      '#page-admin-home{padding:24px 28px 96px!important;overflow:visible!important}',
      '#page-admin-home .card{box-sizing:border-box}',
      '#admin-home-runtime-surface{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:24px;margin:28px 0 96px;align-items:start;clear:both;position:relative;z-index:30}',
      '#admin-home-runtime-surface .card{position:static!important;transform:none!important;margin:0!important;width:auto!important;max-height:560px;min-height:260px;overflow:auto!important}',
      '#admin-home-runtime-surface .admin-data-table{min-width:520px}',
      '#admin-home-runtime-surface .admin-kpi-grid{grid-template-columns:repeat(auto-fit,minmax(140px,1fr))}',
      '#page-admin-home [data-admin-runtime-grid]:not(#admin-home-runtime-surface){display:contents}',
      'main{height:calc(100vh - 76px);overflow:auto!important;padding-bottom:96px!important}',
      '@media (max-width:980px){#admin-home-runtime-surface{grid-template-columns:1fr}}',
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

    const anchor = findOverviewAnchor(home);

    if (anchor && anchor.parentElement) {
      anchor.insertAdjacentElement('afterend', surface);
    } else {
      home.appendChild(surface);
    }

    return surface;
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

  function removeHomeRuntimeDuplicatesAndEmptyGrids() {
    const home = homePage();
    const surface = document.getElementById('admin-home-runtime-surface');

    if (!home || !surface) return;

    home.querySelectorAll('.card').forEach((card) => {
      if (isWantedHomeRuntimeCard(card)) return;

      const text = card.textContent || '';
      const isLegacy =
        text.includes('PROTECTED AREA') ||
        text.includes('Protected Area') ||
        text.includes('Checking admin session') ||
        text.includes('Admin auth token missing') ||
        text.includes('Backend scopes remain the authority');

      if (isLegacy) {
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
    moveHomeRuntimeCards();
    removeHomeRuntimeDuplicatesAndEmptyGrids();
  }

  window.PMK_ADMIN_HOME_LAYOUT = {
    cleanHomeLayout,
    ensureSurface,
    moveHomeRuntimeCards,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      cleanHomeLayout();
      setTimeout(cleanHomeLayout, 200);
      setTimeout(cleanHomeLayout, 800);
      setTimeout(cleanHomeLayout, 2000);
      setTimeout(cleanHomeLayout, 4000);
    });
  } else {
    cleanHomeLayout();
    setTimeout(cleanHomeLayout, 200);
    setTimeout(cleanHomeLayout, 800);
    setTimeout(cleanHomeLayout, 2000);
    setTimeout(cleanHomeLayout, 4000);
  }
})();
