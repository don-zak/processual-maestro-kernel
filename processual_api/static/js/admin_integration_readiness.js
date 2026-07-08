(function () {
  const CARD_ID = "admin-integration-readiness-card";
  const BODY_ID = "admin-integration-readiness-body";
  const ENDPOINT = "/settings/admin/integration-readiness";

  function byId(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    const node = byId(id);
    if (node) node.textContent = value == null ? "-" : String(value);
  }

  function adminHeaders() {
    if (window.PMK_ADMIN_AUTH && typeof window.PMK_ADMIN_AUTH.headers === "function") {
      return window.PMK_ADMIN_AUTH.headers();
    }
    return { Accept: "application/json" };
  }

  function ensureCard() {
    if (byId(CARD_ID)) return byId(CARD_ID);
    const parent = document.querySelector("main") || document.body;
    const card = document.createElement("section");
    card.id = CARD_ID;
    card.className = "admin-card";
    card.setAttribute("aria-label", "Admin integration readiness");
    card.innerHTML = [
      "<h2>Integration Readiness</h2>",
      "<p class=\"muted\">Read-only integration readiness checks for supervisors. No raw secrets, no external HTTP, no runtime connector approval.</p>",
      "<div class=\"admin-grid\">",
      "<div><strong>Total checks</strong><span id=\"admin-integration-readiness-total\">-</span></div>",
      "<div><strong>Blocked</strong><span id=\"admin-integration-readiness-blocked\">-</span></div>",
      "<div><strong>Sandbox ready</strong><span id=\"admin-integration-readiness-sandbox-ready\">-</span></div>",
      "<div><strong>Production allowed</strong><span id=\"admin-integration-readiness-production\">0</span></div>",
      "<div><strong>Runtime connector approved</strong><span id=\"admin-integration-readiness-runtime\">0</span></div>",
      "</div>",
      "<pre id=\"admin-integration-readiness-body\" class=\"mono-block\">Loading integration readiness...</pre>",
    ].join("");
    parent.appendChild(card);
    return card;
  }

  function checkLine(check) {
    return [
      "readiness_check_id=" + (check.readiness_check_id || "-"),
      "adapter_contract_id=" + (check.adapter_contract_id || "-"),
      "credential_profile_id=" + (check.credential_profile_id || "-"),
      "status=" + (check.status || "-"),
      "sandbox_ready=" + String(check.sandbox_ready === true),
      "production_allowed=" + String(check.production_allowed === true),
      "runtime_connector_approved=" + String(check.runtime_connector_approved === true),
      "missing_inputs=" + ((check.missing_inputs || []).join(", ") || "-"),
      "missing_security_controls=" + ((check.missing_security_controls || []).join(", ") || "-"),
      "blocking_reasons=" + ((check.blocking_reasons || []).join(", ") || "-"),
      "next_action=" + (check.next_action || "-"),
    ].join(" | ");
  }

  function renderReadiness(data) {
    ensureCard();
    const summary = data && data.summary ? data.summary : {};
    const checks = Array.isArray(data && data.checks) ? data.checks : [];
    setText("admin-integration-readiness-total", summary.total || 0);
    setText("admin-integration-readiness-blocked", summary.blocked || 0);
    setText("admin-integration-readiness-sandbox-ready", summary.sandbox_ready || 0);
    setText("admin-integration-readiness-production", summary.production_allowed || 0);
    setText("admin-integration-readiness-runtime", summary.runtime_connector_approved || 0);
    const lines = checks.map(checkLine);
    lines.unshift("Integration readiness is read-only. Production and runtime connector approvals remain false.");
    setText(BODY_ID, lines.join("\n\n"));
  }

  async function loadIntegrationReadiness() {
    ensureCard();
    try {
      const response = await fetch(ENDPOINT, { credentials: "include", headers: adminHeaders() });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const data = await response.json();
      renderReadiness(data);
    } catch (error) {
      setText(BODY_ID, "Integration readiness unavailable: " + (error && error.message ? error.message : error));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadIntegrationReadiness);
  } else {
    loadIntegrationReadiness();
  }

  window.PMK_ADMIN_INTEGRATION_READINESS = { loadIntegrationReadiness };
})();
