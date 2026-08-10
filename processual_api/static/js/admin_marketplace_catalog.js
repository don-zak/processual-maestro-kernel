(function () {
  'use strict';

  const API_PATH = '/admin-marketplace/catalog/offers';
  let loaded = false;

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function authHeaders() {
    const headers = window.PMK_ADMIN_AUTH && typeof window.PMK_ADMIN_AUTH.headers === 'function'
      ? window.PMK_ADMIN_AUTH.headers()
      : new Headers();
    headers.set('Accept', 'application/json');
    return headers;
  }

  async function requestCatalog() {
    const response = await fetch(API_PATH, {
      method: 'GET',
      credentials: 'include',
      headers: authHeaders(),
    });
    const text = await response.text();
    let payload = {};
    try { payload = text ? JSON.parse(text) : {}; } catch (error) {}
    if (!response.ok) {
      const failure = new Error('Catalog request failed.');
      failure.status = response.status;
      failure.detail = payload && payload.detail ? payload.detail : '';
      throw failure;
    }
    return payload;
  }

  function failureMessage(error) {
    if (error && error.status === 401) return 'Sign in again to load the original offer catalog.';
    if (error && error.status === 403) return 'Active platform administrator authority is required to view the catalog.';
    if (error && error.status === 503) return 'The original offer catalog is temporarily unavailable.';
    return 'The original offer catalog could not be loaded.';
  }

  function gateLabel(reason) {
    const labels = {
      offer_not_published: 'Offer not published',
      price_not_approved: 'Price not approved',
      currency_not_tnd: 'Currency is not TND',
      checkout_disabled: 'Checkout disabled',
      offer_not_commercially_listed: 'Not commercially listed',
    };
    return labels[reason] || reason;
  }

  function offerCard(offer) {
    const reasons = Array.isArray(offer.local_payment_gate_reasons)
      ? offer.local_payment_gate_reasons
      : [];
    const localState = offer.local_payment_ready
      ? '<span class="am-badge active">Local payment ready</span>'
      : '<span class="am-badge draft">Local payment blocked</span>';
    const gates = reasons.length
      ? '<ul class="am-catalog-gates">' + reasons.map((reason) =>
          '<li>' + escapeHtml(gateLabel(reason)) + '</li>'
        ).join('') + '</ul>'
      : '<p class="am-catalog-ready">Eligible for maestro_direct in TND after the customer Tunisia-address gate passes.</p>';

    return [
      '<article class="am-card am-catalog-offer" data-offer-id="' + escapeHtml(offer.offer_id) + '">',
      '<div class="am-card-heading"><div><span class="am-kicker">' + escapeHtml(offer.plan_display_name) + '</span>',
      '<h3>' + escapeHtml(offer.display_name) + '</h3></div>' + localState + '</div>',
      '<p>' + escapeHtml(offer.description) + '</p>',
      '<div class="am-destination-details">',
      '<div><span>Offer</span><strong>' + escapeHtml(offer.offer_id) + '</strong></div>',
      '<div><span>Billing</span><strong>' + escapeHtml(offer.billing_interval) + '</strong></div>',
      '<div><span>Price</span><strong>' + escapeHtml(offer.public_price_label) + '</strong></div>',
      '<div><span>Currency</span><strong>' + escapeHtml(offer.currency || 'Pending') + '</strong></div>',
      '<div><span>Price status</span><strong>' + escapeHtml(offer.price_status) + '</strong></div>',
      '<div><span>Checkout</span><strong>' + (offer.checkout_enabled ? 'Enabled' : 'Disabled') + '</strong></div>',
      '</div>',
      gates,
      '</article>',
    ].join('');
  }

  function installMarkup(panel) {
    panel.innerHTML = [
      '<div class="am-section-heading">',
      '<div><span class="am-kicker">Canonical program catalog</span><h2>Catalog / Offers</h2>',
      '<p>Read-only projection of the original billing offer pricebook. Local payment remains fail-closed until offer, TND, checkout, confirmed Tunisian address, and active default destination gates all pass.</p></div>',
      '<button id="am-refresh-catalog" class="btn secondary" type="button">Refresh</button>',
      '</div>',
      '<div id="am-catalog-summary" class="am-notice" role="status" aria-live="polite">Loading original offers…</div>',
      '<div id="am-catalog-offer-list" class="am-readiness-grid" data-state="loading"></div>',
    ].join('');

    const refresh = document.getElementById('am-refresh-catalog');
    if (refresh) refresh.addEventListener('click', loadCatalog);
  }

  async function loadCatalog() {
    const panel = document.querySelector('[data-am-panel="catalog"]');
    if (!panel) return;
    if (!document.getElementById('am-catalog-offer-list')) installMarkup(panel);

    const target = document.getElementById('am-catalog-offer-list');
    const summary = document.getElementById('am-catalog-summary');
    const refresh = document.getElementById('am-refresh-catalog');
    if (refresh) refresh.disabled = true;
    if (target) {
      target.dataset.state = 'loading';
      target.innerHTML = '<div class="am-empty">Loading original offers…</div>';
    }

    try {
      const result = await requestCatalog();
      const items = Array.isArray(result.items) ? result.items : [];
      const readyCount = items.filter((item) => item.local_payment_ready).length;
      if (summary) {
        summary.dataset.kind = readyCount ? 'success' : 'info';
        summary.textContent = String(items.length) + ' original offers · ' +
          String(readyCount) + ' locally ready · pricebook ' +
          String(result.pricebook_status || 'unknown') + ' (' +
          String(result.pricebook_version || 'unknown') + ')';
      }
      if (target) {
        target.dataset.state = items.length ? 'ready' : 'empty';
        target.innerHTML = items.length
          ? items.map(offerCard).join('')
          : '<div class="am-empty">No original offers are available.</div>';
      }
      loaded = true;
    } catch (error) {
      if (summary) {
        summary.dataset.kind = 'error';
        summary.textContent = failureMessage(error);
      }
      if (target) {
        target.dataset.state = 'error';
        target.innerHTML = '<div class="am-empty">' + escapeHtml(failureMessage(error)) + '</div>';
      }
    } finally {
      if (refresh) refresh.disabled = false;
    }
  }

  function bindCatalogNavigation() {
    const panel = document.querySelector('[data-am-panel="catalog"]');
    if (panel && !document.getElementById('am-catalog-offer-list')) installMarkup(panel);

    document.querySelectorAll('[data-am-section="catalog"], [data-am-open="catalog"]').forEach((button) => {
      button.addEventListener('click', function () {
        if (!loaded) loadCatalog();
      });
    });
  }

  window.PMK_ADMIN_MARKETPLACE_CATALOG = {
    load: loadCatalog,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindCatalogNavigation);
  } else {
    bindCatalogNavigation();
  }
})();
