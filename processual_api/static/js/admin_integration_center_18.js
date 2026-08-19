(function () {
  "use strict";

  const API = {
    tracking: "/settings/admin/integration-readiness-tracking",
    cases: "/settings/admin/integration-readiness-tracking/cases",
    handoff: "/settings/admin/operator-pilot-handoff",
    progress: "/settings/admin/operator-pilot-handoff/progress",
    camaraQod: "/settings/admin/integration-center/camara-qod-qualification",
  };

  const TABS = [
    ["overview", "Overview"],
    ["cases", "Cases"],
    ["platforms", "Platforms & standards"],
    ["security", "Network & security"],
    ["secrets", "Secrets operations"],
    ["evidence", "Evidence"],
  ];

  const state = {
    tracking: null,
    cases: [],
    handoff: null,
    progress: [],
    camaraQod: null,
    active: "overview",
    loading: true,
    error: "",
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(
      /[&<>"']/g,
      (character) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[character]
    );
  }

  function authHeaders() {
    if (window.PMK_ADMIN_AUTH && typeof window.PMK_ADMIN_AUTH.headers === "function") {
      return window.PMK_ADMIN_AUTH.headers();
    }
    return new Headers({ Accept: "application/json" });
  }

  async function getJson(url) {
    const response = await fetch(url, {
      credentials: "same-origin",
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function metric(label, value, help) {
    return `
      <article class="ic18-metric">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
        <small class="ic18-muted">${escapeHtml(help || "")}</small>
      </article>`;
  }

  function pill(text, tone) {
    return `<span class="ic18-pill ${tone || ""}">${escapeHtml(text)}</span>`;
  }

  function phaseRail() {
    const phases = ["Inputs", "Review", "Sandbox setup", "Sandbox validation", "Pilot acceptance", "Production review"];
    return phases
      .map((phase, index) => {
        const stateClass = index === 0 ? "active" : index > 1 ? "locked" : "";
        return `<div class="ic18-step ${stateClass}"><span>0${index + 1}</span><strong>${escapeHtml(phase)}</strong></div>`;
      })
      .join("");
  }

  function normalizedCases() {
    const payload = state.cases || {};
    return asArray(payload.cases || payload.items || payload);
  }

  function counts() {
    const cases = normalizedCases();
    const openCases = cases.filter(
      (item) => !["completed", "approved", "closed"].includes(String(item.status || "").toLowerCase())
    ).length;
    const progress = asArray(state.progress.actions || state.progress);
    const received = progress.filter((item) => ["received_for_review", "completed"].includes(item.status)).length;
    return { cases: cases.length, open: openCases, received, blockers: Math.max(0, progress.length - received) };
  }

  function statusTone(status) {
    const value = String(status || "").toLowerCase();
    if (/complete|ready|approved|registered|verified|healthy|allowed|passed|pinned|proven/.test(value)) return "good";
    if (/reject|block|fail|expired|no-go|not qualified|disabled|not proven|not approved/.test(value)) return "locked";
    return "warn";
  }

  function rows(items, emptyMessage) {
    if (!items.length) return `<div class="ic18-empty">${escapeHtml(emptyMessage)}</div>`;
    return `<div class="ic18-list">${items
      .map((item) => {
        const title = item.title || item.display_name || item.case_id || item.action_id || "Integration item";
        const status = item.status || item.sector || item.description || "Awaiting review";
        return `<div class="ic18-row"><div><strong>${escapeHtml(title)}</strong><span>${escapeHtml(item.description || status)}</span></div>${pill(String(status).replace(/_/g, " "), statusTone(status))}</div>`;
      })
      .join("")}</div>`;
  }

  function readinessStep(label, status, help) {
    const tone = statusTone(status);
    return `<div class="ic18-readiness-step ${tone}"><span class="ic18-readiness-dot" aria-hidden="true"></span><div><strong>${escapeHtml(label)}</strong><small>${escapeHtml(help)}</small></div>${pill(status, tone)}</div>`;
  }

  function platformCard(platform) {
    return `
      <article class="ic18-platform-card">
        <div class="ic18-platform-head"><div><span class="ic18-platform-kicker">${escapeHtml(platform.family)}</span><h3>${escapeHtml(platform.title)}</h3><p>${escapeHtml(platform.description)}</p></div>${pill(platform.verdict, statusTone(platform.verdict))}</div>
        <div class="ic18-platform-meta"><div><span>Contract</span><strong>${escapeHtml(platform.contract)}</strong></div><div><span>Sandbox</span><strong>${escapeHtml(platform.sandbox)}</strong></div><div><span>Production</span><strong>${escapeHtml(platform.production)}</strong></div></div>
        <div class="ic18-readiness-list">${platform.steps.map((step) => readinessStep(step[0], step[1], step[2])).join("")}</div>
        <div class="ic18-platform-foot"><span>${escapeHtml(platform.note)}</span></div>
      </article>`;
  }

  function camaraQodPlatform() {
    const payload = state.camaraQod;
    const routeBacked = Boolean(payload && payload.status === "reviewed_qualification_contract");
    const callableOperations = routeBacked ? asArray(payload.callable_operations) : [];
    const governanceTasks = routeBacked ? asArray(payload.candidate_task_ids) : [];
    const governanceEntitlements = routeBacked ? asArray(payload.candidate_entitlement_ids) : [];
    const governanceQuotas = routeBacked ? asArray(payload.candidate_quota_meters) : [];
    const external = routeBacked && payload.external_sandbox_evidence ? payload.external_sandbox_evidence : {};
    const compatibility = routeBacked && payload.telefonica_compatibility ? payload.telefonica_compatibility : {};

    const sourceEnabled = routeBacked && payload.server_trusted_source_enabled === true;
    const semanticReviewed = routeBacked && payload.semantic_mapping_state === "proposal_only" && callableOperations.length === 5;
    const governanceApproved =
      routeBacked &&
      payload.governance_candidate_state === "review_required" &&
      payload.governance_candidate_valid === true &&
      payload.governance_approved === true &&
      payload.governance_decision === "approved_with_conditions" &&
      governanceTasks.length === 5 &&
      governanceEntitlements.length === 2 &&
      governanceQuotas.length === 5;
    const runtimeRegistered = routeBacked && payload.runtime_task_registered === true;
    const runtimeDefaultDeny = routeBacked && payload.runtime_default_deny === true;
    const liveProven = routeBacked && payload.live_source_acquisition_proven === true;
    const externalMockProven = routeBacked && external.external_mock_sandbox_proven === true;
    const externalDivergence = routeBacked && external.mock_documentation_divergence_observed === true;
    const providerSandboxProven = routeBacked && payload.provider_sandbox_proven === true;
    const providerNetworkProven = routeBacked && payload.provider_network_proof === true;
    const runtimeConnectorApproved = routeBacked && payload.runtime_connector_approved === true;
    const productionAllowed = routeBacked && payload.production_allowed === true;

    const version = routeBacked && payload.api_version ? payload.api_version : "1.1.0";
    const revision = routeBacked && payload.source_revision ? payload.source_revision : "9cb179fd3b63f43d564c76689295cd681e723548";
    const path = routeBacked && payload.source_path ? payload.source_path : "code/API_definitions/quality-on-demand.yaml";
    const repository = routeBacked && payload.repository ? payload.repository : "camaraproject/QualityOnDemand";

    const sourceStatus = sourceEnabled ? "Policy enabled" : "Pending";
    const semanticStatus = semanticReviewed ? "Reviewed proposal" : "Pending";
    const governanceStatus = governanceApproved ? "Approved" : "Pending";
    const runtimeStatus = runtimeRegistered && runtimeDefaultDeny ? "Registered / default-deny" : "Not registered";
    const liveStatus = liveProven ? "Proven" : "Not proven";
    const externalStatus = externalMockProven ? (externalDivergence ? "Proven / divergence present" : "Proven") : "Not proven";
    const providerNetworkStatus = providerNetworkProven ? "Proven" : "Not proven";
    const connectorStatus = runtimeConnectorApproved ? "Approved" : "Not approved";
    const productionStatus = productionAllowed ? "Allowed" : "Blocked";

    const compatibilityState = compatibility.compatibility_state || "not_proven";
    const note = routeBacked
      ? `Server-owned status: governance ${governanceApproved ? "approved" : "not approved"}; runtime tasks ${runtimeRegistered ? "registered" : "not registered"}${runtimeDefaultDeny ? " with default-deny" : ""}; external Telefónica mock ${externalMockProven ? "interoperability proven" : "not proven"}${externalDivergence ? " with documented divergence" : ""}; provider network ${providerNetworkProven ? "proven" : "not proven"}; runtime connector ${runtimeConnectorApproved ? "approved" : "not approved"}; production ${productionAllowed ? "allowed" : "blocked"}. Pinned source: ${repository} @ ${revision.slice(0, 7)} · ${path}.`
      : "Qualification status route unavailable. Conservative fallback keeps trusted-source enablement, live acquisition, governance approval, provider sandbox and runtime authority unproven. Pinned candidate: camaraproject/QualityOnDemand @ 9cb179f · code/API_definitions/quality-on-demand.yaml.";

    return {
      family: "CAMARA · GSMA Open Gateway",
      title: "Quality on Demand · r3.2 candidate",
      description: "Reviewed public CAMARA release candidate with a server-owned qualification projection. Specification, policy enablement, semantic review, governance approval, runtime registration, external mock evidence, provider proof and production authority remain separate gates.",
      verdict: governanceApproved ? "Governance approved" : "Spec candidate pinned",
      contract: `QoD v${version}`,
      sandbox: providerSandboxProven ? "Proven" : "Not proven",
      production: productionStatus,
      note,
      steps: [
        ["Architecture family", "Ready", "CAMARA is recognized in the governed integration contract model."],
        ["Reviewed release candidate", "Pinned", `Public r3.2 / QoD v${version} is bound to the reviewed immutable source.`],
        ["Server-enabled trusted source", sourceStatus, sourceEnabled ? "The deployment-owned catalog exactly enables the reviewed source tuple; this grants acquisition policy only, not runtime authority." : "A deployment-owned allowlist must exactly enable the reviewed source; code presence alone grants no authority."],
        ["Live source acquisition", liveStatus, liveProven ? "The safe server projection reports retained public-source acquisition evidence." : "No retained live public-source qualification evidence is reported by the server projection."],
        ["Semantic task mapping", semanticStatus, semanticReviewed ? `${callableOperations.length} outbound operations have a reviewed proposal and drift gate.` : "Reviewed operation-to-task semantics are not available from the server projection."],
        ["Governance approval", governanceStatus, governanceApproved ? `${governanceTasks.length} task contracts, ${governanceEntitlements.length} entitlements and ${governanceQuotas.length} quota meters are approved with conditions for the exact governed contract.` : "The exact governance approval is not reported by the server projection."],
        ["Runtime task registration", runtimeStatus, runtimeRegistered && runtimeDefaultDeny ? "The five approved runtime tasks are registered and remain fail-closed by default." : "Runtime task registration/default-deny is not fully reported."],
        ["External Telefónica sandbox", externalStatus, externalMockProven ? `Mock interoperability evidence is retained separately from provider authority; compatibility=${compatibilityState}.` : "No external mock interoperability proof is reported."],
        ["Provider network", providerNetworkStatus, providerNetworkProven ? "Operator-network QoS evidence is reported." : "Operator-network QoS remains unproven; external mock evidence does not satisfy this gate."],
        ["Runtime connector", connectorStatus, runtimeConnectorApproved ? "An independently reviewed runtime connector is approved." : "Runtime connector approval remains explicitly false."],
        ["Production approval", productionStatus, productionAllowed ? "Production authority is explicitly granted." : "Governance approval, runtime registration or external mock proof cannot implicitly grant production authority."],
      ],
    };
  }

  function platformsView() {
    const platforms = [
      camaraQodPlatform(),
      {
        family: "TM Forum Open APIs",
        title: "TM Forum qualification profile",
        description: "Existing ticketing and order-management references are architecture contracts; provider API version and CTK evidence remain case scoped.",
        verdict: "Contract only",
        contract: "References present",
        sandbox: "Unproven",
        production: "Blocked",
        note: "Provider-specific conformance must be demonstrated against an exact API version and sandbox target.",
        steps: [
          ["Reference contracts", "Ready", "Ticketing and order management use the TM Forum contract family."],
          ["Provider API version", "Pending", "External API versions remain operator/provider inputs."],
          ["Endpoint mapping", "Pending", "Discovery provenance and canonical request/response mappings required."],
          ["Live provider proof", "Blocked", "No live external-network qualification is claimed here."],
        ],
      },
      {
        family: "Operator & enterprise APIs",
        title: "Case-scoped proprietary integrations",
        description: "Legacy, proprietary and generic enterprise integrations use the same discovery, binding, secret-reference and sandbox evidence pipeline.",
        verdict: "Case scoped",
        contract: "Supported",
        sandbox: "Per case",
        production: "Blocked",
        note: "No hostname, credential or provider assumption is promoted globally across customers.",
        steps: [
          ["Adapter contract", "Ready", "Canonical sector/domain boundaries exist."],
          ["Endpoint discovery", "Pending", "Review-pinned OpenAPI/Swagger description required when available."],
          ["Credential reference", "Pending", "Secret material remains outside endpoint configuration."],
          ["Acceptance evidence", "Pending", "Case-specific sandbox proof and cleanup are required."],
        ],
      },
    ];

    return `<div class="ic18-section-intro"><div><p class="ic18-eyebrow">Standards readiness</p><h2>Platform qualification, not logo compatibility</h2><p>Every platform is separated into architecture, reviewed specification, server enablement, live acquisition, semantic mapping, governance approval, runtime registration, provider proof and production approval so evidence is never presented as authority.</p></div><div class="ic18-legend" aria-label="Readiness legend">${pill("Ready / pinned", "good")}${pill("Pending review", "warn")}${pill("Blocked / not proven", "locked")}</div></div><div class="ic18-platform-grid">${platforms.map(platformCard).join("")}</div>`;
  }

  function securityView() {
    return `<div class="ic18-grid"><section class="ic18-panel"><div class="ic18-panel-head"><div><h2>Transport guardrails</h2><small>Controls applied before a sandbox request may leave the application boundary.</small></div>${pill("Fail closed", "good")}</div>${rows([
      { title: "HTTPS-only destinations", status: "verified", description: "Endpoint bindings reject non-HTTPS base URLs." },
      { title: "Public-address DNS verification", status: "verified", description: "Private, loopback, link-local, reserved and metadata targets are rejected." },
      { title: "Redirect following", status: "blocked", description: "3xx responses are not followed by the sandbox executor." },
      { title: "Path-segment composition", status: "verified", description: "Task-derived path values are percent-encoded as one route segment." },
      { title: "Response boundary", status: "verified", description: "JSON-only parsing with a 1 MiB response ceiling." },
    ], "")}</section><section class="ic18-panel"><div class="ic18-panel-head"><div><h2>Authority boundary</h2><small>Network reachability never implies runtime or production permission.</small></div></div><div class="ic18-readiness-list">${readinessStep("Endpoint discovered", "Pending", "A pinned specification must pass the discovery quality gate.")}${readinessStep("Binding schema", "Pending", "Task, scopes and canonical mapping must validate.")}${readinessStep("Sandbox execution", "Pending", "Customer/operator test endpoint and managed credentials required.")}${readinessStep("Production authority", "Blocked", "Separate approval path remains mandatory.")}</div></section></div>`;
  }

  function secretsOperationsView() {
    const items = [
      { title: "Infisical provider health", status: "local lab verified", description: "Provider details remain supervisor-only." },
      { title: "Machine identity isolation", status: "verified", description: "dev and ci remain environment scoped." },
      { title: "Secret value exposure", status: "blocked", description: "Only references and lifecycle state are visible here." },
      { title: "Restart persistence", status: "pending proof", description: "Operational gate remains open before real staging." },
      { title: "Encrypted backup and restore", status: "not started", description: "Required before final staging approval." },
    ];
    return `<div class="ic18-grid"><section class="ic18-panel"><div class="ic18-panel-head"><div><h2>Secrets provider boundary</h2><small>Operational state only. No token, password, client secret, or private key value is rendered.</small></div>${pill("Reference only", "good")}</div>${rows(items, "No secrets operations state is available.")}</section><section class="ic18-panel"><div class="ic18-panel-head"><div><h2>Promotion rule</h2><small>Secrets readiness supports qualification but never grants production authority.</small></div></div><div class="ic18-list"><div class="ic18-row"><div><strong>Local isolated lab</strong><span>Allowed</span></div>${pill("Allowed", "good")}</div><div class="ic18-row"><div><strong>Real staging</strong><span>Restart and restore proofs required</span></div>${pill("NO-GO", "locked")}</div><div class="ic18-row"><div><strong>Production</strong><span>Separate human decision required</span></div>${pill("NO-GO", "locked")}</div></div></section></div>`;
  }

  function tabBody() {
    const cases = normalizedCases();
    const progress = asArray(state.progress.actions || state.progress);
    if (state.active === "cases") return rows(cases, "No route-backed integration cases are available yet.");
    if (state.active === "platforms") return platformsView();
    if (state.active === "security") return securityView();
    if (state.active === "secrets") return secretsOperationsView();
    if (state.active === "evidence") return rows(progress, "No pilot evidence progress has been recorded.");

    return `<div class="ic18-grid"><section class="ic18-panel"><div class="ic18-panel-head"><div><h2>Qualification pipeline</h2><small>One workflow shared by organizations, standards and sandbox evidence</small></div>${pill("Default deny", "good")}</div><div class="ic18-rail">${phaseRail()}</div></section><section class="ic18-panel"><div class="ic18-panel-head"><div><h2>Immediate priorities</h2><small>Highest-value actions without duplicating existing services</small></div></div>${rows([
      { title: "Reconcile CAMARA browser rendering", status: "in progress", description: "Render approved governance, registered/default-deny runtime tasks, external mock evidence and blocked provider/runtime/production gates from server truth." },
      { title: "Review provider compatibility disposition", status: "pending governance", description: "Decide evidence-only versus reduced-capability adapter without waiving retrieveSessionsByDevice or the missing-session divergence." },
      { title: "Obtain operator-backed QoD proof", status: "blocked", description: "Requires a non-mock operator environment, managed credentials and controlled test subjects." },
    ], "")}</section></div>`;
  }

  function activateTab(root, key, focus) {
    if (!TABS.some(([candidate]) => candidate === key)) return;
    state.active = key;
    render();
    if (focus) {
      window.requestAnimationFrame(() => {
        const activeTab = root.querySelector(`[data-ic18-tab="${key}"]`);
        if (activeTab) activeTab.focus();
      });
    }
  }

  function bindInteractions(root) {
    root.querySelectorAll("[data-ic18-tab]").forEach((button) => {
      button.addEventListener("click", () => activateTab(root, button.dataset.ic18Tab, false));
      button.addEventListener("keydown", (event) => {
        const index = TABS.findIndex(([key]) => key === button.dataset.ic18Tab);
        let nextIndex = index;
        if (event.key === "ArrowRight") nextIndex = (index + 1) % TABS.length;
        else if (event.key === "ArrowLeft") nextIndex = (index - 1 + TABS.length) % TABS.length;
        else if (event.key === "Home") nextIndex = 0;
        else if (event.key === "End") nextIndex = TABS.length - 1;
        else return;
        event.preventDefault();
        activateTab(root, TABS[nextIndex][0], true);
      });
    });
    root.querySelectorAll("[data-admin-page]").forEach((button) => {
      button.addEventListener("click", () => {
        if (window.PMK_ADMIN_NAV) window.PMK_ADMIN_NAV.setActivePage(button.dataset.adminPage);
      });
    });
  }

  function render() {
    const root = document.getElementById("admin-integration-center-root");
    if (!root) return;
    if (state.loading) {
      root.innerHTML = '<div class="ic18-empty" role="status">Loading integration readiness, cases, CAMARA qualification and pilot evidence…</div>';
      return;
    }

    const summary = counts();
    const tabs = TABS.map(([key, label]) => `<button type="button" role="tab" id="ic18-tab-${key}" class="ic18-tab ${state.active === key ? "active" : ""}" data-ic18-tab="${key}" aria-controls="ic18-panel-${key}" aria-selected="${state.active === key ? "true" : "false"}" tabindex="${state.active === key ? "0" : "-1"}">${label}</button>`).join("");

    root.innerHTML = `<div class="ic18-shell"><section class="ic18-hero"><div><p class="ic18-eyebrow">Stage 18 · Supervisor workspace</p><h1>External Integration Center</h1><p>Unified control plane for institution intake, standards alignment, endpoint contracts, network and security readiness, sandbox qualification, evidence and supervisor decisions.</p><div class="ic18-actions"><button type="button" class="ic18-button" data-ic18-tab="cases">Review cases</button><button type="button" class="ic18-button ghost" data-admin-page="operator-pilot-handoff">Open pilot handoff</button></div></div><div class="ic18-verdict" aria-label="Environment authority"><div><span>Local qualification</span><strong>Allowed</strong></div><div><span>Real staging</span><strong>NO-GO</strong></div><div><span>Production</span><strong>NO-GO</strong></div>${pill("No raw secrets", "good")}</div></section><section class="ic18-metrics" aria-label="Integration readiness metrics">${metric("Integration cases", summary.cases, "Route-backed records")}${metric("Open cases", summary.open, "Need supervisor attention")}${metric("Inputs received", summary.received, "Ready for review")}${metric("Open blockers", summary.blockers, "No automatic approval")}${metric("Runtime authority", state.camaraQod && state.camaraQod.runtime_connector_approved === true ? "Approved" : "Disabled", "Connector authority")}</section><section class="ic18-panel"><div class="ic18-panel-head"><div><h2>Workspace</h2><small>Case-scoped views prevent platform and customer complexity from leaking across the program.</small></div></div><div class="ic18-tabs" role="tablist" aria-label="Integration center views">${tabs}</div><div class="ic18-tab-body" role="tabpanel" id="ic18-panel-${state.active}" aria-labelledby="ic18-tab-${state.active}">${tabBody()}</div></section>${state.error ? `<div class="ic18-empty" role="alert">Some route-backed data could not be loaded: ${escapeHtml(state.error)}</div>` : ""}</div>`;
    bindInteractions(root);
  }

  async function load() {
    state.loading = true;
    render();
    const results = await Promise.allSettled([getJson(API.tracking), getJson(API.cases), getJson(API.handoff), getJson(API.progress), getJson(API.camaraQod)]);
    state.tracking = results[0].status === "fulfilled" ? results[0].value : null;
    state.cases = results[1].status === "fulfilled" ? results[1].value : [];
    state.handoff = results[2].status === "fulfilled" ? results[2].value : null;
    state.progress = results[3].status === "fulfilled" ? results[3].value : [];
    state.camaraQod = results[4].status === "fulfilled" ? results[4].value : null;
    state.error = results.filter((result) => result.status === "rejected").map((result) => result.reason.message).join(", ");
    state.loading = false;
    render();
  }

  window.PMK_INTEGRATION_CENTER_18 = { load, render };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load);
  else load();
})();