
document.addEventListener('DOMContentLoaded', () => {
  async function checkAdminSession() {
    const protectedBlocks = Array.from(document.querySelectorAll('.mono-block')).filter((el) =>
      (el.textContent || '').includes('Checking admin session')
    );

    function writeProtected(message) {
      protectedBlocks.forEach((el) => {
        el.textContent = message;
      });
    }

    try {
      const headers =
        window.PMK_ADMIN_AUTH && typeof PMK_ADMIN_AUTH.headers === 'function'
          ? PMK_ADMIN_AUTH.headers()
          : new Headers({ 'Content-Type': 'application/json' });

      if (!headers.has('Authorization') && !headers.has('X-API-Key')) {
        document.body.dataset.adminSession = 'auth-missing';
        writeProtected('Admin auth token missing. Login did not persist a Bearer token for admin API calls.');
        return;
      }

      const response = await fetch('/auth/me', {
        method: 'GET',
        credentials: 'include',
        headers,
      });

      if (!response.ok) {
        document.body.dataset.adminSession = 'error-' + response.status;
        writeProtected('Admin session check failed: HTTP ' + response.status);
        return;
      }

      const me = await response.json();
      const role = me.role || me.user_role || me.account_role || (me.user && me.user.role) || '';
      const scopes = me.scopes || me.permissions || [];
      const isAdmin =
        role === 'admin' ||
        role === 'administrator' ||
        scopes.includes('admin') ||
        scopes.includes('admin:settings');

      if (!isAdmin) {
        document.body.dataset.adminSession = 'not-admin';
        writeProtected('Session exists, but admin scope was not found.');
        return;
      }

      document.body.dataset.adminSession = 'ok';
      writeProtected('Admin session verified. Backend scopes remain the authority.');
    } catch (error) {
      document.body.dataset.adminSession = 'error';
      writeProtected('Admin session check failed: ' + (error.message || String(error)));
    }
  }

  checkAdminSession();
});
