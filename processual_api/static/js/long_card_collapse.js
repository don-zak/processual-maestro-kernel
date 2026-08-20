(() => {
  const STYLE_ID = 'pmk-long-card-collapse-style';
  const TOOLS_CLASS = 'pmk-long-card-tools';
  const BUTTON_CLASS = 'pmk-long-card-toggle';
  const SEMANTIC_DESCENDANT_SELECTOR = '[class*="card"],[class*="panel"],[class*="hero"],[class*="tile"],#admin-integration-readiness-tracking-summary-card';
  const CANDIDATE_SELECTOR = '#content [class*="card"],#content [class*="panel"],#content [class*="hero"],#content [class*="tile"],.admin-page [class*="card"],.admin-page [class*="panel"],.admin-page [class*="hero"],.admin-page [class*="tile"],.admin-card,.settings-card,#admin-integration-readiness-tracking-summary-card';
  const CARD_HINT = /(\b|[-_])(card|panel|hero|tile)(\b|[-_])/i;
  const KNOWN_CARD_IDS = new Set(['admin-integration-readiness-tracking-summary-card']);
  const observedForResize = new WeakSet();

  function longThreshold() {
    return window.innerWidth <= 600 ? 420 : 520;
  }

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .pmk-long-card-tools { display:flex; justify-content:flex-end; align-items:center; gap:.4rem; margin:0 0 .55rem; }
      .pmk-long-card-toggle { min-height:30px; padding:.28rem .65rem; border-radius:999px; border:1px solid rgba(148,163,184,.42); background:rgba(15,23,42,.72); color:#eaf2ff; font:inherit; font-size:.78rem; font-weight:700; line-height:1.1; cursor:pointer; }
      .pmk-long-card-toggle:hover { border-color:rgba(191,219,254,.72); background:rgba(30,41,59,.9); }
      .pmk-long-card-toggle:focus-visible { outline:2px solid currentColor; outline-offset:2px; }
      [data-pmk-long-card="true"][data-pmk-collapsed="true"] { overflow:hidden!important; }
      @media (max-width:600px) {
        .pmk-long-card-tools { position:sticky; top:0; z-index:3; padding-top:.1rem; background:inherit; }
        .pmk-long-card-toggle { min-height:34px; padding-inline:.75rem; }
      }
    `;
    document.head.appendChild(style);
  }

  function visible(card) {
    return Boolean(card.offsetParent) && card.getClientRects().length > 0;
  }

  function classAndId(card) {
    return `${card.id || ''} ${typeof card.className === 'string' ? card.className : ''}`.trim();
  }

  function isKnownCard(card) {
    return Boolean(card.id) && KNOWN_CARD_IDS.has(card.id);
  }

  function isSemanticCard(card) {
    if (!(card instanceof HTMLElement)) return false;
    if (isKnownCard(card)) return true;
    return CARD_HINT.test(classAndId(card));
  }

  function isStructuralHostPanel(card) {
    return card.matches('.admin-panel') && Boolean(card.querySelector(SEMANTIC_DESCENDANT_SELECTOR));
  }

  function hasDominantSemanticChild(card) {
    const threshold = longThreshold();
    const ownHeight = Math.max(1, card.getBoundingClientRect().height);
    return Array.from(card.querySelectorAll(SEMANTIC_DESCENDANT_SELECTOR)).some((child) => {
      if (!(child instanceof HTMLElement) || !visible(child) || !isSemanticCard(child)) return false;
      const childHeight = child.getBoundingClientRect().height;
      return child.scrollHeight >= threshold && childHeight >= ownHeight * 0.72;
    });
  }

  function visuallyCardLike(card) {
    if (!(card instanceof HTMLElement)) return false;
    if (!visible(card) || !isSemanticCard(card)) return false;
    if (isStructuralHostPanel(card)) return false;
    if (card.scrollHeight < longThreshold()) return false;
    if (card.children.length < 2) return false;
    if (card.matches('#content,#main,.page,.admin-page,.sl18-panel')) return false;
    if (card.closest('[data-pmk-long-card="true"]')) return false;
    if (hasDominantSemanticChild(card)) return false;
    return true;
  }

  function directHeader(card) {
    return Array.from(card.children).find((child) => child.matches('h1,h2,h3,h4,.sec-hdr,.admin-card-header,.settings-card-header,.mbs-head,[data-card-header]')) || null;
  }

  function rememberPresentation(child) {
    if (child.hasAttribute('data-pmk-collapse-prev-hidden')) return;
    child.setAttribute('data-pmk-collapse-prev-hidden', child.hidden ? 'true' : 'false');
    child.setAttribute('data-pmk-collapse-prev-display', child.style.getPropertyValue('display'));
    child.setAttribute('data-pmk-collapse-prev-display-priority', child.style.getPropertyPriority('display'));
  }

  function hideChild(child) {
    rememberPresentation(child);
    child.hidden = true;
    child.style.setProperty('display', 'none', 'important');
  }

  function restoreChild(child) {
    const previousHidden = child.getAttribute('data-pmk-collapse-prev-hidden');
    if (previousHidden === null) return;
    const previousDisplay = child.getAttribute('data-pmk-collapse-prev-display') || '';
    const previousPriority = child.getAttribute('data-pmk-collapse-prev-display-priority') || '';
    child.style.removeProperty('display');
    if (previousDisplay) child.style.setProperty('display', previousDisplay, previousPriority);
    child.hidden = previousHidden === 'true';
    child.removeAttribute('data-pmk-collapse-prev-hidden');
    child.removeAttribute('data-pmk-collapse-prev-display');
    child.removeAttribute('data-pmk-collapse-prev-display-priority');
  }

  function setCollapsed(card, collapsed) {
    const tools = card.querySelector(`:scope > .${TOOLS_CLASS}`);
    const button = tools?.querySelector(`.${BUTTON_CLASS}`);
    const header = directHeader(card);
    card.dataset.pmkCollapsed = collapsed ? 'true' : 'false';
    if (button) {
      button.textContent = collapsed ? 'Expand' : 'Collapse';
      button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    }
    Array.from(card.children).forEach((child) => {
      if (child === tools || child === header) return;
      if (collapsed) hideChild(child);
      else restoreChild(child);
    });
  }

  function enhance(card) {
    if (!(card instanceof HTMLElement)) return;
    if (card.dataset.pmkLongCard === 'true' || !visuallyCardLike(card)) return;
    ensureStyle();
    card.dataset.pmkLongCard = 'true';
    card.dataset.pmkCollapsed = 'false';
    const tools = document.createElement('div');
    tools.className = TOOLS_CLASS;
    tools.setAttribute('data-pmk-long-card-tools', 'true');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = BUTTON_CLASS;
    button.textContent = 'Collapse';
    button.setAttribute('aria-expanded', 'true');
    button.setAttribute('aria-label', 'Collapse long card');
    button.addEventListener('click', () => {
      const next = card.dataset.pmkCollapsed !== 'true';
      setCollapsed(card, next);
      button.setAttribute('aria-label', next ? 'Expand long card' : 'Collapse long card');
    });
    tools.appendChild(button);
    card.insertBefore(tools, card.firstChild);
  }

  const resizeObserver = typeof ResizeObserver === 'function' ? new ResizeObserver((entries) => entries.forEach((entry) => enhance(entry.target))) : null;

  function observeCandidate(card) {
    if (!resizeObserver || observedForResize.has(card) || !isSemanticCard(card)) return;
    observedForResize.add(card);
    resizeObserver.observe(card);
  }

  function scan(root = document) {
    root.querySelectorAll?.(CANDIDATE_SELECTOR).forEach((card) => {
      observeCandidate(card);
      enhance(card);
    });
  }

  let scheduled = false;
  function scheduleScan() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      scan();
    });
  }

  function scheduleVisibilityScans() {
    scheduleScan();
    window.setTimeout(scheduleScan, 100);
    window.setTimeout(scheduleScan, 300);
  }

  document.addEventListener('DOMContentLoaded', () => {
    scan();
    window.setTimeout(scan, 250);
    window.setTimeout(scan, 900);
    window.setTimeout(scan, 1800);
    const observer = new MutationObserver(scheduleScan);
    observer.observe(document.body, { childList:true, subtree:true, characterData:true, attributes:true, attributeFilter:['class','style','hidden'] });
    document.addEventListener('click', (event) => {
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest('.nav-btn[data-page],.nav-btn[data-admin-page],[data-am-section],.sl18-tab')) scheduleVisibilityScans();
    }, true);
    window.addEventListener('hashchange', scheduleVisibilityScans);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) scheduleVisibilityScans(); });
  });
})();
