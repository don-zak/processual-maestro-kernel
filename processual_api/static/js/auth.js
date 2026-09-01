const AUTH = (() => {
  const STORAGE_KEY = 'maestro_token';

  let _currentUser = null;

  function init() {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem('maestro_role');

    const saved = sessionStorage.getItem(STORAGE_KEY);
    if (saved) {
      CLIENT.setToken(saved);
      _currentUser = { token: saved };
    }
    CLIENT.onUnauthorized(() => { logout(); });
  }

  async function login(username, password) {
    const res = await CLIENT.post('/auth/token', { username, password });
    const token = res.access_token;
    CLIENT.setToken(token);
    sessionStorage.setItem(STORAGE_KEY, token);
    sessionStorage.setItem('maestro_ui_session_started_at', new Date().toISOString());
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem('maestro_role');

    _currentUser = { token };
    return token;
  }

  function logout() {
    CLIENT.clearToken();
    sessionStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem('maestro_role');
    sessionStorage.removeItem('maestro_entry_mode');
    sessionStorage.removeItem('maestro_ui_session_started_at');
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem('maestro_role');
    _currentUser = null;
  }

  function isLoggedIn() { return !!_currentUser; }
  function currentUser() { return _currentUser; }

  async function me() {
    try {
      return await CLIENT.get('/auth/me');
    } catch (e) {
      if (e.status === 401) logout();
      throw e;
    }
  }

  return { init, login, logout, isLoggedIn, currentUser, me };
})();

(function loadShowcaseEnhancements() {
  if (!document.querySelector('script[data-maestro-showcase-v2]')) {
    const showcase = document.createElement('script');
    showcase.src = 'js/showcase_v2.js?v=showcase-v2-p1';
    showcase.dataset.maestroShowcaseV2 = 'true';
    document.body.appendChild(showcase);
  }

  if (!document.querySelector('script[data-maestro-decision-journey]')) {
    const journey = document.createElement('script');
    journey.src = 'js/showcase_decision_journey.js?v=decision-journey-p2';
    journey.dataset.maestroDecisionJourney = 'true';
    document.body.appendChild(journey);
  }
})();