(() => {
  'use strict';

  const TAB_DEFS = [
    { key: 'operations', label: 'Operations' },
    { key: 'account', label: 'Account' },
    { key: 'usage', label: 'Plan & usage' },
    { key: 'integration', label: 'Integration' },
    { key: 'support', label: 'Escalations' },
  ];

  function settingsPage() { return document.getElementById('page-settings'); }
  function cardTitle(card) {
    return String(card.querySelector('.sh-title, h2, h3, strong')?.textContent || '').trim().toLowerCase();
  }

  function cardGroup(card) {
    const id = card.id || '';
    const key = card.dataset.settingsSectionKey || '';
    const title = cardTitle(card);

    if (id === 'settings-operations-root') return 'operations';
    if (id === 'set-provider-connection-card') return 'operations';
    if (id === 'set-api-key-integration-card') return 'integration';
    if (id === 'set-client-integration-guide-card') return 'integration';
    if (id === 'set-integration-readiness-card') return 'integration';
    if (id === 'set-client-requests-card' || id === 'set-client-support-card') return 'support';
    if (key === 'requests' || key === 'supervisor') return 'support';
    if (key === 'provider') return 'operations';
    if (key === 'plan-usage' || title.includes('plan and usage')) return 'usage';
    if (key === 'integration-guide' || key === 'readiness' || title.includes('integration')) return 'integration';
    if (title.includes('account') || title.includes('preference')) return 'account';
    if (title.includes('usage') || title.includes('subscription')) return 'usage';
    return 'account';
  }

  function enhanceProviderCard() {
    const card = document.getElementById('set-provider-connection-card');
    if (!card) return;
    card.classList.add('sl18-provider-direct', 'sl18-compact');

    const title = card.querySelector('.sh-title');
    const subtitle = card.querySelector('.sh-sub');
    if (title) title.textContent = 'Provider connection';
    if (subtitle) subtitle.textContent = 'Test, save, replace, or remove your BYOK provider';

    const providerLabel = card.querySelector('label[for="set-provider-setup-provider"]');
    if (providerLabel) providerLabel.textContent = 'Provider';
    const providerSelect = document.getElementById('set-provider-setup-provider');
    if (providerSelect?.options?.[0]) providerSelect.options[0].textContent = 'Choose provider';

    const modelLabel = document.querySelector('label[for="set-provider-setup-model"]');
    if (modelLabel) modelLabel.textContent = 'Model';

    const test = document.getElementById('set-provider-secret-test');
    const save = document.getElementById('set-provider-secret-save');
    const clear = document.getElementById('set-provider-secret-clear');
    if (test) test.textContent = 'Test connection';
    if (save) save.textContent = 'Save encrypted connection';
    if (clear) clear.textContent = 'Remove connection';

    const request = document.getElementById('set-provider-setup-request-prepare');
    if (request) request.classList.add('sl18-hidden');

    const note = document.getElementById('set-provider-connection-note');
    if (note) {
      note.textContent = 'Direct self-service is enabled for provider setup. Credentials are sent only to the secure provider endpoint, stored encrypted, and never displayed after submission.';
      note.classList.add('sl18-section-note');
    }

    const status = document.getElementById('set-provider-setup-request-status');
    if (status) status.textContent = 'Choose a provider and model, then test before saving. Supervisor escalation is needed only for unresolved infrastructure or policy exceptions.';
  }

  function compactSupport() {
    const requests = document.getElementById('set-client-requests-card');
    const support = document.getElementById('set-client-support-card');
    if (requests) {
      requests.classList.add('sl18-compact');
      const sub = requests.querySelector('.sh-sub');
      if (sub) sub.textContent = 'Billing, plan, security, or approval exceptions only';
    }
    if (support) {
      support.classList.add('sl18-compact');
      const sub = support.querySelector('.sh-sub');
      if (sub) sub.textContent = 'Use only when direct operations cannot resolve the issue';
    }
  }

  function activate(key) {
    document.querySelectorAll('.sl18-tab').forEach((button) => {
      button.classList.toggle('active', button.dataset.sl18Tab === key);
    });
    document.querySelectorAll('.sl18-panel').forEach((panel) => {
      panel.classList.toggle('active', panel.dataset.sl18Panel === key);
    });
    sessionStorage.setItem('maestro_settings_tab', key);
  }

  function build() {
    const page = settingsPage();
    if (!page || page.dataset.sl18Ready === '1') return;
    const container = page.firstElementChild || page;
    const cards = Array.from(container.children).filter((node) => {
      return node.id === 'settings-operations-root'
        || node.classList?.contains('card')
        || node.classList?.contains('settings-card');
    });
    if (!cards.length) return;

    const tabs = document.createElement('div');
    tabs.className = 'sl18-tabs';
    tabs.setAttribute('role', 'tablist');
    tabs.innerHTML = TAB_DEFS.map((tab) => `
      <button type="button" class="sl18-tab" data-sl18-tab="${tab.key}">${tab.label}</button>
    `).join('');

    const panels = {};
    TAB_DEFS.forEach((tab) => {
      const panel = document.createElement('section');
      panel.className = 'sl18-panel';
      panel.dataset.sl18Panel = tab.key;
      panels[tab.key] = panel;
    });

    container.insertBefore(tabs, container.firstChild);
    TAB_DEFS.forEach((tab) => container.appendChild(panels[tab.key]));
    cards.forEach((card) => panels[cardGroup(card)].appendChild(card));

    const obsoleteControls = [
      'set-section-collapse-controls',
    ];
    obsoleteControls.forEach((id) => document.getElementById(id)?.classList.add('sl18-hidden'));

    enhanceProviderCard();
    compactSupport();

    tabs.querySelectorAll('[data-sl18-tab]').forEach((button) => {
      button.addEventListener('click', () => activate(button.dataset.sl18Tab));
    });

    const preferred = sessionStorage.getItem('maestro_settings_tab');
    activate(TAB_DEFS.some((tab) => tab.key === preferred) ? preferred : 'operations');
    page.dataset.sl18Ready = '1';
  }

  function init() {
    build();
  }

  window.PMK_SETTINGS_LAYOUT_18 = { init, activate };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(build, 0));
  } else {
    setTimeout(build, 0);
  }
})();
