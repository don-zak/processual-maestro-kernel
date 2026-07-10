(function () {
  "use strict";

  const PACKAGE = {
    package_id: "operator-pilot-handoff-14a",
    package_status: "draft_review",
    handoff_status: "pending_operator_inputs",
    pilot_ready: false,
    production_allowed: false,
    runtime_connector_approved: false,
    customer_credentials_present: false,
    external_http_allowed: false,
    required_inputs: [
      "API documentation",
      "Sandbox base URL",
      "Authentication method",
      "Allowed scopes matrix",
      "Restricted scopes matrix",
      "Rate limits and throttling policy",
      "Test account or sandbox tenant",
      "Sample request and response payloads",
      "Error code catalog",
      "Data retention and masking constraints",
      "Security review contact",
      "Incident escalation contact",
      "Production approval path"
    ],
    specializations: [
      {
        key: "telecom_operator",
        label: "Telecom operators",
        domains: [
          "CRM",
          "Billing",
          "Ticketing",
          "Order Management",
          "Network Assurance",
          "Document / KYC",
          "Enterprise Helpdesk"
        ]
      },
      {
        key: "banking_fintech",
        label: "Banks and fintech",
        domains: [
          "KYC",
          "Account support",
          "Payments support",
          "Case management",
          "Risk review",
          "Document review"
        ]
      },
      {
        key: "government_public_services",
        label: "Government and public services",
        domains: [
          "Citizen case",
          "Service request",
          "Permits",
          "Document verification",
          "Appointment support"
        ]
      },
      {
        key: "university_research",
        label: "Universities and research",
        domains: [
          "Student services",
          "Admissions",
          "Learning support",
          "Research dataset",
          "Digital library"
        ]
      },
      {
        key: "healthcare_admin",
        label: "Healthcare administration",
        domains: [
          "Patient administration",
          "Appointments",
          "Claims administration",
          "Document intake",
          "Non-clinical support"
        ]
      },
      {
        key: "insurance",
        label: "Insurance providers",
        domains: [
          "Policy administration",
          "Claims intake",
          "Broker support",
          "Document review",
          "Customer case"
        ]
      },
      {
        key: "utilities_energy",
        label: "Utilities and energy",
        domains: [
          "Customer service",
          "Metering case",
          "Billing support",
          "Field operations case",
          "Outage support"
        ]
      },
      {
        key: "logistics_transport",
        label: "Logistics and transport",
        domains: [
          "Shipment tracking",
          "Ticketing",
          "Fleet support",
          "Customs documents",
          "Customer case"
        ]
      },
      {
        key: "enterprise_helpdesk",
        label: "Enterprise helpdesk",
        domains: [
          "CRM",
          "Ticketing",
          "Asset support",
          "IT service management",
          "Knowledge base"
        ]
      },
      {
        key: "legal_compliance",
        label: "Legal and compliance",
        domains: [
          "Case intake",
          "Document review",
          "Policy exception",
          "Audit evidence",
          "Compliance tracking"
        ]
      }
    ],
    success_criteria: [
      "Sandbox API documentation reviewed",
      "Allowed read scopes mapped",
      "Restricted write scopes documented",
      "Sample sandbox flow described",
      "Rate limits captured",
      "Audit expectations documented",
      "Rollback and stop criteria defined",
      "Supervisor sign-off required before production"
    ],
    next_actions: [
      "Select the external organization type",
      "Map requested domains to adapter contracts",
      "Request sandbox documentation and test tenant",
      "Review allowed and restricted scopes",
      "Export the Markdown handoff package",
      "Block production until a separate approval phase"
    ]
  };
  const OPERATOR_PILOT_HANDOFF_API_14C = "/settings/admin/operator-pilot-handoff";
  const OPERATOR_PILOT_HANDOFF_EXPORT_API_14C =
    "/settings/admin/operator-pilot-handoff/export";

  let activePackage14C = PACKAGE;
  let backendLoadState14C = "static_fallback";

  function packageForRender14C() {
    return activePackage14C || PACKAGE;
  }

  function normalizeBackendPackage14C(payload) {
    if (!payload || typeof payload !== "object") return null;

    const guardrails = payload.guardrails || {};
    if (
      guardrails.production_allowed !== false ||
      guardrails.runtime_connector_approved !== false ||
      guardrails.customer_credentials_present !== false ||
      guardrails.external_http_allowed !== false
    ) {
      return null;
    }

    return Object.assign({}, PACKAGE, payload, {
      guardrails: Object.assign({}, PACKAGE.guardrails || {}, guardrails)
    });
  }

  async function loadBackendPackage14C() {
    try {
      const response = await fetch(OPERATOR_PILOT_HANDOFF_API_14C, {
        credentials: "same-origin",
        headers: {
          Accept: "application/json"
        }
      });

      if (!response.ok) {
        backendLoadState14C = "backend_http_" + response.status;
        return packageForRender14C();
      }

      const payload = await response.json();
      const normalized = normalizeBackendPackage14C(payload);

      if (!normalized) {
        backendLoadState14C = "backend_rejected_guardrails";
        return packageForRender14C();
      }

      activePackage14C = normalized;
      backendLoadState14C = "backend_loaded";
      return activePackage14C;
    } catch (error) {
      backendLoadState14C = "backend_error";
      return packageForRender14C();
    }
  }


  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function findRoot() {
    return document.getElementById("operator-pilot-handoff-root");
  }

  function listItems(values, className) {
    return values
      .map((value) => `<li class="${className}">${escapeHtml(value)}</li>`)
      .join("");
  }

  function renderSpecializations() {
    return PACKAGE.specializations
      .map((item) => {
        const domains = item.domains
          .map(
            (domain) =>
              `<span class="operator-pilot-domain">${escapeHtml(domain)}</span>`
          )
          .join("");

        return `
          <article class="operator-pilot-specialization" data-entity-type="${escapeHtml(
            item.key
          )}">
            <h4>${escapeHtml(item.label)}</h4>
            <div class="operator-pilot-domains">${domains}</div>
          </article>
        `;
      })
      .join("");
  }

  function buildMarkdown() {

    const PACKAGE = packageForRender14C();
const lines = [
      "# Operator Pilot Handoff",
      "",
      `- Package: \`${PACKAGE.package_id}\``,
      `- Status: \`${PACKAGE.handoff_status}\``,
      `- Pilot ready: \`${PACKAGE.pilot_ready}\``,
      `- Production allowed: \`${PACKAGE.production_allowed}\``,
      `- Runtime connector approved: \`${PACKAGE.runtime_connector_approved}\``,
      "",
      "## Required Operator Inputs",
      ""
    ];

    PACKAGE.required_inputs.forEach((item) => {
      lines.push(`- ${item}`);
    });

    lines.push("", "## Supported Organization Types", "");

    PACKAGE.specializations.forEach((item) => {
      lines.push(`- ${item.label}: ${item.domains.join(", ")}`);
    });

    lines.push("", "## Pilot Success Criteria", "");

    PACKAGE.success_criteria.forEach((item) => {
      lines.push(`- ${item}`);
    });

    lines.push("", "## Supervisor Next Actions", "");

    PACKAGE.next_actions.forEach((item) => {
      lines.push(`- ${item}`);
    });

    lines.push(
      "",
      "## Guardrails",
      "",
      "- Sandbox only.",
      "- No production endpoint is approved.",
      "- No customer credentials are accepted.",
      "- No runtime connector is approved.",
      "- No external HTTP call is executed.",
      "- Production requires a separate supervisor-approved phase."
    );

    return `${lines.join("\n")}\n`;
  }

  function setStatus(message, isError) {
    const status = document.getElementById("operator-pilot-handoff-status");
    if (!status) return;
    status.textContent = message;
    status.dataset.state = isError ? "error" : "ready";
  }

  async function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }

    const area = document.createElement("textarea");
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    return true;
  }

  function exportMarkdown() {
    const blob = new Blob([buildMarkdown()], {
      type: "text/markdown;charset=utf-8"
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "operator-pilot-handoff-14a.md";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setStatus("Markdown handoff exported.", false);
  }

  function bindTools() {
    const rebuild = document.getElementById("operator-pilot-rebuild");
    const copyChecklist = document.getElementById("operator-pilot-copy-checklist");
    const copyMarkdown = document.getElementById("operator-pilot-copy-markdown");
    const exportButton = document.getElementById("operator-pilot-export");

    if (rebuild) {
      rebuild.addEventListener("click", () => {
        render();
        setStatus("Safe handoff package rebuilt.", false);
      });
    }

    if (copyChecklist) {
      copyChecklist.addEventListener("click", async () => {
        await copyText(PACKAGE.required_inputs.map((item) => `- ${item}`).join("\n"));
        setStatus("Operator input checklist copied.", false);
      });
    }

    if (copyMarkdown) {
      copyMarkdown.addEventListener("click", async () => {
        await copyText(buildMarkdown());
        setStatus("Markdown handoff copied.", false);
      });
    }

    if (exportButton) {
      exportButton.addEventListener("click", exportMarkdown);
    }
  }

  function render() {
    const PACKAGE = packageForRender14C();
    const guardrails = PACKAGE.guardrails || PACKAGE;
    const root = findRoot();
    if (!root) return;

    root.dataset.backendLoadState = backendLoadState14C;
    root.dataset.phase = PACKAGE.package_id;
    root.dataset.handoffStatus = PACKAGE.handoff_status;
    root.dataset.pilotReady = String(PACKAGE.pilot_ready);
    root.dataset.productionAllowed = String(guardrails.production_allowed);
    root.dataset.runtimeConnectorApproved = String(
      guardrails.runtime_connector_approved
    );

    root.innerHTML = `
      <section class="operator-pilot-shell">
        <header class="operator-pilot-header">
          <p class="eyebrow">Integration onboarding</p>
          <h2>Operator pilot handoff</h2>
          <p>
            Prepare a sandbox-only handoff package for external organizations
            without approving runtime connectors, production writes, credentials,
            or external HTTP calls.
          </p>
        </header>

        <div class="operator-pilot-status-grid">
          <article>
            <span>Status</span>
            <strong data-operator-pilot-status>${escapeHtml(
              PACKAGE.handoff_status
            )}</strong>
          </article>
          <article>
            <span>Pilot ready</span>
            <strong data-operator-pilot-ready>${escapeHtml(
              PACKAGE.pilot_ready
            )}</strong>
          </article>
          <article>
            <span>Production allowed</span>
            <strong data-operator-production-allowed>${escapeHtml(
              PACKAGE.production_allowed
            )}</strong>
          </article>
          <article>
            <span>Runtime connector approved</span>
            <strong data-operator-runtime-approved>${escapeHtml(
              PACKAGE.runtime_connector_approved
            )}</strong>
          </article>
        </div>

        <div class="operator-pilot-tools" aria-label="Operator handoff tools">
          <button type="button" id="operator-pilot-rebuild">
            Rebuild safe package
          </button>
          <button type="button" id="operator-pilot-copy-checklist">
            Copy input checklist
          </button>
          <button type="button" id="operator-pilot-copy-markdown">
            Copy Markdown
          </button>
          <button type="button" id="operator-pilot-export">
            Export Markdown
          </button>
        </div>

        <p id="operator-pilot-handoff-status" class="operator-pilot-status">
          Safe package ready for supervisor review.
        </p>

        <section class="operator-pilot-card">
          <h3>Required organization inputs</h3>
          <ul class="operator-pilot-checklist">
            ${listItems(PACKAGE.required_inputs, "operator-pilot-input")}
          </ul>
        </section>

        <section class="operator-pilot-card">
          <h3>Supported organization types and domains</h3>
          <div class="operator-pilot-specializations">
            ${renderSpecializations()}
          </div>
        </section>

        <section class="operator-pilot-card">
          <h3>Pilot success criteria</h3>
          <ul>${listItems(PACKAGE.success_criteria, "operator-pilot-criterion")}</ul>
        </section>

        <section class="operator-pilot-card">
          <h3>Supervisor next actions</h3>
          <ul>${listItems(PACKAGE.next_actions, "operator-pilot-action")}</ul>
        </section>

        <section class="operator-pilot-card operator-pilot-guardrails">
          <h3>Guardrails</h3>
          <ul>
            <li>Sandbox only.</li>
            <li>No production endpoint is approved.</li>
            <li>No customer credentials are accepted.</li>
            <li>No runtime connector is approved.</li>
            <li>No external HTTP call is executed.</li>
            <li>Production requires a separate supervisor-approved phase.</li>
          </ul>
        </section>
      </section>
    `;

    bindTools();
  }

  function ensureExplanationPanel() {
    const root = findRoot();
    if (!root) return;

    const shell = root.querySelector(".operator-pilot-shell");
    if (!shell || shell.querySelector(".operator-pilot-explainer")) return;

    const panel = document.createElement("section");
    panel.className = "operator-pilot-panel operator-pilot-explainer";
    panel.setAttribute("aria-label", "Operator pilot handoff explanation");
    panel.innerHTML = [
      '<div class="operator-pilot-title">What this handoff page does</div>',
      '<div class="operator-pilot-explainer-grid">',
      '<div class="operator-pilot-explainer-card">',
      '<strong>Supervisor purpose</strong>',
      '<p>Prepare a sandbox-only package that tells an external organization what inputs are needed before a pilot can be reviewed.</p>',
      '</div>',
      '<div class="operator-pilot-explainer-card">',
      '<strong>What remains blocked</strong>',
      '<p>Production access, runtime connectors, customer credentials, production writes, and external HTTP calls remain explicitly blocked.</p>',
      '</div>',
      '<div class="operator-pilot-explainer-card">',
      '<strong>Next operator action</strong>',
      '<p>Provide API documentation, sandbox URL, authentication method, scopes, sample payloads, rate limits, and security contacts.</p>',
      '</div>',
      '</div>'
    ].join("");

    const header = shell.querySelector(".operator-pilot-header");
    if (header && header.nextSibling) {
      shell.insertBefore(panel, header.nextSibling);
      return;
    }

    shell.prepend(panel);
  }

  function downloadBackendMarkdown14C() {
    window.open(OPERATOR_PILOT_HANDOFF_EXPORT_API_14C, "_blank", "noopener");
  }
  async function init() {

    await loadBackendPackage14C();
render();
    ensureExplanationPanel();

    const exportButton = document.getElementById("operator-pilot-export");
    if (exportButton) {
      exportButton.addEventListener("click", downloadBackendMarkdown14C);
    }
  }
  window.PMK_OPERATOR_PILOT_HANDOFF_14A = {
    buildMarkdown,
    package: PACKAGE,
    render
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

// PMK OPERATOR PILOT HANDOFF ACTIONS UI 14D START
(() => {
  "use strict";

  const OPERATOR_PILOT_HANDOFF_ACTIONS_API_14D =
    "/settings/admin/operator-pilot-handoff/actions-preview";

  let actionsLoadState14D = "actions_loading";
  let actionsPackage14D = null;

  function root14D() {
    return document.getElementById("operator-pilot-handoff-root");
  }

  function escapeHtml14D(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function normalizeActionsPackage14D(payload) {
    if (!payload || typeof payload !== "object") return null;
    if (payload.read_only !== true || payload.preview_only !== true) return null;

    const guardrails = payload.guardrails || {};
    if (
      guardrails.production_allowed !== false ||
      guardrails.runtime_connector_approved !== false ||
      guardrails.customer_credentials_present !== false ||
      guardrails.external_http_allowed !== false ||
      guardrails.persistent_write_allowed !== false ||
      guardrails.automatic_activation_allowed !== false
    ) {
      return null;
    }

    if (!Array.isArray(payload.actions)) return null;
    if (payload.actions.length < 10) return null;
    if (payload.actions.length !== payload.action_count) return null;

    const actionsAreSafe = payload.actions.every(
      (action) =>
        action &&
        typeof action === "object" &&
        action.execution_mode === "copy_only" &&
        action.requires_credentials === false &&
        action.requires_production === false &&
        action.runtime_connector_approved === false &&
        action.external_http_allowed === false &&
        action.persistent_write_allowed === false
    );

    return actionsAreSafe ? payload : null;
  }

  async function loadActionsPackage14D() {
    try {
      const response = await fetch(OPERATOR_PILOT_HANDOFF_ACTIONS_API_14D, {
        credentials: "same-origin",
        headers: { Accept: "application/json" }
      });

      if (!response.ok) {
        actionsLoadState14D = "actions_http_" + response.status;
        return null;
      }

      const normalized = normalizeActionsPackage14D(await response.json());
      if (!normalized) {
        actionsLoadState14D = "actions_rejected_guardrails";
        return null;
      }

      actionsPackage14D = normalized;
      actionsLoadState14D = "actions_loaded";
      return normalized;
    } catch (error) {
      actionsLoadState14D = "actions_error";
      return null;
    }
  }

  async function copyText14D(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }

  function requestNote14D(action) {
    return [
      `Action: ${action.label}`,
      `Requested from: ${action.required_from}`,
      `Purpose: ${action.description}`,
      `Supervisor note: ${action.supervisor_note}`,
      "Execution mode: copy-only",
      "Production access: blocked",
      "Runtime connector approval: blocked",
      "Credentials: not requested or stored",
      "External HTTP execution: blocked"
    ].join("\n");
  }

  function renderActionCards14D(actions) {
    return actions
      .map(
        (action) => `
          <article
            class="operator-pilot-action-card"
            data-action-id="${escapeHtml14D(action.action_id)}"
          >
            <span class="operator-pilot-action-status">
              ${escapeHtml14D(action.status)}
            </span>
            <h4>${escapeHtml14D(action.label)}</h4>
            <p>${escapeHtml14D(action.description)}</p>
            <dl class="operator-pilot-action-meta">
              <div>
                <dt>Requested from</dt>
                <dd>${escapeHtml14D(action.required_from)}</dd>
              </div>
              <div>
                <dt>Execution</dt>
                <dd>${escapeHtml14D(action.execution_mode)}</dd>
              </div>
            </dl>
            <button
              type="button"
              class="operator-pilot-action-copy"
              data-operator-pilot-copy-action="${escapeHtml14D(action.action_id)}"
            >
              Copy request note
            </button>
          </article>
        `
      )
      .join("");
  }

  function setDatasets14D(root, payload) {
    root.dataset.actionsLoadState = actionsLoadState14D;
    root.dataset.actionsCount = String(payload ? payload.action_count : 0);
    root.dataset.actionsReadOnly = String(Boolean(payload && payload.read_only));
    root.dataset.actionsPreviewOnly = String(
      Boolean(payload && payload.preview_only)
    );
  }

  function bindCopyButtons14D(panel, payload) {
    panel
      .querySelectorAll("[data-operator-pilot-copy-action]")
      .forEach((button) => {
        button.addEventListener("click", async () => {
          const action = payload.actions.find(
            (item) =>
              item.action_id === button.dataset.operatorPilotCopyAction
          );
          if (!action) return;

          await copyText14D(requestNote14D(action));
          button.textContent = "Request note copied";
          window.setTimeout(() => {
            button.textContent = "Copy request note";
          }, 1600);
        });
      });
  }

  function renderActions14D(payload) {
    const root = root14D();
    if (!root) return false;

    const shell = root.querySelector(".operator-pilot-shell");
    if (!shell) return false;

    const previous = shell.querySelector("#operator-pilot-actions-14d");
    if (previous) previous.remove();

    const panel = document.createElement("section");
    panel.id = "operator-pilot-actions-14d";
    panel.className = "operator-pilot-panel operator-pilot-actions-14d";
    panel.setAttribute("aria-label", "Supervisor readiness actions");

    setDatasets14D(root, payload);

    if (!payload) {
      panel.innerHTML = `
        <div class="operator-pilot-actions-header">
          <div>
            <div class="operator-pilot-title">Supervisor readiness actions</div>
            <p>Read-only action preview is unavailable. No action was executed.</p>
          </div>
          <span class="operator-pilot-actions-state">
            ${escapeHtml14D(actionsLoadState14D)}
          </span>
        </div>
      `;
    } else {
      panel.innerHTML = `
        <div class="operator-pilot-actions-header">
          <div>
            <div class="operator-pilot-title">Supervisor readiness actions</div>
            <p>
              Prepare copy-only requests for operator inputs. This preview does
              not save progress, send messages, activate connectors, or grant
              production access.
            </p>
          </div>
          <span class="operator-pilot-actions-state">
            ${escapeHtml14D(actionsLoadState14D)}
          </span>
        </div>
        <div class="operator-pilot-actions-summary">
          <span><strong>${escapeHtml14D(payload.action_count)}</strong> pending actions</span>
          <span>Read-only preview</span>
          <span>Copy-only controls</span>
        </div>
        <div class="operator-pilot-actions-grid">
          ${renderActionCards14D(payload.actions)}
        </div>
      `;
      bindCopyButtons14D(panel, payload);
    }

    const explainer = shell.querySelector(".operator-pilot-explainer");
    if (explainer) {
      explainer.insertAdjacentElement("afterend", panel);
    } else {
      shell.appendChild(panel);
    }

    return true;
  }

  async function waitForShell14D() {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const root = root14D();
      if (root && root.querySelector(".operator-pilot-shell")) return true;
      await new Promise((resolve) => window.setTimeout(resolve, 25));
    }
    return false;
  }

  function bindRebuildRecovery14D() {
    const rebuild = document.getElementById("operator-pilot-rebuild");
    if (!rebuild || rebuild.dataset.actionsRecovery14d === "1") return;

    rebuild.dataset.actionsRecovery14d = "1";
    rebuild.addEventListener("click", () => {
      window.setTimeout(() => {
        renderActions14D(actionsPackage14D);
        bindRebuildRecovery14D();
      }, 0);
    });
  }

  async function initActions14D() {
    const results = await Promise.all([
      loadActionsPackage14D(),
      waitForShell14D()
    ]);
    renderActions14D(results[0]);
    bindRebuildRecovery14D();
  }

  window.PMK_OPERATOR_PILOT_HANDOFF_ACTIONS_14D = {
    api: OPERATOR_PILOT_HANDOFF_ACTIONS_API_14D,
    load: loadActionsPackage14D,
    normalize: normalizeActionsPackage14D,
    render: renderActions14D
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initActions14D);
  } else {
    initActions14D();
  }
})();
// PMK OPERATOR PILOT HANDOFF ACTIONS UI 14D END
