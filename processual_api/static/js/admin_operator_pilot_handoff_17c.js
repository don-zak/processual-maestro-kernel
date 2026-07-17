(function () {
  "use strict";

  window.PMK_OPERATOR_PILOT_HANDOFF_17C_ENABLED = true;

  const API = {
    package: "/settings/admin/operator-pilot-handoff",
    actions: "/settings/admin/operator-pilot-handoff/actions-preview",
    progress: "/settings/admin/operator-pilot-handoff/progress",
    intakePreview: "/settings/admin/operator-pilot-handoff/intake-preview",
    export: "/settings/admin/operator-pilot-handoff/export"
  };

  const MANIFEST_TEMPLATE = {
    manifest_version: "pilot-handoff-intake-17c-r1",
    organization: {
      organization_id: "org_reference",
      display_name: "Organization pilot",
      sector: "telecom",
      technical_contact_ref: "contact://integration-team"
    },
    integration: {
      adapter_contract_id: "ticketing_adapter_reference",
      credential_profile_id: "telecom_operations_api_reference",
      target_environment: "sandbox",
      api_documentation_ref: "document://api-guide-v1",
      sandbox_base_url_ref: "target://sandbox-environment",
      authentication_method: "oauth2_client_credentials_reference",
      requested_scopes: ["ticketing:read"],
      sample_payload_refs: ["evidence://request-sample"]
    },
    network_security: {
      dns_names: ["sandbox.example.invalid"],
      tls_min_version: "1.2",
      outbound_allowlist_refs: ["allowlist://sandbox-v1"]
    },
    operations: {
      rate_limit_ref: "policy://rate-limit-v1",
      support_contact_ref: "contact://pilot-support",
      maintenance_window_ref: "window://sandbox-pilot"
    },
    governance: {
      data_classification: "restricted_metadata_only",
      retention_policy_ref: "policy://retention-v1",
      incident_contact_ref: "contact://security-incident"
    },
    evidence_refs: ["evidence://operator-approval-request"]
  };

  const state = {
    loadState: "loading",
    activeTab: "overview",
    package: null,
    actions: [],
    progress: [],
    intakePreview: null,
    intakeState: "idle",
    error: ""
  };

  const STATUS_LABELS = {
    pending_operator_inputs: "Waiting for organization inputs",
    pilot_handoff_pending_operator_inputs: "Waiting for organization inputs",
    pending_operator_input: "Input not received",
    requested: "Requested",
    received_for_review: "Received for review",
    needs_clarification: "Needs clarification",
    completed: "Reviewed",
    draft_review: "Draft review",
    ready_for_supervisor_review: "Ready for supervisor review",
    needs_input: "More information required"
  };

  function root() {
    return document.getElementById("operator-pilot-handoff-root");
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function label(value) {
    const raw = String(value == null ? "" : value);
    if (STATUS_LABELS[raw]) return STATUS_LABELS[raw];
    return raw.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function formatTimestamp(value) {
    if (!value) return "Not recorded";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
      timeZone: "UTC",
      timeZoneName: "short"
    }).format(date);
  }

  function safeArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function authHeaders(json) {
    let headers;
    if (window.PMK_ADMIN_AUTH && typeof window.PMK_ADMIN_AUTH.headers === "function") {
      headers = window.PMK_ADMIN_AUTH.headers();
    } else {
      headers = new Headers();
    }
    headers.set("Accept", "application/json");
    if (json) headers.set("Content-Type", "application/json");
    return headers;
  }

  async function fetchJson(url, options) {
    const request = Object.assign({ credentials: "same-origin" }, options || {});
    request.headers = authHeaders(Boolean(request.body));
    const response = await fetch(url, request);
    if (response.status === 401) {
      const error = new Error("Admin session expired");
      error.code = "unauthorized";
      throw error;
    }
    if (!response.ok) {
      let detail = "HTTP " + response.status;
      try {
        const payload = await response.json();
        detail = payload.detail || payload.message || detail;
      } catch (_error) {
        // A safe status message is enough; response bodies are never rendered.
      }
      const error = new Error(typeof detail === "string" ? detail : "Request rejected");
      error.code = "http_" + response.status;
      throw error;
    }
    return response.json();
  }

  function guardrailsAreSafe(payload) {
    const guardrails = (payload && payload.guardrails) || payload || {};
    return (
      guardrails.production_allowed === false &&
      guardrails.runtime_connector_approved === false &&
      guardrails.customer_credentials_present === false &&
      guardrails.external_http_allowed === false
    );
  }

  function normalizeActions(payload) {
    if (!payload || payload.read_only !== true || payload.preview_only !== true) return [];
    if (!guardrailsAreSafe(payload)) return [];
    return safeArray(payload.actions).filter((action) =>
      action && action.execution_mode === "copy_only" &&
      action.requires_credentials === false &&
      action.requires_production === false &&
      action.persistent_write_allowed === false
    );
  }

  function normalizeProgress(payload) {
    if (!payload || !guardrailsAreSafe(payload)) return [];
    return safeArray(payload.actions);
  }

  function progressFor(actionId) {
    return state.progress.find((item) => item.action_id === actionId) || {};
  }

  async function loadDashboard() {
    state.loadState = "loading";
    render();
    try {
      const results = await Promise.all([
        fetchJson(API.package),
        fetchJson(API.actions),
        fetchJson(API.progress)
      ]);
      if (!guardrailsAreSafe(results[0])) throw new Error("Unsafe package rejected");
      state.package = results[0];
      state.actions = normalizeActions(results[1]);
      state.progress = normalizeProgress(results[2]);
      state.loadState = "loaded";
    } catch (error) {
      state.loadState = error.code === "unauthorized" ? "unauthorized" : "backend_unavailable";
      state.error = error.message || "Dashboard data could not be loaded";
    }
    render();
  }

  function statusTone(value) {
    const current = String(value || "");
    if (/ready|reviewed|received|complete/.test(current)) return "good";
    if (/clarification|blocked|rejected/.test(current)) return "bad";
    return "warn";
  }

  function phaseRail() {
    const steps = [
      ["Inputs", "active"],
      ["Review", "next"],
      ["Sandbox setup", "locked"],
      ["Sandbox validation", "locked"],
      ["Pilot acceptance", "locked"],
      ["Production review", "locked"]
    ];
    return steps.map((step, index) => `
      <li class="pmk17c-phase ${step[1]}" aria-current="${step[1] === "active" ? "step" : "false"}">
        <span>${index + 1}</span><strong>${escapeHtml(step[0])}</strong>
      </li>`).join("");
  }

  function metric(title, value, tone, help) {
    return `<article class="pmk17c-metric ${tone || ""}">
      <span>${escapeHtml(title)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(help || "")}</small>
    </article>`;
  }

  function renderOverview(pkg) {
    const required = safeArray(pkg.required_inputs).length;
    const received = state.progress.filter((item) =>
      ["received_for_review", "completed"].includes(item.status)
    ).length;
    const blockers = state.actions.filter((action) =>
      !["completed", "received_for_review"].includes(progressFor(action.action_id).status)
    ).length;
    return `
      <section class="pmk17c-summary-grid" aria-label="Pilot executive summary">
        ${metric("Required inputs", required || state.actions.length, "", "Reference fields and evidence")}
        ${metric("Received", received, received ? "good" : "", "Available for review")}
        ${metric("Open review items", blockers, blockers ? "warn" : "good", "No automatic approvals")}
        ${metric("Sandbox", pkg.pilot_ready ? "Ready" : "Not ready", pkg.pilot_ready ? "good" : "warn", "Qualification remains separate")}
        ${metric("Production", "Not eligible", "locked", "Explicitly blocked")}
        ${metric("Runtime", "Disabled", "locked", "No connector authority")}
      </section>
      <section class="pmk17c-overview-grid">
        <article class="pmk17c-panel pmk17c-next">
          <div class="pmk17c-kicker">Current decision</div>
          <h3>Collect and validate the organization manifest</h3>
          <p>Import reference-only integration data, resolve missing fields, then route the safe assessment to the supervisor review queue.</p>
          <button class="pmk17c-primary" type="button" data-open-tab="intake">Open Intake &amp; Validation</button>
        </article>
        <article class="pmk17c-panel">
          <div class="pmk17c-panel-head"><div><div class="pmk17c-kicker">Blocking reasons</div><h3>${blockers} open items</h3></div><span class="pmk17c-badge warn">Input phase</span></div>
          <ul class="pmk17c-clean-list">
            <li><span>01</span><div><strong>Organization references</strong><small>Documentation, target, scopes and samples</small></div></li>
            <li><span>02</span><div><strong>Network controls</strong><small>DNS, TLS and outbound allowlist references</small></div></li>
            <li><span>03</span><div><strong>Supervisor review</strong><small>Evidence-based decision before sandbox qualification</small></div></li>
          </ul>
        </article>
      </section>`;
  }

  function manifestTemplateText() {
    return JSON.stringify(MANIFEST_TEMPLATE, null, 2);
  }

  function renderIntake() {
    return `
      <section class="pmk17c-intake-flow" aria-label="How integration data reaches Maestro">
        <div class="pmk17c-flow-step"><span>1</span><div><strong>Prepare</strong><small>References only; never secret values</small></div></div>
        <div class="pmk17c-flow-step"><span>2</span><div><strong>Import</strong><small>Upload JSON or paste a manifest</small></div></div>
        <div class="pmk17c-flow-step"><span>3</span><div><strong>Validate</strong><small>Schema, completeness and policy checks</small></div></div>
        <div class="pmk17c-flow-step"><span>4</span><div><strong>Review</strong><small>Supervisor evidence queue</small></div></div>
      </section>
      <aside class="pmk17c-intake-boundary">
        <div><strong>Send to Maestro here</strong><span>Organization IDs, API-document references, sandbox target references, scopes, DNS/TLS metadata, operating-policy references and evidence references.</span></div>
        <div><strong>Never send here</strong><span>Passwords, tokens, private keys or secret values. Those belong to a separately approved vault binding after the readiness review.</span></div>
      </aside>
      <section class="pmk17c-method-grid">
        <article class="pmk17c-method active"><span>Recommended</span><h3>Safe JSON manifest</h3><p>Upload the standard reference package. The browser checks it before a non-persistent backend preview.</p></article>
        <article class="pmk17c-method"><span>Guided</span><h3>Paste manifest</h3><p>Paste the same schema when the organization sends data through a controlled channel.</p></article>
        <article class="pmk17c-method"><span>API</span><h3>Automated intake</h3><p>Authenticated systems can call the preview endpoint using the same schema and review rules.</p><code>POST ${API.intakePreview}</code></article>
      </section>
      <section class="pmk17c-panel pmk17c-intake-workbench">
        <div class="pmk17c-panel-head">
          <div><div class="pmk17c-kicker">Reference-only intake</div><h3>Integration manifest</h3></div>
          <div class="pmk17c-inline-actions">
            <button type="button" class="pmk17c-secondary" id="pmk17c-load-template">Load template</button>
            <button type="button" class="pmk17c-secondary" id="pmk17c-download-template">Download template</button>
          </div>
        </div>
        <label class="pmk17c-dropzone" for="pmk17c-manifest-file" id="pmk17c-dropzone">
          <input id="pmk17c-manifest-file" type="file" accept="application/json,.json">
          <strong>Drop a JSON manifest here</strong>
          <small>Maximum 256 KB · secret-bearing fields are rejected</small>
        </label>
        <label class="pmk17c-textarea-label" for="pmk17c-manifest-text">Or paste the safe manifest</label>
        <textarea id="pmk17c-manifest-text" rows="12" spellcheck="false" placeholder="Paste the pilot-handoff-intake-17c-r1 JSON manifest"></textarea>
        <div class="pmk17c-intake-footer">
          <div class="pmk17c-safety-note"><strong>No persistence in R1.</strong> The preview returns counts, missing fields and a digest; it does not echo the submitted manifest.</div>
          <button type="button" class="pmk17c-primary" id="pmk17c-validate-manifest">Validate package</button>
        </div>
        <div id="pmk17c-intake-result" class="pmk17c-intake-result" data-state="${escapeHtml(state.intakeState)}" aria-live="polite">${renderIntakeResult()}</div>
      </section>`;
  }

  function renderIntakeResult() {
    if (state.intakeState === "idle") return "No manifest has been evaluated in this session.";
    if (state.intakeState === "loading") return "Validating structure, completeness and safety policy…";
    if (state.intakeState === "error") return `<strong>Package rejected.</strong> ${escapeHtml(state.error)}`;
    const preview = state.intakePreview || {};
    const missing = safeArray(preview.missing_fields);
    return `<div class="pmk17c-result-head">
        <div><span>Assessment</span><strong>${escapeHtml(label(preview.status))}</strong></div>
        <div class="pmk17c-score"><strong>${escapeHtml(preview.completeness_percent)}%</strong><span>complete</span></div>
      </div>
      <div class="pmk17c-result-meta"><span>Digest ${escapeHtml(preview.manifest_digest || "—")}</span><span>Persisted: No</span><span>External calls: None</span></div>
      ${missing.length ? `<div class="pmk17c-missing"><strong>Missing fields</strong><ul>${missing.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>` : `<p class="pmk17c-ready-note">The reference package can enter supervisor review. This is not sandbox authorization.</p>`}`;
  }

  function actionRows() {
    if (!state.actions.length) return `<tr><td colspan="6" class="pmk17c-empty-cell">No case-specific input actions are available.</td></tr>`;
    return state.actions.map((action) => {
      const progress = progressFor(action.action_id);
      const current = progress.status || "pending_operator_input";
      return `<tr>
        <td><strong>${escapeHtml(action.title || label(action.action_id))}</strong><small>${escapeHtml(action.purpose || action.description || "Reference required for review")}</small></td>
        <td>${escapeHtml(action.requested_from || action.owner || "Organization")}</td>
        <td><span class="pmk17c-badge ${statusTone(current)}">${escapeHtml(label(current))}</span></td>
        <td>${escapeHtml(progress.reference || "Not attached")}</td>
        <td>${escapeHtml(progress.updated_at || "—")}</td>
        <td>${escapeHtml(progress.note || "Awaiting safe reference")}</td>
      </tr>`;
    }).join("");
  }

  function renderInputs() {
    return `<section class="pmk17c-panel pmk17c-table-panel">
      <div class="pmk17c-panel-head"><div><div class="pmk17c-kicker">Case-specific data</div><h3>Required inputs</h3></div><span class="pmk17c-badge">${state.actions.length} items</span></div>
      <div class="pmk17c-table-wrap"><table><thead><tr><th>Input</th><th>Requested from</th><th>Status</th><th>Reference</th><th>Last update</th><th>Next action</th></tr></thead><tbody>${actionRows()}</tbody></table></div>
    </section>`;
  }

  function renderReviews(pkg) {
    const controls = [
      ["Production access", "Blocked by policy", "Integration supervisor", "Yes"],
      ["Runtime connector", "Disabled", "Platform owner", "Yes"],
      ["Customer credential values", "Not accepted", "Security", "Yes"],
      ["External HTTP", "Disabled", "Network security", "Yes"],
      ["Sandbox qualification", pkg.pilot_ready ? "Ready for review" : "Pending evidence", "Pilot owner", "Yes"]
    ];
    return `<section class="pmk17c-panel pmk17c-table-panel">
      <div class="pmk17c-panel-head"><div><div class="pmk17c-kicker">Decision boundaries</div><h3>Reviews &amp; controls</h3></div><span class="pmk17c-badge locked">Default deny</span></div>
      <div class="pmk17c-table-wrap"><table><thead><tr><th>Control</th><th>Status</th><th>Owner</th><th>Blocking?</th><th>Evidence</th></tr></thead><tbody>${controls.map((row) => `<tr><td><strong>${row[0]}</strong></td><td><span class="pmk17c-badge locked">${row[1]}</span></td><td>${row[2]}</td><td>${row[3]}</td><td>Reference required</td></tr>`).join("")}</tbody></table></div>
    </section>`;
  }

  function renderPlan() {
    const stages = [
      ["Organization inputs", "Organization integration team", "In progress", "Provide safe manifest"],
      ["Contract review", "Solution architect", "Pending", "Review API and scope references"],
      ["Security review", "Security and network", "Pending", "Review DNS, TLS and allowlist evidence"],
      ["Sandbox setup", "Pilot owner", "Locked", "Requires reviewed evidence"],
      ["Pilot acceptance", "Business owner", "Locked", "Requires sandbox validation"],
      ["Production review", "Authorized supervisor", "Locked", "Separate governed phase"]
    ];
    return `<section class="pmk17c-panel pmk17c-table-panel">
      <div class="pmk17c-panel-head"><div><div class="pmk17c-kicker">Controlled sequence</div><h3>Pilot plan</h3></div></div>
      <div class="pmk17c-table-wrap"><table><thead><tr><th>Stage</th><th>Owner</th><th>Status</th><th>Next action</th><th>Blocking reason</th></tr></thead><tbody>${stages.map((row, index) => `<tr><td><strong>${index + 1}. ${row[0]}</strong></td><td>${row[1]}</td><td><span class="pmk17c-badge ${index ? "locked" : "warn"}">${row[2]}</span></td><td>${row[3]}</td><td>${index ? "Prior stage incomplete" : "Manifest not reviewed"}</td></tr>`).join("")}</tbody></table></div>
    </section>`;
  }

  function renderEvidence() {
    const preview = state.intakePreview;
    return `<section class="pmk17c-panel pmk17c-table-panel">
      <div class="pmk17c-panel-head"><div><div class="pmk17c-kicker">Safe metadata only</div><h3>Evidence &amp; audit</h3></div><span class="pmk17c-badge">Append-only target</span></div>
      <div class="pmk17c-table-wrap"><table><thead><tr><th>Evidence type</th><th>Safe reference</th><th>Digest</th><th>Actor reference</th><th>Status</th></tr></thead><tbody>
        ${preview ? `<tr><td><strong>Intake preview</strong></td><td>Session-only assessment</td><td>${escapeHtml(preview.manifest_digest)}</td><td>Authenticated admin</td><td><span class="pmk17c-badge good">Validated</span></td></tr>` : `<tr><td colspan="5" class="pmk17c-empty-cell">No case evidence has been attached. Import a safe manifest to generate a non-persistent assessment digest.</td></tr>`}
      </tbody></table></div>
      <div class="pmk17c-policy-strip"><span>Never displayed</span><strong>Secret values</strong><strong>Access tokens</strong><strong>Passwords</strong><strong>Sensitive request bodies</strong></div>
    </section>`;
  }

  function activeContent(pkg) {
    if (state.activeTab === "intake") return renderIntake();
    if (state.activeTab === "inputs") return renderInputs();
    if (state.activeTab === "reviews") return renderReviews(pkg);
    if (state.activeTab === "plan") return renderPlan();
    if (state.activeTab === "evidence") return renderEvidence();
    return renderOverview(pkg);
  }

  function renderShell(pkg) {
    const status = pkg.handoff_status || pkg.package_status || "pending_operator_inputs";
    const updatedAt = pkg.updated_at || "";
    return `<section class="pmk17c-shell" data-phase="pilot-handoff-17c-r1" data-load-state="${escapeHtml(state.loadState)}" data-active-tab="${escapeHtml(state.activeTab)}" data-production-allowed="false" data-runtime-connector-approved="false">
      <header class="pmk17c-hero">
        <div class="pmk17c-hero-main">
          <div class="pmk17c-kicker">Pilot handoff · governed integration</div>
          <div class="pmk17c-title-row"><h2>Integration Pilot Workspace</h2><span class="pmk17c-badge ${statusTone(status)}">${escapeHtml(label(status))}</span></div>
          <p>One place to receive integration references, evaluate readiness, coordinate reviews and prepare a sandbox pilot—without exposing credentials or granting runtime authority.</p>
        </div>
        <div class="pmk17c-hero-actions">
          <button type="button" class="pmk17c-secondary" id="pmk17c-refresh">Refresh</button>
          <button type="button" class="pmk17c-secondary" id="pmk17c-export">Export handoff</button>
        </div>
        <dl class="pmk17c-identity">
          <div><dt>Pilot ID</dt><dd>${escapeHtml(pkg.case_id || pkg.package_id || "Unassigned")}</dd></div>
          <div><dt>Organization</dt><dd>${escapeHtml(pkg.organization_name || "Awaiting selection")}</dd></div>
          <div><dt>Sector</dt><dd>${escapeHtml(label(pkg.sector || "Not selected"))}</dd></div>
          <div><dt>Environment</dt><dd>Sandbox</dd></div>
          <div><dt>Owner</dt><dd>${escapeHtml(pkg.owner || "Integration supervisor")}</dd></div>
          <div><dt>Last updated</dt><dd title="${escapeHtml(updatedAt)}">${escapeHtml(formatTimestamp(updatedAt))}</dd></div>
        </dl>
        <ol class="pmk17c-phase-rail">${phaseRail()}</ol>
      </header>
      <nav class="pmk17c-tabs" aria-label="Pilot handoff sections">
        ${[["overview","Overview"],["intake","Intake & Validation"],["inputs","Required Inputs"],["reviews","Reviews & Controls"],["plan","Pilot Plan"],["evidence","Evidence & Audit"]].map((tab) => `<button type="button" role="tab" aria-selected="${state.activeTab === tab[0]}" class="${state.activeTab === tab[0] ? "active" : ""}" data-pmk17c-tab="${tab[0]}">${tab[1]}</button>`).join("")}
      </nav>
      <main class="pmk17c-content" data-pmk17c-panel="${escapeHtml(state.activeTab)}">${activeContent(pkg)}</main>
    </section>`;
  }

  function render() {
    const host = root();
    if (!host) return;
    host.dataset.phase = "pilot-handoff-17c-r1";
    host.dataset.loadState = state.loadState;
    host.dataset.activeTab = state.activeTab;
    host.dataset.productionAllowed = "false";
    host.dataset.runtimeConnectorApproved = "false";

    if (state.loadState === "loading") {
      host.innerHTML = `<section class="pmk17c-state"><span class="pmk17c-spinner"></span><h2>Loading Pilot Handoff</h2><p>Gathering the package, review actions and progress metadata.</p></section>`;
      return;
    }
    if (state.loadState === "unauthorized") {
      host.innerHTML = `<section class="pmk17c-state error"><span>Session</span><h2>Admin session expired</h2><p>Sign in again to load case-specific integration data.</p><a class="pmk17c-primary" href="/login">Sign in again</a></section>`;
      return;
    }
    if (state.loadState !== "loaded" || !state.package) {
      host.innerHTML = `<section class="pmk17c-state error"><span>Unavailable</span><h2>Pilot data could not be loaded</h2><p>${escapeHtml(state.error || "The backend is unavailable or returned an unsafe payload.")}</p><button class="pmk17c-primary" type="button" id="pmk17c-retry">Try again</button></section>`;
      const retry = document.getElementById("pmk17c-retry");
      if (retry) retry.addEventListener("click", loadDashboard);
      return;
    }

    host.innerHTML = renderShell(state.package);
    bindInteractions();
  }

  function parseManifestText(text) {
    if (!text || !text.trim()) throw new Error("Choose a JSON file or paste a manifest first.");
    if (text.length > 262144) throw new Error("Manifest exceeds the 256 KB limit.");
    let manifest;
    try {
      manifest = JSON.parse(text);
    } catch (_error) {
      throw new Error("Manifest is not valid JSON.");
    }
    if (!manifest || Array.isArray(manifest) || typeof manifest !== "object") {
      throw new Error("Manifest must be one JSON object.");
    }
    const serialized = JSON.stringify(manifest).toLowerCase();
    const forbidden = ["client_secret", "api_key", "access_token", "refresh_token", "password", "private_key", "authorization"];
    if (forbidden.some((marker) => serialized.includes('"' + marker + '"'))) {
      throw new Error("Secret-bearing fields are prohibited. Replace values with controlled references.");
    }
    return manifest;
  }

  async function validateManifest() {
    const textarea = document.getElementById("pmk17c-manifest-text");
    try {
      const manifest = parseManifestText(textarea ? textarea.value : "");
      state.intakeState = "loading";
      state.error = "";
      updateIntakeResult();
      state.intakePreview = await fetchJson(API.intakePreview, {
        method: "POST",
        body: JSON.stringify(manifest)
      });
      state.intakeState = "loaded";
    } catch (error) {
      state.intakeState = "error";
      state.error = error.message || "Manifest validation failed";
    }
    updateIntakeResult();
  }

  function updateIntakeResult() {
    const target = document.getElementById("pmk17c-intake-result");
    if (!target) return;
    target.dataset.state = state.intakeState;
    target.innerHTML = renderIntakeResult();
  }

  function downloadText(filename, text) {
    const blob = new Blob([text], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function bindInteractions() {
    document.querySelectorAll("[data-pmk17c-tab], [data-open-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        state.activeTab = button.dataset.pmk17cTab || button.dataset.openTab || "overview";
        render();
      });
    });
    const refresh = document.getElementById("pmk17c-refresh");
    if (refresh) refresh.addEventListener("click", loadDashboard);
    const exportButton = document.getElementById("pmk17c-export");
    if (exportButton) exportButton.addEventListener("click", () => window.open(API.export, "_blank", "noopener"));
    const loadTemplate = document.getElementById("pmk17c-load-template");
    if (loadTemplate) loadTemplate.addEventListener("click", () => {
      const textarea = document.getElementById("pmk17c-manifest-text");
      if (textarea) textarea.value = manifestTemplateText();
    });
    const downloadTemplate = document.getElementById("pmk17c-download-template");
    if (downloadTemplate) downloadTemplate.addEventListener("click", () => downloadText("pilot-handoff-intake-17c-r1.json", manifestTemplateText()));
    const validateButton = document.getElementById("pmk17c-validate-manifest");
    if (validateButton) validateButton.addEventListener("click", validateManifest);
    const input = document.getElementById("pmk17c-manifest-file");
    if (input) input.addEventListener("change", async () => {
      const file = input.files && input.files[0];
      if (!file) return;
      if (file.size > 262144) {
        state.intakeState = "error";
        state.error = "Manifest exceeds the 256 KB limit.";
        updateIntakeResult();
        return;
      }
      const textarea = document.getElementById("pmk17c-manifest-text");
      if (textarea) textarea.value = await file.text();
    });
    const dropzone = document.getElementById("pmk17c-dropzone");
    if (dropzone && input) {
      dropzone.addEventListener("dragover", (event) => {
        event.preventDefault();
        dropzone.dataset.dragging = "true";
      });
      dropzone.addEventListener("dragleave", () => {
        dropzone.dataset.dragging = "false";
      });
      dropzone.addEventListener("drop", async (event) => {
        event.preventDefault();
        dropzone.dataset.dragging = "false";
        const file = event.dataTransfer && event.dataTransfer.files[0];
        if (!file) return;
        if (file.size > 262144) {
          state.intakeState = "error";
          state.error = "Manifest exceeds the 256 KB limit.";
          updateIntakeResult();
          return;
        }
        const textarea = document.getElementById("pmk17c-manifest-text");
        if (textarea) textarea.value = await file.text();
      });
    }
  }

  function init() {
    loadDashboard();
  }

  window.PMK_OPERATOR_PILOT_HANDOFF_17C = {
    api: API,
    manifestTemplate: MANIFEST_TEMPLATE,
    reload: loadDashboard,
    render
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
