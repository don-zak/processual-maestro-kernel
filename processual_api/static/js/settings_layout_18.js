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
  let initialized = false;
  let enterpriseConsoleLoading = false;
  let enterpriseConsoleLoaded = false;

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
      id === 'set-enterprise-integration-eligibility-card' ||
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

  function tabId(key) {
    return `sl18-tab-${key}`;
  }

  function panelId(key) {
    return `sl18-panel-${key}`;
  }

  function moveTabFocus(tabs, currentIndex, direction) {
    if (!tabs.length) {
      return;
    }

    const nextIndex = (
      currentIndex + direction + tabs.length
    ) % tabs.length;
    tabs[nextIndex].focus();
  }

  function handleTabKeydown(event, tabs) {
    const currentIndex = tabs.indexOf(event.currentTarget);
    if (currentIndex < 0) {
      return;
    }

    if (event.key === 'ArrowRight') {
      event.preventDefault();
      moveTabFocus(tabs, currentIndex, 1);
      return;
    }

    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      moveTabFocus(tabs, currentIndex, -1);
      return;
    }

    if (event.key === 'Home') {
      event.preventDefault();
      tabs[0]?.focus();
      return;
    }

    if (event.key === 'End') {
      event.preventDefault();
      tabs[tabs.length - 1]?.focus();
      return;
    }

    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      activate(event.currentTarget.dataset.sl18Tab, true);
    }
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
          id="${tabId(tab.key)}"
          role="tab"
          aria-selected="false"
          aria-controls="${panelId(tab.key)}"
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
        panel.id = panelId(tab.key);
        panel.dataset.sl18Panel = tab.key;
        panel.setAttribute('role', 'tabpanel');
        panel.setAttribute('aria-labelledby', tabId(tab.key));
        panel.hidden = true;
        panelsRoot.appendChild(panel);
      } else {
        panel.id = panelId(tab.key);
        panel.setAttribute('aria-labelledby', tabId(tab.key));
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

      const tabButtons = Array.from(
        tabs.querySelectorAll('[data-sl18-tab]')
      );
      tabButtons.forEach((button) => {
        button.addEventListener('keydown', (event) => {
          handleTabKeydown(event, tabButtons);
        });
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

  function ensureEnterpriseConsoleCard(panel) {
    let card = document.getElementById('set-enterprise-console-card');
    if (card) {
      return card;
    }

    card = document.createElement('section');
    card.id = 'set-enterprise-console-card';
    card.className = 'settings-card sl18-enterprise-console';
    card.setAttribute('aria-labelledby', 'set-enterprise-console-title');

    const header = document.createElement('div');
    header.className = 'sec-hdr';

    const headerCopy = document.createElement('div');
    const title = document.createElement('div');
    title.id = 'set-enterprise-console-title';
    title.className = 'sh-title';
    title.textContent = 'Enterprise Integration';
    const subtitle = document.createElement('div');
    subtitle.className = 'sh-sub';
    subtitle.textContent = 'Server-authoritative entitlement, identity, readiness, and approval state';
    headerCopy.append(title, subtitle);

    const badge = document.createElement('span');
    badge.id = 'set-enterprise-console-badge';
    badge.className = 'sl18-enterprise-badge';
    badge.textContent = 'Loading';
    header.append(headerCopy, badge);

    const summary = document.createElement('div');
    summary.className = 'settings-grid sl18-enterprise-summary';
    summary.innerHTML = [
      '<div class="inp-group"><label class="inp-label">Plan</label><span id="set-enterprise-console-plan" class="font-data">—</span></div>',
      '<div class="inp-group"><label class="inp-label">Environment</label><span id="set-enterprise-console-environment" class="font-data">sandbox</span></div>',
      '<div class="inp-group"><label class="inp-label">Active keys</label><span id="set-enterprise-console-key-count" class="font-data">—</span></div>',
      '<div class="inp-group"><label class="inp-label">Sandbox ready</label><span id="set-enterprise-console-sandbox-ready" class="font-data">—</span></div>',
    ].join('');

    const nextAction = document.createElement('div');
    nextAction.className = 'sl18-enterprise-next';
    const nextLabel = document.createElement('strong');
    nextLabel.textContent = 'Next safe action';
    const nextText = document.createElement('span');
    nextText.id = 'set-enterprise-console-next-action';
    nextText.textContent = 'Loading enterprise integration state…';
    nextAction.append(nextLabel, nextText);

    const stages = document.createElement('ol');
    stages.id = 'set-enterprise-console-stages';
    stages.className = 'sl18-enterprise-stages';
    stages.setAttribute('aria-label', 'Enterprise integration lifecycle');

    const safety = document.createElement('p');
    safety.id = 'set-enterprise-console-safety';
    safety.className = 'sl18-enterprise-safety';
    safety.textContent = 'Production access is not granted from Settings. Runtime connector approval remains supervised and fail-closed.';

    card.append(header, summary, nextAction, stages, safety);
    panel.prepend(card);
    return card;
  }

  function enterpriseStatusLabel(status) {
    const labels = {
      ready: 'Ready',
      available: 'Available',
      action_required: 'Action required',
      blocked: 'Blocked',
      locked: 'Locked',
    };
    return labels[String(status || '').toLowerCase()] || 'Pending';
  }

  function renderEnterpriseConsole(payload) {
    const card = document.getElementById('set-enterprise-console-card');
    if (!card || !payload) {
      return;
    }

    const enabled = payload.enabled === true;
    card.dataset.enterpriseEnabled = String(enabled);

    const badge = document.getElementById('set-enterprise-console-badge');
    if (badge) {
      badge.textContent = enterpriseStatusLabel(payload.status);
      badge.dataset.status = String(payload.status || 'pending');
    }

    const plan = document.getElementById('set-enterprise-console-plan');
    const environment = document.getElementById('set-enterprise-console-environment');
    const keyCount = document.getElementById('set-enterprise-console-key-count');
    const sandboxReady = document.getElementById('set-enterprise-console-sandbox-ready');
    const nextAction = document.getElementById('set-enterprise-console-next-action');

    if (plan) {
      plan.textContent = String(payload.plan_id || payload.normalized_plan_id || '—');
    }
    if (environment) {
      environment.textContent = String(payload.environment || 'sandbox');
    }
    if (keyCount) {
      keyCount.textContent = String(Number(payload.key_count || 0));
    }
    if (sandboxReady) {
      sandboxReady.textContent = String(Number(payload.readiness?.sandbox_ready || 0));
    }
    if (nextAction) {
      nextAction.textContent = String(payload.next_action || 'Review integration readiness.');
    }

    const stages = document.getElementById('set-enterprise-console-stages');
    if (stages) {
      stages.replaceChildren();
      const sections = Array.isArray(payload.sections) ? payload.sections : [];
      sections.forEach((section) => {
        const item = document.createElement('li');
        item.className = 'sl18-enterprise-stage';
        item.dataset.status = String(section.status || 'pending');

        const dot = document.createElement('span');
        dot.className = 'sl18-enterprise-stage-dot';
        dot.setAttribute('aria-hidden', 'true');

        const copy = document.createElement('span');
        copy.className = 'sl18-enterprise-stage-copy';
        const label = document.createElement('strong');
        label.textContent = String(section.label || section.id || 'Integration stage');
        const status = document.createElement('span');
        status.textContent = enterpriseStatusLabel(section.status);
        const action = document.createElement('small');
        action.textContent = String(section.next_action || '');
        copy.append(label, status, action);
        item.append(dot, copy);
        stages.appendChild(item);
      });
    }
  }

  function renderEnterpriseConsoleError() {
    const badge = document.getElementById('set-enterprise-console-badge');
    const nextAction = document.getElementById('set-enterprise-console-next-action');
    if (badge) {
      badge.textContent = 'Unavailable';
      badge.dataset.status = 'blocked';
    }
    if (nextAction) {
      nextAction.textContent = 'Enterprise integration state could not be loaded. No production access has been granted.';
    }
  }

  async function loadEnterpriseConsole(force = false) {
    if (enterpriseConsoleLoading || (enterpriseConsoleLoaded && !force)) {
      return;
    }
    if (typeof CLIENT === 'undefined' || typeof CLIENT.get !== 'function') {
      renderEnterpriseConsoleError();
      return;
    }

    enterpriseConsoleLoading = true;
    try {
      const payload = await CLIENT.get('/settings/enterprise-integration');
      renderEnterpriseConsole(payload);
      enterpriseConsoleLoaded = true;
    } catch (error) {
      renderEnterpriseConsoleError();
    } finally {
      enterpriseConsoleLoading = false;
    }
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

    if (safeKey === 'integration') {
      loadEnterpriseConsole();
    }

    if (persist) {
      sessionStorage.setItem(
        TAB_STORAGE_KEY,
        safeKey
      );
    }
  }

  function observePageMutations(page) {
    observer?.observe(page, {
      childList: true,
      subtree: true,
    });
  }

  function reconcile() {
    const page = settingsPage();

    if (!page || reconciling) {
      return;
    }

    reconciling = true;
    const resumeObserver = Boolean(observer);
    observer?.disconnect();

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

      if (panels.integration) {
        ensureEnterpriseConsoleCard(panels.integration);
      }

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
      if (resumeObserver) {
        observePageMutations(page);
      }
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

    observePageMutations(page);
  }

  function init() {
    if (initialized) {
      reconcile();
      return;
    }

    initialized = true;
    reconcile();
    observePage();
  }

  window.PMK_SETTINGS_LAYOUT_18 = {
    init,
    activate,
    reconcile,
    loadEnterpriseConsole,
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
