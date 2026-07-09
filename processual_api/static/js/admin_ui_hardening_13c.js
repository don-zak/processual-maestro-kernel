/* ADMIN_UI_HARDENING_13C_R1
   Presentation-only DOM enhancement. No fetch, no key generation, no secret display.
*/
(function () {
  "use strict";

  const VERSION = "admin-ui-hardening-13c-r2";
  let scheduled = false;

  function markCards() {
    document.querySelectorAll("section").forEach((section) => {
      section.classList.add("pmk-admin-card");
    });
  }

  function wrapTables() {
    document.querySelectorAll("table").forEach((table) => {
      if (table.closest(".pmk-admin-table-frame")) return;

      const frame = document.createElement("div");
      frame.className = "pmk-admin-table-frame";
      frame.setAttribute("tabindex", "0");
      frame.setAttribute("role", "region");

      const title = table.closest("section")?.querySelector("h2,h3,h4")?.textContent?.trim() || "Admin table";
      frame.setAttribute("aria-label", title);

      table.parentNode.insertBefore(frame, table);
      frame.appendChild(table);
    });
  }

  function groupActionButtons() {
    document.querySelectorAll("td").forEach((td) => {
      if (td.querySelector(":scope > .pmk-admin-actions-row")) return;

      const buttons = Array.from(td.children).filter((node) => node.tagName?.toLowerCase() === "button");
      if (buttons.length < 2) return;

      const row = document.createElement("div");
      row.className = "pmk-admin-actions-row";
      td.insertBefore(row, buttons[0]);
      buttons.forEach((button) => row.appendChild(button));
    });

    document.querySelectorAll(".pmk-13b-actions").forEach((row) => {
      row.classList.add("pmk-admin-button-row");
    });
  }

  function chipBareBooleans() {
    const scopes = [
      "[data-admin-integration-activation-license-panel]",
      "[data-admin-integration-pilot-tracking-panel]",
      "[data-admin-operator-readiness-package]",
      "[data-admin-integration-readiness-panel]",
      "[data-admin-integration-readiness-tracking-panel]"
    ].join(",");

    document.querySelectorAll(scopes).forEach((scope) => {
      scope.querySelectorAll("div,p,span,li,td").forEach((node) => {
        if (node.children.length) return;

        const value = node.textContent.trim();
        if (value !== "false" && value !== "true") return;

        node.classList.add("pmk-admin-boolean-chip");
        node.dataset.value = value;
        node.title = value === "false" ? "Guardrail remains false/disabled" : "Flag is true/enabled";
      });
    });
  }

  function collapseLargeJsonBlocks() {
    document.querySelectorAll("pre").forEach((pre) => {
      if (pre.closest(".pmk-admin-json-details")) return;

      const text = pre.textContent || "";
      const looksLarge = text.length > 900;
      const looksMetadata = text.includes('"key_id"') || text.includes('"scopes"') || text.includes('"quota_limit"');
      const looksJson = text.trim().startsWith("{") || text.trim().startsWith("[");

      if (!looksLarge && !looksMetadata) return;
      if (!looksJson && !looksMetadata) return;

      const details = document.createElement("details");
      details.className = "pmk-admin-json-details";

      const summary = document.createElement("summary");
      summary.textContent = "Developer metadata details";

      pre.parentNode.insertBefore(details, pre);
      details.appendChild(summary);
      details.appendChild(pre);
    });
  }

  function grid13BForms() {
    document.querySelectorAll("[data-admin-integration-activation-license-panel], [data-admin-integration-pilot-tracking-panel]").forEach((panel) => {
      const labels = Array.from(panel.querySelectorAll("label"));
      if (labels.length < 2) return;

      const parent = labels[0].parentElement;
      if (!parent || parent.classList.contains("pmk-admin-form-grid")) return;

      const grid = document.createElement("div");
      grid.className = "pmk-admin-form-grid";
      parent.insertBefore(grid, labels[0]);
      labels.forEach((label) => grid.appendChild(label));
    });
  }

  function labelGuardrailBooleans() {
    const guardrailLabels = [
      "Runtime enabled",
      "Production allowed",
      "External HTTP",
      "Raw secret visible"
    ];

    const panels = [
      "[data-admin-integration-activation-license-panel]",
      "[data-admin-integration-pilot-tracking-panel]"
    ];

    panels.forEach((selector) => {
      document.querySelectorAll(selector).forEach((panel) => {
        const chips = Array.from(panel.querySelectorAll(".pmk-admin-boolean-chip"))
          .filter((chip) => {
            const value = chip.dataset.value || chip.textContent.trim();
            return value === "false" || value === "true";
          });

        chips.slice(0, guardrailLabels.length).forEach((chip, index) => {
          const value = chip.dataset.value || chip.textContent.trim();
          chip.dataset.guardrailLabel = guardrailLabels[index];
          chip.setAttribute("aria-label", `${guardrailLabels[index]}: ${value}`);
          chip.setAttribute("title", `${guardrailLabels[index]}: ${value}`);
          chip.textContent = `${guardrailLabels[index]}: ${value}`;
        });

        const firstChip = chips[0];
        if (firstChip && !panel.querySelector(".pmk-admin-guardrail-caption")) {
          const caption = document.createElement("div");
          caption.className = "pmk-admin-guardrail-caption";
          caption.textContent = "Safety guardrails";
          firstChip.parentNode.insertBefore(caption, firstChip);
        }
      });
    });
  }

  function enhanceAll() {
    markCards();
    wrapTables();
    groupActionButtons();
    chipBareBooleans();
    labelGuardrailBooleans();
    collapseLargeJsonBlocks();
    grid13BForms();
  }

  function scheduleEnhance() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      enhanceAll();
    });
  }

  function start() {
    enhanceAll();
    const observer = new MutationObserver(scheduleEnhance);
    observer.observe(document.body, { childList: true, subtree: true });
    window.PMK_ADMIN_UI_HARDENING_13C.observer = observer;
  }

  window.PMK_ADMIN_UI_HARDENING_13C = {
    version: VERSION,
    enhanceAll
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
