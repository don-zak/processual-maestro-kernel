(() => {
  'use strict';

  const INTEGRATION_CARD_IDS = [
    'set-enterprise-console-card',
    'set-enterprise-integration-eligibility-card',
    'set-api-key-integration-card',
    'set-integration-readiness-card',
    'set-client-integration-guide-card',
  ];

  let reconciling = false;

  function integrationPanel() {
    return document.querySelector(
      '#page-settings .sl18-panel[data-sl18-panel="integration"]'
    );
  }

  function reconcileOwnership() {
    if (reconciling) return;

    const panel = integrationPanel();
    if (!panel) return;

    reconciling = true;
    try {
      INTEGRATION_CARD_IDS.forEach((id) => {
        const card = document.getElementById(id);
        if (card && card.parentElement !== panel) {
          panel.appendChild(card);
        }
      });
    } finally {
      reconciling = false;
    }
  }

  function start() {
    reconcileOwnership();

    const page = document.getElementById('page-settings');
    if (!page || window.PMK_VQ1_SETTINGS_OWNERSHIP_OBSERVER) return;

    const observer = new MutationObserver(() => {
      window.requestAnimationFrame(reconcileOwnership);
    });
    observer.observe(page, { childList: true, subtree: true });
    window.PMK_VQ1_SETTINGS_OWNERSHIP_OBSERVER = observer;

    [100, 500, 1500, 3500].forEach((delay) => {
      window.setTimeout(reconcileOwnership, delay);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
