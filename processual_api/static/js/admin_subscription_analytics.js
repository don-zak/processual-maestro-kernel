(function () {
  "use strict";

  const HOST_ID = "admin-subscription-analytics-host";
  const ENDPOINT = "/settings/admin/subscription-analytics";

  function getHost() {
    return document.getElementById(HOST_ID);
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function numberText(value) {
    const parsed = Number(value || 0);
    if (!Number.isFinite(parsed)) {
      return "0";
    }
    return parsed.toLocaleString();
  }

  function statusText(value) {
    const text = String(value || "").trim();
    return text || "not available";
  }

  function adminHeaders() {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === "function") {
      return auth.headers({});
    }
    return {};
  }

  function metric(label, value, options) {
    const detail = options && options.detail ? options.detail : "";
    const state = options && options.state ? options.state : "";

    return `
      <div class="admin-subscription-analytics-metric" data-state="${escapeHtml(state)}">
        <span class="admin-subscription-analytics-label">${escapeHtml(label)}</span>
        <span class="admin-subscription-analytics-value">
          <strong>${escapeHtml(numberText(value))}</strong>
          ${detail ? `<small>${escapeHtml(detail)}</small>` : ""}
        </span>
      </div>
    `;
  }

  function summaryPill(label, value) {
    return `
      <div class="admin-subscription-analytics-pill">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(numberText(value))}</strong>
      </div>
    `;
  }

  function allowanceNote(clients, usage) {
    const totalClients = Number(clients.total || 0);
    const allowance = Number(usage.monthly_units_allowance || 0);
    const used = Number(usage.monthly_units_used || 0);

    if (totalClients > 0 && allowance <= 0) {
      return `
        <div class="admin-subscription-analytics-note" data-state="not-wired">
          Monthly allowance data is not wired yet for these clients. The card is showing
          source-of-truth zeros instead of estimated or mock quota values.
        </div>
      `;
    }

    if (allowance > 0) {
      const percent = Math.min(100, Math.round((used / allowance) * 100));
      return `
        <div class="admin-subscription-analytics-note" data-state="ready">
          Monthly usage is at ${escapeHtml(percent)}% of the known allowance.
        </div>
      `;
    }

    return `
      <div class="admin-subscription-analytics-note" data-state="empty">
        No client allowance data is available yet.
      </div>
    `;
  }
  function planSourceDiagnostics(planSources) {
    const sources = planSources || {};
    const settings = Number(sources.settings || 0);
    const clientRequests = Number(sources.client_requests || 0);
    const missing = Number(sources.missing || 0);
    const total = settings + clientRequests + missing;

    if (total <= 0) {
      return "";
    }

    return `
      <div class="admin-subscription-analytics-plan-sources">
        <h3>Plan source diagnostics</h3>
        ${metric("Settings", settings)}
        ${metric("Client requests", clientRequests)}
        ${metric("Missing", missing, {
          detail: missing > 0 ? "No verified plan source" : "",
          state: missing > 0 ? "not-wired" : "",
        })}
        <div class="admin-subscription-analytics-note" data-state="not-wired">
          No verified plan source was found for these clients. Allowance remains
          source-of-truth zero until a plan is stored in settings, subscriptions,
          or an approved client request.
        </div>
      </div>
    `;
  }

  function renderRisk(riskItems) {
    if (!Array.isArray(riskItems) || riskItems.length === 0) {
      return `
        <div class="admin-subscription-analytics-empty">
          No subscription or quota risks detected.
        </div>
      `;
    }

    return riskItems
      .slice(0, 6)
      .map((item) => {
        const severity = statusText(item.severity);
        const kind = statusText(item.kind);
        const clientId = statusText(item.client_id);
        const planId = statusText(item.plan_id);
        const used = numberText(item.used);
        const limit = numberText(item.limit);
        const message = statusText(item.message);

        return `
          <li class="admin-subscription-analytics-risk" data-severity="${escapeHtml(severity)}">
            <strong>${escapeHtml(severity.toUpperCase())}: ${escapeHtml(kind)}</strong>
            <span>${escapeHtml(clientId)} · ${escapeHtml(planId)} · ${escapeHtml(used)} / ${escapeHtml(limit)}</span>
            <small>${escapeHtml(message)}</small>
          </li>
        `;
      })
      .join("");
  }

  function renderUnavailable(host, message) {
    host.innerHTML = `
      <section class="admin-card admin-subscription-analytics-card" aria-live="polite">
        <div class="admin-card-header">
          <div>
            <p class="admin-eyebrow">Admin analytics</p>
            <h2>Subscription &amp; Usage Analytics</h2>
          </div>
          <button type="button" data-admin-subscription-refresh>Refresh</button>
        </div>
        <p class="admin-muted">
          Subscription analytics are not available yet.
          ${escapeHtml(message || "")}
        </p>
      </section>
    `;
  }

  function renderAnalytics(host, payload) {
    const clients = payload.clients || {};
    const usage = payload.usage || {};
    const apiKeys = payload.api_keys || {};
    const subscriptions = payload.subscriptions || {};
    const plans = payload.plans || {};
    const risk = payload.risk || [];
    const planSources = payload.plan_sources || {};

    host.innerHTML = `
      <section class="admin-card admin-subscription-analytics-card" aria-live="polite">
        <div class="admin-card-header">
          <div>
            <p class="admin-eyebrow">Admin analytics</p>
            <h2>Subscription &amp; Usage Analytics</h2>
            <p class="admin-muted">
              Source of truth: <code>${escapeHtml(ENDPOINT)}</code>
            </p>
          </div>
          <button type="button" data-admin-subscription-refresh>Refresh</button>
        </div>

        <div class="admin-subscription-analytics-summary">
          ${summaryPill("Clients", clients.total)}
          ${summaryPill("Active subscriptions", subscriptions.active)}
          ${summaryPill("Monthly units", usage.monthly_units_used)}
          ${summaryPill("Risk indicators", Array.isArray(risk) ? risk.length : 0)}
        </div>

        <div class="admin-subscription-analytics-grid">
          <div>
            <h3>Clients</h3>
            ${metric("Total clients", clients.total)}
            ${metric("Active clients", clients.active)}
            ${metric("Pilot clients", clients.pilot)}
            ${metric("Suspended clients", clients.suspended)}
            ${metric("Expired clients", clients.expired)}
          </div>

          <div>
            <h3>Usage &amp; quota</h3>
            ${metric("Monthly units used", usage.monthly_units_used)}
            ${metric("Monthly allowance", usage.monthly_units_allowance, {
              detail: Number(clients.total || 0) > 0 && Number(usage.monthly_units_allowance || 0) <= 0
                ? "Not wired yet"
                : "",
              state: Number(clients.total || 0) > 0 && Number(usage.monthly_units_allowance || 0) <= 0
                ? "not-wired"
                : "",
            })}
            ${metric("Near quota limit", usage.near_quota_limit)}
            ${metric("Quota exceeded", usage.quota_exceeded)}
            ${allowanceNote(clients, usage)}
          </div>

          <div>
            <h3>API Keys</h3>
            ${metric("Active API keys", apiKeys.active)}
            ${metric("Revoked API keys", apiKeys.revoked)}
            ${metric("Client keys", apiKeys.client_keys)}
            ${metric("Billing keys", apiKeys.billing_keys)}
            ${metric("Ops keys", apiKeys.ops_keys)}
          </div>

          <div>
            <h3>Subscriptions</h3>
            ${metric("Active subscriptions", subscriptions.active)}
            ${metric("Trial subscriptions", subscriptions.trial)}
            ${metric("Past due", subscriptions.past_due)}
            ${metric("Cancelled", subscriptions.cancelled)}
            ${metric("Expired", subscriptions.expired)}
          </div>
        </div>

        <div class="admin-subscription-analytics-plans">
          <h3>Plans</h3>
          ${metric("Developer", plans.developer)}
          ${metric("Starter", plans.starter)}
          ${metric("Business", plans.business)}
          ${metric("Enterprise", plans.enterprise)}
          ${metric("Enterprise integration", plans.enterprise_integration)}
          ${metric("Unknown", plans.unknown)}
        </div>

        ${planSourceDiagnostics(planSources)}

        <div class="admin-subscription-analytics-risks">
          <h3>Risk indicators</h3>
          <ul>${renderRisk(risk)}</ul>
        </div>
      </section>
    `;
  }

  async function loadAnalytics() {
    const host = getHost();
    if (!host) {
      return;
    }

    host.dataset.adminSubscriptionAnalytics = "loading";
    host.innerHTML = `
      <section class="admin-card admin-subscription-analytics-card" aria-live="polite">
        <h2>Subscription &amp; Usage Analytics</h2>
        <p class="admin-muted">Loading subscription analytics...</p>
      </section>
    `;

    try {
      const response = await fetch(ENDPOINT, {
        headers: adminHeaders(),
        credentials: "include",
      });

      if (!response.ok) {
        renderUnavailable(host, `Request failed with status ${response.status}.`);
        host.dataset.adminSubscriptionAnalytics = "unavailable";
        return;
      }

      const payload = await response.json();
      renderAnalytics(host, payload || {});
      host.dataset.adminSubscriptionAnalytics = "ready";
    } catch (error) {
      renderUnavailable(host, error && error.message ? error.message : "Fetch failed.");
      host.dataset.adminSubscriptionAnalytics = "error";
    }
  }

  function bindRefresh() {
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-admin-subscription-refresh]");
      if (!button) {
        return;
      }
      event.preventDefault();
      loadAnalytics();
    });
  }

  function init() {
    bindRefresh();
    loadAnalytics();
  }

  window.PMK_ADMIN_SUBSCRIPTION_ANALYTICS = {
    load: loadAnalytics,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();