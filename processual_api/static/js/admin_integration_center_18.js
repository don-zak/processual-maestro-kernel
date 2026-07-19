(function () {
  "use strict";

  const API = {
    tracking: "/settings/admin/integration-readiness-tracking",
    cases: "/settings/admin/integration-readiness-tracking/cases",
    handoff: "/settings/admin/operator-pilot-handoff",
    progress: "/settings/admin/operator-pilot-handoff/progress",
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
    const phases = [
      "Inputs",
      "Review",
      "Sandbox setup",
      "Sandbox validation",
      "Pilot acceptance",
      "Production review",
    ];
    return phases
      .map((phase, index) => {
        const stateClass = index === 0 ? "active" : index > 1 ? "locked" : "";
        return `
          <div class="ic18-step ${stateClass}">
            <span>0${index + 1}</span>
            <strong>${escapeHtml(phase)}</strong>
          </div>`;
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
    const received = progress.filter((item) =>
      ["received_for_review", "completed"].includes(item.status)
    ).length;

    return {
      cases: cases.length,
      open: openCases,
      received,
      blockers: Math.max(0, progress.length - received),
    };
  }

  function statusTone(status) {
    const value = String(status || "").toLowerCase();
    if (/complete|ready|approved|verified|healthy|allowed/.test(value)) return "good";
    if (/reject|block|fail|expired|no-go/.test(value)) return "locked";
    return "warn";
  }

  function rows(items, emptyMessage) {
    if (!items.length) return `<div class="ic18-empty">${escapeHtml(emptyMessage)}</div>`;

    return `
      <div class="ic18-list">
        ${items
          .map((item) => {
            const title =
              item.title || item.display_name || item.case_id || item.action_id || "Integration item";
            const status = item.status || item.sector || item.description || "Awaiting review";
            return `
              <div class="ic18-row">
                <div>
                  <strong>${escapeHtml(title)}</strong>
                  <span>${escapeHtml(status)}</span>
                </div>
                ${pill(String(status).replace(/_/g, " "), statusTone(status))}
              </div>`;
          })
          .join("")}
      </div>`;
  }

  function secretsOperationsView() {
    const items = [
      {
        title: "Infisical provider health",
        status: "local lab verified",
        description: "Provider details remain supervisor-only.",
      },
      {
        title: "Machine identity isolation",
        status: "verified",
        description: "dev and ci remain environment scoped.",
      },
      {
        title: "Secret value exposure",
        status: "blocked",
        description: "Only references and lifecycle state are visible here.",
      },
      {
        title: "Restart persistence",
        status: "pending proof",
        description: "Operational gate remains open before real staging.",
      },
      {
        title: "Encrypted backup and restore",
        status: "not started",
        description: "Required before final staging approval.",
      },
    ];

    return `
      <div class="ic18-grid">
        <section class="ic18-panel">
          <div class="ic18-panel-head">
            <div>
              <h2>Secrets provider boundary</h2>
              <small>Operational state only. No token, password, client secret, or private key value is rendered.</small>
            </div>
            ${pill("Reference only", "good")}
          </div>
          ${rows(items, "No secrets operations state is available.")}
        </section>
        <section class="ic18-panel">
          <div class="ic18-panel-head">
            <div>
              <h2>Promotion rule</h2>
              <small>Secrets readiness supports qualification but never grants production authority.</small>
            </div>
          </div>
          <div class="ic18-list">
            <div class="ic18-row"><div><strong>Local isolated lab</strong><span>Allowed</span></div>${pill("Allowed", "good")}</div>
            <div class="ic18-row"><div><strong>Real staging</strong><span>Restart and restore proofs required</span></div>${pill("NO-GO", "locked")}</div>
            <div class="ic18-row"><div><strong>Production</strong><span>Separate human decision required</span></div>${pill("NO-GO", "locked")}</div>
          </div>
        </section>
      </div>`;
  }

  function tabBody() {
    const cases = normalizedCases();
    const progress = asArray(state.progress.actions || state.progress);

    if (state.active === "cases") {
      return rows(cases, "No route-backed integration cases are available yet.");
    }

    if (state.active === "platforms") {
      return rows(
        [
          {
            title: "CAMARA / GSMA Open Gateway",
            status: "catalogue planned",
            description: "Capability and conformance profile per integration case.",
          },
          {
            title: "TM Forum Open APIs",
            status: "catalogue planned",
            description: "API version, CTK and mapping evidence per case.",
          },
          {
            title: "Operator-specific profiles",
            status: "case scoped",
            description: "No global operator assumptions.",
          },
        ],
        ""
      );
    }

    if (state.active === "security") {
      return rows(
        [
          { title: "DNS and TLS readiness", status: "reference only" },
          { title: "OAuth / OIDC and consent", status: "supervisor review" },
          { title: "Credential binding", status: "vault reference only" },
        ],
        ""
      );
    }

    if (state.active === "secrets") return secretsOperationsView();
    if (state.active === "evidence") {
      return rows(progress, "No pilot evidence progress has been recorded.");
    }

    return `
      <div class="ic18-grid">
        <section class="ic18-panel">
          <div class="ic18-panel-head">
            <div>
              <h2>Qualification pipeline</h2>
              <small>One workflow shared by organizations, standards and sandbox evidence</small>
            </div>
            ${pill("Default deny", "good")}
          </div>
          <div class="ic18-rail">${phaseRail()}</div>
        </section>
        <section class="ic18-panel">
          <div class="ic18-panel-head">
            <div>
              <h2>Immediate priorities</h2>
              <small>Highest-value actions without duplicating existing services</small>
            </div>
          </div>
          ${rows(
            [
              { title: "Consolidate existing readiness cases", status: "in progress" },
              { title: "Attach CAMARA/TM Forum profiles per case", status: "next" },
              { title: "Expose safe institution projection", status: "next" },
            ],
            ""
          )}
        </section>
      </div>`;
  }

  function bindInteractions(root) {
    root.querySelectorAll("[data-ic18-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        state.active = button.dataset.ic18Tab;
        render();
      });
    });

    root.querySelectorAll("[data-admin-page]").forEach((button) => {
      button.addEventListener("click", () => {
        if (window.PMK_ADMIN_NAV) {
          window.PMK_ADMIN_NAV.setActivePage(button.dataset.adminPage);
        }
      });
    });
  }

  function render() {
    const root = document.getElementById("admin-integration-center-root");
    if (!root) return;

    if (state.loading) {
      root.innerHTML = '<div class="ic18-empty">Loading integration readiness, cases and pilot evidence…</div>';
      return;
    }

    const summary = counts();
    const tabs = TABS.map(
      ([key, label]) =>
        `<button class="ic18-tab ${state.active === key ? "active" : ""}" data-ic18-tab="${key}">${label}</button>`
    ).join("");

    root.innerHTML = `
      <div class="ic18-shell">
        <section class="ic18-hero">
          <div>
            <p class="ic18-eyebrow">Stage 18 · Supervisor workspace</p>
            <h1>External Integration Center</h1>
            <p>Unified control plane for institution intake, CAMARA and TM Forum alignment, API contracts, network and security readiness, sandbox qualification, evidence and supervisor decisions.</p>
            <div class="ic18-actions">
              <button class="ic18-button" data-ic18-tab="cases">Review cases</button>
              <button class="ic18-button ghost" data-admin-page="operator-pilot-handoff">Open pilot handoff</button>
            </div>
          </div>
          <div class="ic18-verdict">
            <div><span>Local qualification</span><strong>Allowed</strong></div>
            <div><span>Real staging</span><strong>NO-GO</strong></div>
            <div><span>Production</span><strong>NO-GO</strong></div>
            ${pill("No raw secrets", "good")}
          </div>
        </section>

        <section class="ic18-metrics">
          ${metric("Integration cases", summary.cases, "Route-backed records")}
          ${metric("Open cases", summary.open, "Need supervisor attention")}
          ${metric("Inputs received", summary.received, "Ready for review")}
          ${metric("Open blockers", summary.blockers, "No automatic approval")}
          ${metric("Runtime authority", "Disabled", "Explicit guardrail")}
        </section>

        <section class="ic18-panel">
          <div class="ic18-panel-head">
            <div>
              <h2>Workspace</h2>
              <small>Case-scoped views prevent platform and customer complexity from leaking across the program.</small>
            </div>
          </div>
          <div class="ic18-tabs">${tabs}</div>
          <div style="margin-top:1rem">${tabBody()}</div>
        </section>

        ${
          state.error
            ? `<div class="ic18-empty">Some route-backed data could not be loaded: ${escapeHtml(state.error)}</div>`
            : ""
        }
      </div>`;

    bindInteractions(root);
  }

  async function load() {
    state.loading = true;
    render();

    const results = await Promise.allSettled([
      getJson(API.tracking),
      getJson(API.cases),
      getJson(API.handoff),
      getJson(API.progress),
    ]);

    state.tracking = results[0].status === "fulfilled" ? results[0].value : null;
    state.cases = results[1].status === "fulfilled" ? results[1].value : [];
    state.handoff = results[2].status === "fulfilled" ? results[2].value : null;
    state.progress = results[3].status === "fulfilled" ? results[3].value : [];
    state.error = results
      .filter((result) => result.status === "rejected")
      .map((result) => result.reason.message)
      .join(", ");
    state.loading = false;
    render();
  }

  window.PMK_INTEGRATION_CENTER_18 = { load, render };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
