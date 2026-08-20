(() => {
  const STYLE_ID = 'pmk-long-card-collapse-style';
  const TOOLS_CLASS = 'pmk-long-card-tools';
  const BUTTON_CLASS = 'pmk-long-card-toggle';
  const LONG_THRESHOLD_PX = 520;
  const SELECTOR = [
    '#content .card',
    '#content .settings-card',
    '#content .pmk-admin-card',
    '.admin-page .card',
    '.admin-page .admin-card',
    '.admin-page .pmk-admin-card',
    '.admin-page .admin-subscription-analytics-card',
  ].join(',');

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

  function directHeader(card) {
    return Array.from(card.children).find((child) =>
      child.matches('h1,h2,h3,h4,.sec-hdr,.admin-card-header,.settings-card-header,[data-card-header]')
    ) || null;
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
      if (collapsed) {
        if (!child.hasAttribute('data-pmk-collapse-prev-hidden')) {
          child.setAttribute('data-pmk-collapse-prev-hidden', child.hidden ? 'true' : 'false');
        }
        child.hidden = true;
      } else {
        const previous = child.getAttribute('data-pmk-collapse-prev-hidden');
        if (previous !== null) {
          child.hidden = previous === 'true';
          child.removeAttribute('data-pmk-collapse-prev-hidden');
        }
      }
    });
  }

  function enhance(card) {
    if (!(card instanceof HTMLElement)) return;
    if (card.dataset.pmkLongCard === 'true') return;
    if (!visible(card)) return;
    if (card.scrollHeight < LONG_THRESHOLD_PX) return;

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

  function scan(root = document) {
    root.querySelectorAll?.(SELECTOR).forEach(enhance);
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

  document.addEventListener('DOMContentLoaded', () => {
    scan();
    window.setTimeout(scan, 250);
    window.setTimeout(scan, 900);
    const observer = new MutationObserver(scheduleScan);
    observer.observe(document.body, { childList: true, subtree: true });
  });
})();
