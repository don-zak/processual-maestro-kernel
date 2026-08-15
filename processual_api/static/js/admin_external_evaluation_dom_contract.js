(function () {
  const CATEGORY_ID = 'admin-api-key-category';
  const LIFECYCLE_ID = 'admin-api-key-lifecycle-card';
  const EVALUATION_CARD_ID = 'admin-api-key-external-evaluation-card';
  const EVALUATION_BODY_ID = 'admin-api-key-external-evaluation-body';
  const EVALUATION_HOST_ID = 'admin-evaluation-grants';
  const EXTERNAL_CATEGORY = 'external_evaluation';
  const STANDARD_IDS = [
    'admin-api-key-role',
    'admin-api-key-plan-id',
    'admin-api-key-quota-limit-override',
    'admin-api-key-expires-at',
    'admin-api-key-label',
    'admin-api-key-client-id',
    'admin-api-key-user-id',
    'admin-api-key-purpose',
    'admin-api-key-issued-to',
    'admin-api-key-scopes',
    'admin-api-key-generate-btn',
    'admin-api-key-refresh-btn',
    'admin-api-key-create-result',
    'admin-api-key-table',
    'admin-api-key-profile-controls',
  ];
  let observer = null;
  let applying = false;

  function category() {
    return document.getElementById(CATEGORY_ID);
  }

  function lifecycle() {
    return document.getElementById(LIFECYCLE_ID);
  }

  function externalSelected() {
    return category()?.value === EXTERNAL_CATEGORY;
  }

  function ensureExternalOption() {
    const select = category();
    if (!select) return false;
    if (!select.querySelector(`option[value="${EXTERNAL_CATEGORY}"]`)) {
      const option = document.createElement('option');
      option.value = EXTERNAL_CATEGORY;
      option.textContent = 'External Evaluation Access - governed sandbox evaluation';
      select.appendChild(option);
    }
    return true;
  }

  function ensureEvaluationCard() {
    const root = lifecycle();
    if (!root) return null;
    let card = document.getElementById(EVALUATION_CARD_ID);
    if (!card) {
      card = document.createElement('section');
      card.id = EVALUATION_CARD_ID;
      card.className = 'card flat';
      card.dataset.categoryOwned = 'true';
      card.dataset.domContract = 'true';
      card.innerHTML = `
        <div class="sec-hdr">
          <div class="sh-title">External Evaluation Lifecycle</div>
          <div class="sh-sub">verify → provision → bind tasks → create grant → issue once → test → revoke</div>
        </div>
        <div class="admin-note">
          External Evaluation is controlled by Category. Standard API key generation is disabled while this lifecycle is selected. Production access remains disabled.
        </div>
        <div id="${EVALUATION_BODY_ID}" style="margin-top:var(--s-3)">
          <section class="card flat" data-evaluation-verification-stage="true">
            <div class="sec-hdr">
              <div class="sh-title">Administrator Verification</div>
              <div class="sh-sub">required before governed provisioning and one-time issue controls are enabled</div>
            </div>
            <div id="${EVALUATION_HOST_ID}" class="card flat" data-evaluation-grant-placeholder="true">
              <div class="admin-note" data-evaluation-access-status>
                Administrator verification is required before evaluation grant controls can be shown.
              </div>
              <div class="muted" style="margin-top:var(--s-2)">
                Backend scopes remain authoritative. Raw API keys are shown only at issue time.
              </div>
            </div>
          </section>
        </div>
      `;
      const authority = document.getElementById('admin-api-key-category-authority');
      if (authority?.nextSibling) root.insertBefore(card, authority.nextSibling);
      else root.prepend(card);
    }
    return card;
  }

  function remember(node) {
    if (!node || node.dataset.externalEvaluationDomContractRemembered === 'true') return;
    node.dataset.externalEvaluationDomContractRemembered = 'true';
    node.dataset.externalEvaluationDomContractHidden = node.hidden ? 'true' : 'false';
    node.dataset.externalEvaluationDomContractDisplay = node.style.display || '';
  }

  function setVisible(node, visible) {
    if (!node) return;
    remember(node);
    if (visible) {
      node.hidden = node.dataset.externalEvaluationDomContractHidden === 'true';
      node.style.display = node.dataset.externalEvaluationDomContractDisplay || '';
    } else {
      node.hidden = true;
      node.style.display = 'none';
    }
  }

  function standardNodes() {
    const root = lifecycle();
    if (!root) return [];
    const nodes = new Set();

    STANDARD_IDS.forEach((id) => {
      const element = document.getElementById(id);
      if (!element) return;
      if (id === 'admin-api-key-profile-controls') {
        nodes.add(element);
        return;
      }
      const label = element.closest('label');
      if (label && root.contains(label)) {
        nodes.add(label);
        return;
      }
      const actions = element.closest('.admin-actions');
      if (actions && root.contains(actions)) {
        nodes.add(actions);
        return;
      }
      if (root.contains(element)) nodes.add(element);
    });

    root.querySelectorAll('.admin-grid').forEach((grid) => {
      if (
        grid.querySelector('#admin-api-key-role') ||
        grid.querySelector('#admin-api-key-plan-id') ||
        grid.querySelector('#admin-api-key-client-id')
      ) {
        nodes.add(grid);
      }
    });

    root.querySelectorAll('h3').forEach((heading) => {
      const title = (heading.textContent || '').trim();
      if (title === 'External usage examples') {
        nodes.add(heading);
        if (heading.nextElementSibling) nodes.add(heading.nextElementSibling);
      }
      if (title === 'Safe metadata cards') {
        nodes.add(heading);
        let sibling = heading.nextElementSibling;
        while (sibling && sibling.id !== 'admin-supervisor-session-key-panel') {
          nodes.add(sibling);
          if (sibling.id === 'admin-api-key-table') break;
          sibling = sibling.nextElementSibling;
        }
      }
    });

    return [...nodes].filter((node) => !node.closest(`#${EVALUATION_CARD_ID}`));
  }

  function setStandardVisible(visible) {
    standardNodes().forEach((node) => setVisible(node, visible));
    const generate = document.getElementById('admin-api-key-generate-btn');
    if (generate) {
      generate.disabled = !visible;
      if (!visible) generate.dataset.externalEvaluationBlocked = 'true';
      else delete generate.dataset.externalEvaluationBlocked;
    }
  }

  function dispatchCategoryChanged() {
    try {
      window.dispatchEvent(
        new CustomEvent('pmk-api-key-category-changed', {
          detail: { category: category()?.value || '' },
        })
      );
    } catch {
      window.dispatchEvent(new Event('pmk-api-key-category-changed'));
    }
  }

  function apply() {
    if (applying) return;
    applying = true;
    try {
      if (!ensureExternalOption()) return;
      const card = ensureEvaluationCard();
      if (!card) return;
      const body = document.getElementById(EVALUATION_BODY_ID);
      const external = externalSelected();

      card.hidden = !external;
      card.style.display = external ? '' : 'none';
      card.dataset.activated = external ? 'true' : 'false';
      if (body) {
        body.hidden = !external;
        body.style.display = external ? '' : 'none';
      }
      setStandardVisible(!external);

      if (external) {
        const mode = document.getElementById('admin-api-key-provisioning-mode');
        if (mode && mode.value !== 'external_evaluation') {
          mode.value = 'external_evaluation';
          mode.dispatchEvent(new Event('change', { bubbles: true }));
        }
        window.PMK_ADMIN_SESSION?.syncEvaluationSelectionState?.();
        window.PMK_ADMIN_SESSION?.check?.();
      }
    } finally {
      applying = false;
    }
  }

  function bind() {
    const select = category();
    if (!select) return false;
    if (select.dataset.domContractBound !== 'true') {
      select.dataset.domContractBound = 'true';
      select.addEventListener('change', () => {
        apply();
        dispatchCategoryChanged();
      });
    }
    return true;
  }

  function installObserver() {
    const root = lifecycle();
    if (!root || observer) return;
    observer = new MutationObserver(() => {
      if (externalSelected()) window.setTimeout(apply, 0);
    });
    observer.observe(root, { childList: true, subtree: true });
  }

  document.addEventListener(
    'click',
    (event) => {
      if (!externalSelected()) return;
      const generate = event.target.closest?.('#admin-api-key-generate-btn');
      if (!generate) return;
      event.preventDefault();
      event.stopImmediatePropagation();
    },
    true
  );

  function reconcile(attempt = 0) {
    if (!ensureExternalOption() || !ensureEvaluationCard() || !bind()) {
      if (attempt < 100) window.setTimeout(() => reconcile(attempt + 1), 100);
      return;
    }
    installObserver();
    apply();
  }

  window.PMK_ADMIN_EXTERNAL_EVALUATION_DOM_CONTRACT = {
    apply,
    reconcile,
    selected: externalSelected,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => reconcile());
  } else {
    reconcile();
  }
})();
