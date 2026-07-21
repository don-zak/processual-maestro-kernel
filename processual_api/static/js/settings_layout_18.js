(() => {
  'use strict';

  const TAB_DEFS = [
    { key: 'operations', label: 'Operations' },
    { key: 'account', label: 'Account' },
    { key: 'usage', label: 'Plan & usage' },
    { key: 'integration', label: 'Integration' },
    { key: 'support', label: 'Escalations' },
  ];

  const TAB_STORAGE_KEY = 'maestro_settings_tab';

  let observer = null;
  let reconciling = false;
  let reconcileTimer = null;

  function settingsPage() {
    return document.getElementById('page-settings');
  }

  function cardTitle(card) {
    return String(
      card.querySelector(
        ':scope > .sec-hdr .sh-title, ' +
        ':scope > .settings-card-header h3, ' +
        ':scope > h2, ' +
        ':scope > h3, ' +
        ':scope > strong'
      )?.textContent || ''
    ).trim().toLowerCase();
  }

  function cardGroup(card) {
    const id = card.id || '';
    const key = card.dataset.settingsSectionKey || '';
    const title = cardTitle(card);

    if (id === 'settings-operations-root') {
      return 'operations';
    }

    if (id === 'set-provider-connection-card') {
      return 'operations';
    }

    if (
      id === 'set-api-key-integration-card' ||
      id === 'set-client-integration-guide-card' ||
      id === 'set-integration-readiness-card'
    ) {
      return 'integration';
    }

    if (
      id === 'set-client-requests-card' ||
      id === 'set-client-support-card'
    ) {
      return 'support';
    }

    if (key === 'requests' || key === 'supervisor') {
      return 'support';
    }

    if (key === 'provider') {
      return 'operations';
    }

    if (
      key === 'plan-usage' ||
      title.includes('plan and usage') ||
      title.includes('plan & usage')
    ) {
      return 'usage';
    }

    if (
      key === 'integration-guide' ||
      key === 'readiness' ||
      title.includes('integration')
    ) {
      return 'integration';
    }

    if (
      title.includes('account') ||
      title.includes('preference') ||
      title.includes('privacy')
    ) {
      return 'account';
    }

    if (
      title.includes('usage') ||
      title.includes('subscription') ||
      title.includes('billing summary')
    ) {
      return 'usage';
    }

    return 'account';
  }

  function ensureLayoutShell(page) {
    let tabs = page.querySelector(':scope > .sl18-tabs');
    let panelsRoot = page.querySelector(':scope > .sl18-panels');

    if (!tabs) {
      tabs = document.createElement('nav');
      tabs.className = 'sl18-tabs';
      tabs.setAttribute('role', 'tablist');
      tabs.setAttribute('aria-label', 'Client settings sections');

      tabs.innerHTML = TAB_DEFS.map((tab) => `
        <button
          type="button"
          class="sl18-tab"
          role="tab"
          aria-selected="false"
          data-sl18-tab="${tab.key}"
        >${tab.label}</button>
      `).join('');

      page.insertBefore(tabs, page.firstChild);
    }

    if (!panelsRoot) {
      panelsRoot = document.createElement('div');
      panelsRoot.className = 'sl18-panels';
      page.appendChild(panelsRoot);
    }

    TAB_DEFS.forEach((tab) => {
      let panel = panelsRoot.querySelector(
        `[data-sl18-panel="${tab.key}"]`
      );

      if (!panel) {
        panel = document.createElement('section');
        panel.className = 'sl18-panel';
        panel.dataset.sl18Panel = tab.key;
        panel.setAttribute('role', 'tabpanel');
        panel.hidden = true;
        panelsRoot.appendChild(panel);
      }
    });

    if (tabs.dataset.sl18Bound !== '1') {
      tabs.addEventListener('click', (event) => {
        const button = event.target.closest('[data-sl18-tab]');

        if (!button) {
          return;
        }

        event.preventDefault();
        activate(button.dataset.sl18Tab, true);
      });

      tabs.dataset.sl18Bound = '1';
    }

    return {
      tabs,
      panelsRoot,
    };
  }

  function enhanceProviderCard() {
    const card = document.getElementById(
      'set-provider-connection-card'
    );

    if (!card) {
      return;
    }

    card.classList.add(
      'sl18-provider-direct',
      'sl18-compact'
    );

    const title = card.querySelector('.sh-title');
    const subtitle = card.querySelector('.sh-sub');

    if (title) {
      title.textContent = 'Provider connection';
    }

    if (subtitle) {
      subtitle.textContent =
        'Test, save, replace, or remove your BYOK provider';
    }

    const providerLabel = card.querySelector(
      'label[for="set-provider-setup-provider"]'
    );

    if (providerLabel) {
      providerLabel.textContent = 'Provider';
    }

    const providerSelect = document.getElementById(
      'set-provider-setup-provider'
    );

    if (providerSelect?.options?.[0]) {
      providerSelect.options[0].textContent =
        'Choose provider';
    }

    const modelLabel = card.querySelector(
      'label[for="set-provider-setup-model"]'
    );

    if (modelLabel) {
      modelLabel.textContent = 'Model';
    }

    const test = document.getElementById(
      'set-provider-secret-test'
    );

    const save = document.getElementById(
      'set-provider-secret-save'
    );

    const clear = document.getElementById(
      'set-provider-secret-clear'
    );

    if (test) {
      test.textContent = 'Test connection';
    }

    if (save) {
      save.textContent = 'Save encrypted connection';
    }

    if (clear) {
      clear.textContent = 'Remove connection';
    }

    const request = document.getElementById(
      'set-provider-setup-request-prepare'
    );

    if (request) {
      request.classList.add('sl18-hidden');
    }

    const note = document.getElementById(
      'set-provider-connection-note'
    );

    if (note) {
      note.textContent =
        'Direct self-service is enabled for provider setup. ' +
        'Credentials are sent only to the secure provider endpoint, ' +
        'stored encrypted, and never displayed after submission.';

      note.classList.add('sl18-section-note');
    }

    const status = document.getElementById(
      'set-provider-setup-request-status'
    );

    if (status) {
      status.textContent =
        'Choose a provider and model, then test before saving. ' +
        'Supervisor escalation is needed only for unresolved ' +
        'infrastructure or policy exceptions.';
    }
  }

  function mergeEscalationCards() {
    const requests = document.getElementById(
      'set-client-requests-card'
    );

    const support = document.getElementById(
      'set-client-support-card'
    );

    if (!requests) {
      return;
    }

    requests.classList.add(
      'sl18-compact',
      'sl18-escalation-card'
    );

    const requestTitle = requests.querySelector(
      ':scope > .sec-hdr .sh-title'
    );

    const requestSubtitle = requests.querySelector(
      ':scope > .sec-hdr .sh-sub'
    );

    if (requestTitle) {
      requestTitle.textContent =
        'Escalations & support';
    }

    if (requestSubtitle) {
      requestSubtitle.textContent =
        'Billing, plan, security, or approval exceptions only. ' +
        'Use this area also for unresolved operational exceptions.';
    }

    if (
      !support ||
      support.dataset.sl18Merged === '1'
    ) {
      return;
    }

    support.classList.remove(
      'card',
      'settings-section',
      'sl18-compact'
    );

    support.classList.add(
      'sl18-escalation-subsection'
    );

    support.dataset.sl18Merged = '1';

    const supportTitle = support.querySelector(
      ':scope > .sec-hdr .sh-title'
    );

    const supportSubtitle = support.querySelector(
      ':scope > .sec-hdr .sh-sub'
    );

    if (supportTitle) {
      supportTitle.textContent =
        'Direct supervisor message';
    }

    if (supportSubtitle) {
      supportSubtitle.textContent =
        'Use only when direct operations cannot resolve the issue. ' +
        'The request workflow should remain the primary escalation path.';
    }

    requests.appendChild(support);
  }

  function topLevelSettingsCards(page) {
    const selector = [
      '#settings-operations-root',
      '.card.settings-section',
      '.settings-card',
    ].join(',');

    return Array.from(
      page.querySelectorAll(selector)
    ).filter((card) => {
      if (
        card.closest('.sl18-escalation-subsection')
      ) {
        return false;
      }

      const parentCard = card.parentElement?.closest(
        '.card.settings-section, .settings-card'
      );

      return !parentCard;
    });
  }

  function currentTab() {
    const preferred = sessionStorage.getItem(
      TAB_STORAGE_KEY
    );

    return TAB_DEFS.some(
      (tab) => tab.key === preferred
    )
      ? preferred
      : 'operations';
  }

  function activate(key, persist = true) {
    const page = settingsPage();

    if (!page) {
      return;
    }

    const safeKey = TAB_DEFS.some(
      (tab) => tab.key === key
    )
      ? key
      : 'operations';

    page.querySelectorAll('.sl18-tab').forEach(
      (button) => {
        const active =
          button.dataset.sl18Tab === safeKey;

        button.classList.toggle('active', active);
        button.setAttribute(
          'aria-selected',
          String(active)
        );
        button.tabIndex = active ? 0 : -1;
      }
    );

    page.querySelectorAll('.sl18-panel').forEach(
      (panel) => {
        const active =
          panel.dataset.sl18Panel === safeKey;

        panel.classList.toggle('active', active);
        panel.hidden = !active;
      }
    );

    if (persist) {
      sessionStorage.setItem(
        TAB_STORAGE_KEY,
        safeKey
      );
    }
  }

  function reconcile() {
    const page = settingsPage();

    if (!page || reconciling) {
      return;
    }

    reconciling = true;

    try {
      const { panelsRoot } =
        ensureLayoutShell(page);

      enhanceProviderCard();
      mergeEscalationCards();

      const panels = {};

      TAB_DEFS.forEach((tab) => {
        panels[tab.key] =
          panelsRoot.querySelector(
            `[data-sl18-panel="${tab.key}"]`
          );
      });

      topLevelSettingsCards(page).forEach(
        (card) => {
          const group = cardGroup(card);
          const panel = panels[group];

          if (
            panel &&
            card.parentElement !== panel
          ) {
            panel.appendChild(card);
          }
        }
      );

      const obsoleteControls = [
        'set-section-collapse-controls',
      ];

      obsoleteControls.forEach((id) => {
        document
          .getElementById(id)
          ?.classList.add('sl18-hidden');
      });

      activate(currentTab(), false);

      page.dataset.sl18Ready = '1';
    } finally {
      reconciling = false;
    }
  }

  function scheduleReconcile() {
    window.clearTimeout(reconcileTimer);

    reconcileTimer = window.setTimeout(
      reconcile,
      30
    );
  }

  function observePage() {
    const page = settingsPage();

    if (!page || observer) {
      return;
    }

    observer = new MutationObserver(() => {
      if (!reconciling) {
        scheduleReconcile();
      }
    });

    observer.observe(page, {
      childList: true,
      subtree: true,
    });
  }

  function init() {
    reconcile();
    observePage();

    window.setTimeout(reconcile, 100);
    window.setTimeout(reconcile, 500);
    window.setTimeout(reconcile, 1500);
  }

  window.PMK_SETTINGS_LAYOUT_18 = {
    init,
    activate,
    reconcile,
  };

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      init,
      { once: true }
    );
  } else {
    init();
  }
})();
