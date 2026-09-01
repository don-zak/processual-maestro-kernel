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
  const scripts = [
    ['data-maestro-showcase-v2', 'js/showcase_v2.js?v=showcase-v2-p1'],
    ['data-maestro-decision-journey', 'js/showcase_decision_journey.js?v=decision-journey-p5'],
    ['data-maestro-decision-receipt', 'js/showcase_decision_receipt.js?v=decision-receipt-p5'],
    ['data-maestro-decision-motion', 'js/showcase_decision_motion.js?v=decision-motion-p2'],
    ['data-maestro-guided-flow', 'js/showcase_guided_flow.js?v=guided-flow-p5'],
    ['data-maestro-cinematic-transitions', 'js/showcase_cinematic_transitions.js?v=cinematic-p4'],
  ];

  scripts.forEach(([attribute, src]) => {
    if (document.querySelector(`script[${attribute}]`)) return;
    const script = document.createElement('script');
    script.src = src;
    script.setAttribute(attribute, 'true');
    document.body.appendChild(script);
  });
})();