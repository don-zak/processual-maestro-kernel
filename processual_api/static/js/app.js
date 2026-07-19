const pageMeta = {
  overview:   { title: 'System Overview', sub: 'Kernel health, agents, and gateway status' },
  cgt:        { title: 'CGT Evaluator', sub: 'Compute fate vector from 12 parameters' },
  workflows:  { title: 'Workflow Registry', sub: 'Create, inspect, and govern workflows' },
  governance: { title: 'Governance Panel', sub: 'Policies, decisions, and safety boundaries' },
  telemetry:  { title: 'Telemetry', sub: 'Live metric streams and ingest' },
  reports:    { title: 'Reports & Evidence', sub: 'Fate reports, evidence packs, integrity' },
  governor:   { title: 'CGT Governor', sub: 'LLM output governance — rank, reward, policy' },
  gateway:    { title: 'Gateway Dashboard', sub: 'Agent registry, evaluation, lifecycle management' },
  simulation: { title: 'Supervision Simulation', sub: 'Virtual agent governance pipeline' },
  adapters:   { title: 'Adapter Manager', sub: 'Provider configuration and testing' },
  settings:   { title: 'Client Settings', sub: 'Account, preferences, plan, and support' },
};

const APP = (() => {
  /* ─── Shared State ─── */
  const gwAgents = [];
  const gwDecisionFeed = [];
  const rankColors = {
    flourishing: { c: '#22d3a0', bg: 'rgba(34,211,160,0.1)' },
    stable:      { c: '#4aaef5', bg: 'rgba(74,174,245,0.1)' },
    hybrid:      { c: '#a78bfa', bg: 'rgba(167,139,250,0.1)' },
    distorted:   { c: '#fb923c', bg: 'rgba(251,146,60,0.1)' },
    transient:   { c: '#fbbf24', bg: 'rgba(251,191,36,0.1)' },
    extinct:     { c: '#f87171', bg: 'rgba(248,113,113,0.1)' },
  };

  function getGwActionColor(action) {
    const m = { pass: '#22d3a0', repair: '#fbbf24', block: '#f87171', escalate: '#fb923c', freeze: '#60a5fa', activate: '#22d3a0', deactivate: '#f87171', rehabilitate: '#a78bfa' };
    return m[action] || '#8aa3c8';
  }

  /* ─── Toast System ─── */
  function showToast(msg, type) {
    type = type || 'info';
    const container = document.getElementById('toast-container');
    if (!container) return;
    const t = document.createElement('div');
    t.className = 'toast ' + type;
    t.textContent = msg;
    container.appendChild(t);
    requestAnimationFrame(() => t.classList.add('show'));
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, 3000);
  }

  /* ─── Loading Spinner ─── */
  function showLoading(btnId, text) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn._origText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> ' + (text || 'Loading...');
  }

  function hideLoading(btnId) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.disabled = false;
    btn.innerHTML = btn._origText || btn.innerHTML;
  }

  /* ─── Clock ─── */
  function tickClock() {
    const n = new Date();
    const tc = document.getElementById('clock-t');
    const td = document.getElementById('clock-d');
    if (tc) tc.textContent = n.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    if (td) td.textContent = n.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
  }

  /* ─── Navigation ─── */
  function navigateTo(pg) {
    const btn = document.querySelector('.nav-btn[data-page="' + pg + '"]');
    if (!btn) return;
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const pageEl = document.getElementById('page-' + pg);
    if (pageEl) pageEl.classList.add('active');
    const tt = document.getElementById('topbar-title');
    const ts = document.getElementById('topbar-sub');
    if (tt && pageMeta[pg]) tt.textContent = pageMeta[pg].title;
    if (ts && pageMeta[pg]) ts.textContent = pageMeta[pg].sub;
    window.location.hash = 'page-' + pg;
    if (pg === 'settings') { PAGES.settings?.init?.(); }
    if (pg === 'institution') { PAGES.institution?.init?.(); }
    if (pg === 'gateway') {
      PAGES.gateway?.refresh();
      setTimeout(() => {
        CHARTS.drawGauge('gw-gauge', parseFloat(document.getElementById('gw-avg-reward')?.textContent) || 0, -2, 2);
        CHARTS.drawStateDiagram('gw-state-diagram', APP.gwAgents.map(a => a.state));
      }, 100);
    }
    if (pg === 'overview') {
      PAGES.overview?.refresh();
      setTimeout(() => CHARTS.drawStateDiagram('state-diagram', APP.gwAgents.map(a => a.state)), 100);
    }
    if (pg === 'governor') { PAGES.governor?.refresh(); }
    if (pg === 'simulation') { PAGES.simulation?.refresh(); }
    if (pg === 'adapters') { PAGES.adapters?.refresh(); }
  }

  function initNav() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.addEventListener('click', () => navigateTo(btn.dataset.page));
    });
  }

  /* ─── Keyboard Shortcuts ─── */
  function initKeyboard() {
    document.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
      const navKeys = { '1':'overview','2':'cgt','3':'workflows','4':'governance','5':'telemetry','6':'reports','7':'governor','8':'gateway','9':'simulation','0':'adapters','-':'settings' };
      const pg = navKeys[e.key];
      if (pg) {
        const btn = document.querySelector('.nav-btn[data-page="' + pg + '"]');
        if (btn) btn.click();
      }
      if (e.key === 'r' || e.key === 'R') {
        const btn = document.getElementById('gw-reg-btn');
        if (btn && document.getElementById('page-gateway')?.classList.contains('active')) btn.click();
      }
      if (e.key === 'e' || e.key === 'E') {
        const btn = document.getElementById('gw-eval-btn');
        if (btn && document.getElementById('page-gateway')?.classList.contains('active')) btn.click();
      }
    });
  }

  /* ─── RTL Toggle ─── */
  function initRtlToggle() {
    const btn = document.getElementById('lang-toggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
      I18N.toggle();
      btn.textContent = I18N.lang() === 'ar' ? 'EN' : 'AR';
      document.body.dir = I18N.lang() === 'ar' ? 'rtl' : 'ltr';
      showToast('Language: ' + I18N.lang().toUpperCase(), 'info');
    });
  }

  /* ─── Subscription Banner ─── */
  async function checkSubscription() {
    const banner = document.getElementById('sub-banner');
    if (!banner) return;
    try {
      const sub = await CLIENT.get('/settings/subscription');
      const stage = sub.stage || 'active';
      const plan = sub.plan || '—';
      const status = sub.status || 'active';

      if (stage === 'active') {
        banner.style.display = 'none';
        return;
      }

      banner.style.display = 'block';

      if (stage === 'grace') {
        banner.style.backgroundColor = 'rgba(251,191,36,0.1)';
        banner.style.borderColor = 'rgba(251,191,36,0.3)';
        banner.style.color = '#fbbf24';
        banner.innerHTML = '⚠ Payment overdue — service is <strong>read-only</strong>. <a href="/billing/portal" style="color:#fbbf24;text-decoration:underline">Update billing →</a>';
      } else if (stage === 'suspended') {
        banner.style.backgroundColor = 'rgba(248,113,113,0.1)';
        banner.style.borderColor = 'rgba(248,113,113,0.3)';
        banner.style.color = '#f87171';
        banner.innerHTML = '✖ Subscription suspended — <a href="/billing/portal" style="color:#f87171;text-decoration:underline">Reactivate now →</a>';
      } else if (stage === 'expired') {
        banner.style.backgroundColor = 'rgba(248,113,113,0.15)';
        banner.style.borderColor = 'rgba(248,113,113,0.4)';
        banner.style.color = '#ef4444';
        banner.innerHTML = '✖ Subscription expired — please <a href="/pricing" style="color:#ef4444;text-decoration:underline">re-subscribe</a>.';
      }
    } catch (e) {
      // silently ignore — banner just won't show
    }
  }

  /* ─── Init ─── */
  function hasDescentGateSession() {
    return sessionStorage.getItem('maestro_descent_gate_seen') === '1';
  }

  function init() {
    if (!hasDescentGateSession()) {
      window.location.replace('/');
      return;
    }

    AUTH.init();
    tickClock(); setInterval(tickClock, 1000);
    initNav();
    initKeyboard();
    initRtlToggle();

    const lt = document.getElementById('lang-toggle');
    if (lt) lt.textContent = I18N.lang() === 'ar' ? 'EN' : 'AR';

    if (!AUTH.isLoggedIn()) {
      window.location.replace('/login');
      return;
    }
    checkSubscription();
    loadInitialPage();
  }

  function loadInitialPage() {
    const hash = window.location.hash.replace('#page-', '');
    if (hash && pageMeta[hash]) {
      navigateTo(hash);
    } else {
      PAGES.overview?.refresh();
    }
  }

  return {
    gwAgents, gwDecisionFeed, rankColors, getGwActionColor,
    showToast, showLoading, hideLoading,
    init
  };
})();

