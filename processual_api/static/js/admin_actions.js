(function () {
  function clearAuthState() {
    const keys = [
      'token',
      'access_token',
      'auth_token',
      'maestro_token',
      'maestro_auth_token',
      'pmk_token',
      'pmk_auth_token',
      'user',
      'role',
    ];

    keys.forEach((key) => {
      try { localStorage.removeItem(key); } catch (error) {}
      try { sessionStorage.removeItem(key); } catch (error) {}
    });

    try {
      document.cookie.split(';').forEach((cookie) => {
        const name = cookie.split('=')[0].trim();
        if (!name) return;
        document.cookie = name + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/';
      });
    } catch (error) {}
  }

  function openClientConsole() {
    window.location.assign('/console');
  }

  async function logout() {
    try {
      if (window.CLIENT && typeof CLIENT.post === 'function') {
        await CLIENT.post('/auth/logout', {});
      }
    } catch (error) {
      // Backend logout route is optional; client-side cleanup still runs.
    }

    clearAuthState();
    window.location.replace('/login?mode=admin');
  }

  function loadAdminMarketplaceCatalog() {
    if (document.querySelector('script[data-admin-marketplace-catalog]')) return;
    const script = document.createElement('script');
    script.src = '/console/js/admin_marketplace_catalog.js?v=a3-original-offers-1';
    script.defer = true;
    script.dataset.adminMarketplaceCatalog = 'true';
    document.head.appendChild(script);
  }

  function bindAdminActions() {
    const clientButton = document.getElementById('admin-client-console-btn');
    const logoutButton = document.getElementById('admin-logout-btn');

    if (clientButton) {
      clientButton.addEventListener('click', (event) => {
        event.preventDefault();
        openClientConsole();
      });
    }

    if (logoutButton) {
      logoutButton.addEventListener('click', (event) => {
        event.preventDefault();
        logout();
      });
    }

    loadAdminMarketplaceCatalog();
  }

  window.PMK_ADMIN_ACTIONS = {
    bindAdminActions,
    clearAuthState,
    loadAdminMarketplaceCatalog,
    logout,
    openClientConsole,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindAdminActions);
  } else {
    bindAdminActions();
  }
})();
