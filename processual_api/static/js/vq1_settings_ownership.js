(() => {
  'use strict';

  const INTEGRATION_CARD_IDS = [
    'set-enterprise-console-card',
    'set-enterprise-integration-eligibility-card',
    'set-api-key-integration-card',
    'set-integration-readiness-card',
    'set-client-integration-guide-card',
    'settings-integration-claim-keys-host',
  ];

  const TAB_KEYS = ['operations', 'account', 'usage', 'integration', 'support'];
  const TAB_STORAGE_KEY = 'maestro_settings_tab';

  let reconciling = false;

  function settingsPage() {
    return document.getElementById('page-settings');
  }

  function integrationPanel() {
    return document.querySelector(
      '#page-settings .sl18-panel[data-sl18-panel="integration"]'
    );
  }

  function validTabKey(value) {
    return TAB_KEYS.includes(String(value || ''));
  }

  function currentTabKey() {
    const selected = document.querySelector(
      '#page-settings [data-sl18-tab][aria-selected="true"]'
    );
    if (selected && validTabKey(selected.dataset.sl18Tab)) {
      return selected.dataset.sl18Tab;
    }

    try {
      const stored = sessionStorage.getItem(TAB_STORAGE_KEY);
      if (validTabKey(stored)) return stored;
    } catch (_) {}

    return 'operations';
  }

  function activateTab(key, persist = true) {
    if (!validTabKey(key)) return false;

    const page = settingsPage();
    if (!page) return false;

    const tabs = Array.from(page.querySelectorAll('[data-sl18-tab]'));
    const panels = Array.from(page.querySelectorAll('[data-sl18-panel]'));
    if (!tabs.length || !panels.length) return false;

    let selectedTab = null;
    let selectedPanel = null;

    tabs.forEach((tab) => {
      const active = tab.dataset.sl18Tab === key;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
      tab.tabIndex = active ? 0 : -1;
      if (active) selectedTab = tab;
    });

    panels.forEach((panel) => {
      const active = panel.dataset.sl18Panel === key;
      panel.classList.toggle('active', active);
      panel.hidden = !active;
      panel.setAttribute('aria-hidden', active ? 'false' : 'true');
      panel.style.display = active ? 'flex' : 'none';
      if (active) selectedPanel = panel;
    });

    if (!selectedTab || !selectedPanel) return false;

    if (persist) {
      try {
        sessionStorage.setItem(TAB_STORAGE_KEY, key);
      } catch (_) {}
    }

    page.dataset.activeSettingsTab = key;
    selectedPanel.dataset.tabActivationProven = 'true';
    return true;
  }

  function bindTabs() {
    const page = settingsPage();
    if (!page) return;

    const tabs = page.querySelector('.sl18-tabs');
    if (!tabs) return;

    if (tabs.dataset.pmkExecutableTabsBound !== '1') {
      tabs.addEventListener('click', (event) => {
        const button = event.target.closest('[data-sl18-tab]');
        if (!button || !tabs.contains(button)) return;
        const key = button.dataset.sl18Tab;
        if (!validTabKey(key)) return;
        event.preventDefault();
        activateTab(key, true);
      }, true);

      tabs.addEventListener('keydown', (event) => {
        const button = event.target.closest('[data-sl18-tab]');
        if (!button || !tabs.contains(button)) return;
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        activateTab(button.dataset.sl18Tab, true);
      }, true);

      tabs.dataset.pmkExecutableTabsBound = '1';
    }

    activateTab(currentTabKey(), false);
  }

  function reconcileOwnership() {
    if (reconciling) return;

    const panel = integrationPanel();
    if (!panel) {
      bindTabs();
      return;
    }

    reconciling = true;
    try {
      INTEGRATION_CARD_IDS.forEach((id) => {
        const card = document.getElementById(id);
        if (card && card.parentElement !== panel) {
          panel.appendChild(card);
        }
      });
      bindTabs();
    } finally {
      reconciling = false;
    }
  }

  function start() {
    reconcileOwnership();

    const page = settingsPage();
    if (!page || window.PMK_VQ1_SETTINGS_OWNERSHIP_OBSERVER) return;

    const observer = new MutationObserver(() => {
      window.requestAnimationFrame(reconcileOwnership);
    });
    observer.observe(page, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['hidden', 'aria-selected', 'class'],
    });
    window.PMK_VQ1_SETTINGS_OWNERSHIP_OBSERVER = observer;

    [100, 500, 1500, 3500].forEach((delay) => {
      window.setTimeout(reconcileOwnership, delay);
    });
  }

  window.PMK_SETTINGS_TAB_RUNTIME = {
    activateTab,
    currentTabKey,
    reconcileOwnership,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