(function bootstrapInstitutionWorkspace18() {
  pageMeta.institution = {
    title: 'Institution Workspace',
    sub: 'Integration requirements, submissions, actions, sandbox progress, and credential status',
  };

  const navWrap = document.getElementById('nav-wrap');
  if (navWrap && !navWrap.querySelector('[data-page="institution"]')) {
    const settingsButton = navWrap.querySelector('[data-page="settings"]');
    const button = document.createElement('button');
    button.className = 'nav-btn';
    button.dataset.page = 'institution';
    button.innerHTML = '<span class="nav-ind"></span><span class="nav-ico">◇</span><span>Institution</span>';
    navWrap.insertBefore(button, settingsButton || null);
  }

  const content = document.getElementById('content');
  if (content && !document.getElementById('page-institution')) {
    const page = document.createElement('div');
    page.className = 'page';
    page.id = 'page-institution';
    page.innerHTML = '<div id="institution-workspace-root"><div class="iw18-empty">Loading institution workspace…</div></div>';
    content.appendChild(page);
  }

  if (!document.querySelector('link[data-iw18-style]')) {
    const style = document.createElement('link');
    style.rel = 'stylesheet';
    style.href = 'css/institution_workspace_18.css?v=stage18r1';
    style.dataset.iw18Style = 'true';
    document.head.appendChild(style);
  }

  if (!document.querySelector('script[data-iw18-script]')) {
    const script = document.createElement('script');
    script.src = 'js/pages/institution_workspace_18.js?v=stage18r1';
    script.dataset.iw18Script = 'true';
    document.body.appendChild(script);
  }
})();
