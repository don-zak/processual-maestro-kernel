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
    const root = findRoot();
    if (!root) return;

    root.dataset.phase = PACKAGE.package_id;
    root.dataset.handoffStatus = PACKAGE.handoff_status;
    root.dataset.pilotReady = String(PACKAGE.pilot_ready);
    root.dataset.productionAllowed = String(PACKAGE.production_allowed);
    root.dataset.runtimeConnectorApproved = String(
      PACKAGE.runtime_connector_approved
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
  function init() {
    render();
    ensureExplanationPanel();
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
