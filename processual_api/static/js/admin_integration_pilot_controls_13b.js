// PMK INTEGRATION PILOT CONTROLS 13B START
// adminpilot13b-session-storage-r1
// lineage: adminpilot13b-isolated-recovery
(() => {
  const VERSION = "adminpilot13b-session-storage-r1";
  const LIST_ENDPOINT = "/settings/admin/integration-tasks";

  const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

  function supervisorSession() {
    const storageKeys = [
      "pmk_supervisor_session_key",
      "pmk_sup_session_key",
      "pmk_admin_supervisor_session",
    ];

    const read = (storage, key) => {
      try {
        const value = storage?.getItem?.(key);
        const text = String(value || "").trim();
        return text.startsWith("pmk_sup_") ? text : "";
      } catch (_error) {
        return "";
      }
    };

    for (const key of storageKeys) {
      const fromSession = read(window.sessionStorage, key);
      if (fromSession) return fromSession;

      const fromLocal = read(window.localStorage, key);
      if (fromLocal) return fromLocal;
    }

    return "";
  }

  function headers() {
    const out = { Accept: "application/json", "Content-Type": "application/json" };
    const auth =
      typeof window.PMK_ADMIN_AUTH?.headers === "function"
        ? window.PMK_ADMIN_AUTH.headers()
        : window.PMK_ADMIN_AUTH?.headers;

    if (auth instanceof Headers) {
      auth.forEach((value, key) => {
        out[key] = value;
      });
    } else if (auth && typeof auth === "object") {
      Object.assign(out, auth);
    }

    const session = supervisorSession();
    if (session) out["X-Admin-Supervisor-Session"] = session;
    return out;
  }


  function format13BErrorPayload(payload) {
    if (!payload) {
      return "Unknown integration pilot error.";
    }

    if (typeof payload === "string") {
      return payload;
    }

    const detail = payload.detail || payload.error || payload.message || payload;

    if (typeof detail === "string") {
      return detail;
    }

    if (detail && typeof detail === "object") {
      const parts = [];

      if (detail.error) {
        parts.push(String(detail.error));
      }

      if (detail.message) {
        parts.push(String(detail.message));
      }

      if (detail.required_any_scope) {
        const scopes = Array.isArray(detail.required_any_scope)
          ? detail.required_any_scope.join(", ")
          : String(detail.required_any_scope);
        parts.push(`required_any_scope: ${scopes}`);
      }

      if (Object.prototype.hasOwnProperty.call(detail, "supervisor_session_present")) {
        parts.push(`supervisor_session_present: ${detail.supervisor_session_present}`);
      }

      if (detail.provided_scopes) {
        const provided = Array.isArray(detail.provided_scopes)
          ? detail.provided_scopes.join(", ")
          : String(detail.provided_scopes);
        parts.push(`provided_scopes: ${provided || "none"}`);
      }

      if (parts.length) {
        return parts.join(" | ");
      }

      try {
        return JSON.stringify(detail);
      } catch {
        return "Integration pilot request failed with an object response.";
      }
    }

    try {
      return JSON.stringify(payload);
    } catch {
      return String(payload);
    }
  }

  async function parse13BResponseError(response) {
    const text = await response.text();

    if (!text) {
      return `${response.status} ${response.statusText}`.trim();
    }

    try {
      const payload = JSON.parse(text);
      return format13BErrorPayload(payload);
    } catch {
      return text;
    }
  }


  function stringify13BError(error) {
    if (!error) {
      return "Unknown integration pilot error.";
    }

    if (typeof error === "string") {
      return error;
    }

    if (error instanceof Error && error.message && error.message !== "[object Object]") {
      return error.message;
    }

    const payload = error.detail || error.error || error.message || error;

    if (typeof payload === "string") {
      return payload;
    }

    if (payload && typeof payload === "object") {
      const parts = [];

      if (payload.error) {
        parts.push(String(payload.error));
      }

      if (payload.message) {
        parts.push(String(payload.message));
      }

      if (payload.required_any_scope) {
        const scopes = Array.isArray(payload.required_any_scope)
          ? payload.required_any_scope.join(", ")
          : String(payload.required_any_scope);
        parts.push(`required_any_scope: ${scopes}`);
      }

      if (Object.prototype.hasOwnProperty.call(payload, "supervisor_session_present")) {
        parts.push(`supervisor_session_present: ${payload.supervisor_session_present}`);
      }

      if (payload.provided_scopes) {
        const provided = Array.isArray(payload.provided_scopes)
          ? payload.provided_scopes.join(", ")
          : String(payload.provided_scopes);
        parts.push(`provided_scopes: ${provided || "none"}`);
      }

      if (parts.length) {
        return parts.join(" | ");
      }

      try {
        return JSON.stringify(payload);
      } catch {
        return "Integration pilot request failed with an object response.";
      }
    }

    return String(payload);
  }

  async function parse13BErrorResponse(response) {
    const body = await response.text().catch(() => "");
    if (!body) {
      return `${response.status} ${response.statusText}`.trim();
    }

    try {
      return stringify13BError(JSON.parse(body));
    } catch {
      return body;
    }
  }

  async function requestJson(path, options = {}) {
    const response = await window.fetch(path, {
      credentials: "include",
      ...options,
      headers: headers(options.headers || {}),
    });

    if (!response.ok) {
      const message = await parse13BErrorResponse(response);
      throw new Error(message || response.statusText || "Integration pilot request failed.");
    }

    if (response.status === 204) {
      return {};
    }

    return response.json();
  }

  function ensureStyles() {
    if (document.querySelector("#pmk-13b-isolated-panels-style")) return;

    const style = document.createElement("style");
    style.id = "pmk-13b-isolated-panels-style";
    style.textContent = `
      .pmk-13b-shell {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
        gap: 14px;
        width: 100%;
        max-width: 100%;
        margin: 16px 0;
      }
      .pmk-13b-panel, .pmk-13b-panel * { box-sizing: border-box; }
      .pmk-13b-panel {
        max-width: 100%;
        overflow: hidden;
        padding: 16px;
        border: 1px solid rgba(148, 163, 184, 0.28);
        border-radius: 16px;
        background: rgba(15, 23, 42, 0.045);
      }
      .pmk-13b-panel h3 {
        margin: 0 0 8px;
        font-size: 1.05rem;
        line-height: 1.25;
      }
      .pmk-13b-panel p {
        margin: 0 0 10px;
        line-height: 1.5;
        opacity: 0.84;
      }
      .pmk-13b-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
        gap: 8px;
        margin: 10px 0;
      }
      .pmk-13b-panel label {
        display: grid;
        gap: 4px;
        min-width: 0;
        font-size: 0.82rem;
        font-weight: 700;
      }
      .pmk-13b-panel input, .pmk-13b-panel textarea {
        width: 100%;
        min-width: 0;
        padding: 8px 10px;
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.28);
        background: rgba(255, 255, 255, 0.05);
      }
      .pmk-13b-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 10px 0;
      }
      .pmk-13b-actions button {
        min-height: 34px;
        padding: 8px 11px;
        border-radius: 10px;
        border: 1px solid rgba(59, 130, 246, 0.34);
        background: rgba(59, 130, 246, 0.12);
        cursor: pointer;
        font-weight: 700;
      }
      .pmk-13b-actions button:disabled {
        opacity: 0.62;
        cursor: wait;
      }
      .pmk-13b-output {
        display: block;
        max-width: 100%;
        margin-top: 10px;
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px dashed rgba(148, 163, 184, 0.34);
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        white-space: normal;
        word-break: break-all;
        overflow-wrap: anywhere;
      }
      .pmk-13b-guardrails {
        display: flex;
        flex-wrap: wrap;
        gap: 7px;
        margin-top: 10px;
      }
      .pmk-13b-guardrails span {
        display: inline-flex;
        min-height: 24px;
        align-items: center;
        padding: 4px 8px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        font-size: 0.75rem;
        font-weight: 700;
      }
      .pmk-13b-table-wrap {
        max-width: 100%;
        overflow-x: auto;
        margin-top: 10px;
      }
      .pmk-13b-table {
        width: 100%;
        min-width: 640px;
        border-collapse: collapse;
      }
      .pmk-13b-table th, .pmk-13b-table td {
        padding: 8px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.20);
        text-align: left;
        vertical-align: top;
      }
      .pmk-13b-table code {
        white-space: normal;
        word-break: break-all;
        overflow-wrap: anywhere;
      }
    `;
    document.head.appendChild(style);
  }

  function ensureHost() {
    let host = document.querySelector("#admin-integration-pilot-controls-host");
    if (!host) {
      host = document.createElement("section");
      host.id = "admin-integration-pilot-controls-host";
      host.setAttribute("data-admin-integration-pilot-controls-host", "true");
      host.setAttribute("aria-label", "Integration Pilot Controls");

      const target =
        document.querySelector("#page-admin-api-keys") ||
        document.querySelector("#main") ||
        document.querySelector("main") ||
        document.body;

      target.appendChild(host);
    }
    return host;
  }

  function guardrails() {
    return `
      <div class="pmk-13b-guardrails" data-admin-pilot-guardrails>
        <span data-admin-pilot-runtime-enabled>false</span>
        <span data-admin-pilot-production-allowed>false</span>
        <span data-admin-pilot-external-http>false</span>
        <span data-admin-pilot-secret-visible>false</span>
      </div>
    `;
  }

  function taskRows(tasks) {
    if (!tasks.length) {
      return `<tr><td colspan="5">No integration pilot tracking tasks yet.</td></tr>`;
    }

    return tasks.map((task) => `
      <tr data-admin-pilot-track-row>
        <td><code>${esc(task.task_id)}</code></td>
        <td>${esc(task.client_id)}</td>
        <td data-admin-pilot-track-status>${esc(task.status)}</td>
        <td><code>${esc(task.masked_activation_permission_key || "—")}</code></td>
        <td>
          <div class="pmk-13b-actions">
            <button type="button" data-admin-pilot-control-action="suspend" data-task-id="${esc(task.task_id)}">Suspend</button>
            <button type="button" data-admin-pilot-control-action="resume" data-task-id="${esc(task.task_id)}">Resume</button>
            <button type="button" data-admin-pilot-control-action="revoke" data-task-id="${esc(task.task_id)}">Revoke</button>
            <button type="button" data-admin-pilot-control-action="cancel" data-task-id="${esc(task.task_id)}">Cancel</button>
          </div>
        </td>
      </tr>
    `).join("");
  }

  function render(payload = {}) {
    ensureStyles();
    const host = ensureHost();
    const tasks = Array.isArray(payload.tasks) ? payload.tasks : [];
    const latestMasked = tasks.find((task) => task.masked_activation_permission_key)?.masked_activation_permission_key || "iapk_****************";

    host.innerHTML = `
      <div class="pmk-13b-shell" data-admin-pilot13b-shell>
        <section class="pmk-13b-panel" data-admin-integration-activation-license-panel>
          <h3>Integration Activation Permission License</h3>
          <p>
            Supervisor-only permission key for preparing integration onboarding.
            Raw output is visible once; stored lists remain masked.
          </p>

          <div class="pmk-13b-grid">
            <label>Client ID <input data-admin-pilot-license-client value="operator-activation-license-13b"></label>
            <label>Operator org <input data-admin-pilot-license-org value="operator-activation-license-13b"></label>
            <label>Officer identity <input data-admin-pilot-license-officer value="integration-supervisor"></label>
          </div>

          <div class="pmk-13b-actions">
            <button type="button" data-admin-pilot-license-generate>Generate Activation Permission Key</button>
          </div>

          <code class="pmk-13b-output" data-admin-pilot-license-output data-admin-activation-permission-key-once>No activation permission key generated yet.</code>

          <p><strong>Latest masked value:</strong> <code data-admin-pilot-license-masked>${esc(latestMasked)}</code></p>
          ${guardrails()}
        </section>

        <section class="pmk-13b-panel" data-admin-integration-pilot-tracking-panel>
          <h3>Integration Pilot Tracking</h3>
          <p>
            Track pilot tasks and supervisor controls without enabling runtime connectors.
          </p>

          <div class="pmk-13b-grid">
            <label>Client ID <input data-admin-pilot-track-client value="operator-pilot-tracking-13b"></label>
            <label>Operator org <input data-admin-pilot-track-org value="operator-pilot-tracking-13b"></label>
            <label>Officer identity <input data-admin-pilot-track-officer value="pilot-tracking-supervisor"></label>
          </div>

          <label>Pilot terms note <textarea data-admin-pilot-track-note rows="2">Safe pilot tracking task for integration readiness.</textarea></label>

          <div class="pmk-13b-actions">
            <button type="button" data-admin-pilot-track-create>Create tracking task</button>
            <button type="button" data-admin-pilot-track-refresh>Refresh tracking</button>
          </div>

          <div class="pmk-13b-table-wrap">
            <table class="pmk-13b-table" data-admin-pilot-track-table>
              <thead>
                <tr><th>Task</th><th>Client</th><th>Status</th><th>Masked key</th><th>Controls</th></tr>
              </thead>
              <tbody>${taskRows(tasks)}</tbody>
            </table>
          </div>

          ${guardrails()}
        </section>
      </div>
    `;

    bind(host);
  }

  async function load() {
    const payload = await requestJson(LIST_ENDPOINT);
    render(payload);
    return payload;
  }

  async function createTask(prefix) {
    const client = document.querySelector(`[data-admin-pilot-${prefix}-client]`)?.value || `operator-${prefix}-13b`;
    const org = document.querySelector(`[data-admin-pilot-${prefix}-org]`)?.value || client;
    const officer = document.querySelector(`[data-admin-pilot-${prefix}-officer]`)?.value || "integration-supervisor";
    const note =
      document.querySelector(`[data-admin-pilot-${prefix}-note]`)?.value ||
      "Safe sandbox-only integration pilot task.";

    return requestJson(LIST_ENDPOINT, {
      method: "POST",
      body: JSON.stringify({
        client_id: client,
        operator_org_id: org,
        integration_officer_identity: officer,
        pilot_terms_note: note,
        source: `admin_${prefix}_isolated_panel_13b`,
        status: "pending_supervisor_review",
        sandbox_only: true,
      }),
    });
  }

  async function generateLicense() {
    const button = document.querySelector("[data-admin-pilot-license-generate]");
    const output = document.querySelector("[data-admin-pilot-license-output]");
    if (button) {
      button.disabled = true;
      button.textContent = "Generating…";
    }
    if (output) {
      output.textContent = "Generating activation permission key…";
      output.dataset.visibleOnce = "false";
    }

    try {
      const created = await createTask("license");
      const taskId = created?.task?.task_id;
      if (!taskId) throw new Error("Missing created pilot task id");

      const issued = await requestJson(`${LIST_ENDPOINT}/${encodeURIComponent(taskId)}/activation-permission-key`, {
        method: "POST",
        body: JSON.stringify({ source: "admin_license_isolated_panel_13b", visible_once: true }),
      });

      const fresh = await requestJson(LIST_ENDPOINT);
      render(fresh);

      const freshOutput = document.querySelector("[data-admin-pilot-license-output]");
      if (freshOutput) {
        freshOutput.textContent =
          issued.activation_permission_key_once ||
          "Generation failed: no raw key returned.";
        freshOutput.dataset.visibleOnce = String(!!issued.activation_permission_key_once);
      }

      return issued;
    } catch (error) {
      const freshOutput = document.querySelector("[data-admin-pilot-license-output]");
      if (freshOutput) {
        freshOutput.textContent = `Generation failed: ${String(error?.message || error)}`;
        freshOutput.dataset.visibleOnce = "false";
      }
      throw error;
    } finally {
      const freshButton = document.querySelector("[data-admin-pilot-license-generate]");
      if (freshButton) {
        freshButton.disabled = false;
        freshButton.textContent = "Generate Activation Permission Key";
      }
    }
  }

  async function controlTask(taskId, action) {
    const payload = await requestJson(`${LIST_ENDPOINT}/${encodeURIComponent(taskId)}/${action}`, {
      method: "POST",
      body: JSON.stringify({ reason: `admin_${action}_isolated_panel_13b` }),
    });
    await load();
    return payload;
  }

  function bind(host) {
    const generate = host.querySelector("[data-admin-pilot-license-generate]");
    if (generate && !generate.dataset.bound) {
      generate.dataset.bound = "true";
      generate.addEventListener("click", () => generateLicense().catch(() => {}));
    }

    const create = host.querySelector("[data-admin-pilot-track-create]");
    if (create && !create.dataset.bound) {
      create.dataset.bound = "true";
      create.addEventListener("click", async () => {
        create.disabled = true;
        try {
          await createTask("track");
          await load();
        } finally {
          create.disabled = false;
        }
      });
    }

    const refresh = host.querySelector("[data-admin-pilot-track-refresh]");
    if (refresh && !refresh.dataset.bound) {
      refresh.dataset.bound = "true";
      refresh.addEventListener("click", () => load().catch(() => {}));
    }

    host.querySelectorAll("[data-admin-pilot-control-action]").forEach((button) => {
      if (button.dataset.bound) return;
      button.dataset.bound = "true";
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await controlTask(button.dataset.taskId, button.dataset.adminPilotControlAction);
        } finally {
          button.disabled = false;
        }
      });
    });
  }

  function boot() {
    ensureStyles();
    render({ tasks: [] });
    load().catch(() => {});
  }

  window.PMK_ADMIN_INTEGRATION_PILOT_CONTROLS_13B = {
    version: VERSION,
    load,
    render,
    createTask,
    generateLicense,
    controlTask,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
// PMK INTEGRATION PILOT CONTROLS 13B END

// PMK 13B isolated guardrail static sentinels
// runtime=false
// production=false
// external_http=false
// secret_visible=false
// runtime_enabled=false
// production_allowed=false
// external_http_enabled=false
// raw_secret_visible=false
