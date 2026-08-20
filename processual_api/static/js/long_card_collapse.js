(() => {
  const STYLE_ID = 'pmk-long-card-collapse-style';
  const TOOLS_CLASS = 'pmk-long-card-tools';
  const BUTTON_CLASS = 'pmk-long-card-toggle';
  const CANDIDATE_SELECTOR = '#content div,#content section,#content article,.admin-page div,.admin-page section,.admin-page article';
  const WRAPPER_HINT = /(\b|[-_])(page|grid|layout|root|host|shell|wrapper|container|content|nav|tabs|panels)(\b|[-_])/i;
  const CARD_HINT = /(\b|[-_])(card|panel|hero|summary|tile|block)(\b|[-_])/i;
  const observedForResize = new WeakSet();

  function longThreshold() {
    return window.innerWidth <= 600 ? 420 : 520;
  }

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .pmk-long-card-tools {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 0.4rem;
        margin: 0 0 0.55rem;
      }
      .pmk-long-card-toggle {
        min-height: 30px;
        padding: 0.28rem 0.65rem;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.42);
        background: rgba(15, 23, 42, 0.72);
        color: #eaf2ff;
        font: inherit;
        font-size: 0.78rem;
        font-weight: 700;
        line-height: 1.1;
        cursor: pointer;
      }
      .pmk-long-card-toggle:hover {
        border-color: rgba(191, 219, 254, 0.72);
        background: rgba(30, 41, 59, 0.9);
      }
      .pmk-long-card-toggle:focus-visible {
        outline: 2px solid currentColor;
        outline-offset: 2px;
      }
      [data-pmk-long-card="true"][data-pmk-collapsed="true"] {
        overflow: hidden !important;
      }
      @media (max-width: 600px) {
        .pmk-long-card-tools {
          position: sticky;
          top: 0;
          z-index: 3;
          padding-top: 0.1rem;
          background: inherit;
        }
        .pmk-long-card-toggle {
          min-height: 34px;
          padding-inline: 0.75rem;
        }
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

  function likelySurfaceCandidate(card) {
    if (!(card instanceof HTMLElement)) return false;
    if (card.matches('#content,#main,.page,.admin-page,.sl18-panel')) return false;
    const identity = classAndId(card);
    if (CARD_HINT.test(identity)) return true;
    if (card.matches('section,article')) return true;
    if (card.children.length < 2) return false;
    const style = getComputedStyle(card);
    const radius = Number.parseFloat(style.borderTopLeftRadius || '0') || 0;
    const border = Number.parseFloat(style.borderTopWidth || '0') || 0;
    return radius >= 6 || border > 0;
  }

  function visuallyCardLike(card) {
    if (!(card instanceof HTMLElement)) return false;
    if (!visible(card)) return false;
    const threshold = longThreshold();
    if (card.scrollHeight < threshold) return false;
    if (card.children.length < 2) return false;
    if (card.matches('#content,#main,.page,.admin-page,.sl18-panel')) return false;

    const identity = classAndId(card);
    if (WRAPPER_HINT.test(identity) && !CARD_HINT.test(identity)) return false;

    const style = getComputedStyle(card);
    const radius = Number.parseFloat(style.borderTopLeftRadius || '0') || 0;
    const border = Number.parseFloat(style.borderTopWidth || '0') || 0;
    const hasVisualSurface = radius >= 6 || border > 0 || CARD_HINT.test(identity);
    if (!hasVisualSurface) return false;

    const directLongSurfaces = Array.from(card.children).filter((child) => {
      if (!(child instanceof HTMLElement) || !visible(child)) return false;
      const childIdentity = classAndId(child);
      if (!CARD_HINT.test(childIdentity)) return false;
      return child.scrollHeight >= threshold && child.clientHeight >= card.clientHeight * 0.75;
    });
    if (directLongSurfaces.length === 1 && !CARD_HINT.test(identity)) return false;

    return true;
  }

  function directHeader(card) {
    return Array.from(card.children).find((child) =>
      child.matches('h1,h2,h3,h4,.sec-hdr,.admin-card-header,.settings-card-header,.mbs-head,[data-card-header]')
    ) || null;
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
    if (previousDisplay) {
      child.style.setProperty('display', previousDisplay, previousPriority);
    }
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
    if (card.dataset.pmkLongCard === 'true') return;
    if (!visuallyCardLike(card)) return;

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

  const resizeObserver = typeof ResizeObserver === 'function'
    ? new ResizeObserver((entries) => {
        entries.forEach((entry) => enhance(entry.target));
      })
    : null;

  function observeCandidate(card) {
    if (!resizeObserver || observedForResize.has(card) || !likelySurfaceCandidate(card)) return;
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
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ['class', 'style', 'hidden'],
    });

    document.addEventListener('click', (event) => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target) return;
      if (target.closest('.nav-btn[data-page],.nav-btn[data-admin-page],[data-am-section],.sl18-tab')) {
        scheduleVisibilityScans();
      }
    }, true);

    window.addEventListener('hashchange', scheduleVisibilityScans);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) scheduleVisibilityScans();
    });
  });
})();
