(() => {
  "use strict";

  const READY = "ready-v2";

  function eyeIcon(visible) {
    if (visible) {
      return `
        <svg viewBox="0 0 24 24" width="20" height="20"
             aria-hidden="true" focusable="false">
          <path fill="currentColor"
            d="M3.3 2.3 2.2 3.4l3.1 3.1A12.6 12.6 0 0 0 1.6 11l-.2.5.2.5C3.4 16.2 7.2 19 12 19c1.6 0 3.1-.3 4.4-.9l4.2 4.2 1.1-1.1L3.3 2.3Zm8.7 14.9c-3.9 0-7-2.1-8.6-5.7a10.8 10.8 0 0 1 3.1-3.8l1.8 1.8A4.5 4.5 0 0 0 14.5 15l1.2 1.2c-1.1.6-2.3 1-3.7 1Zm-2.1-6.1 3 3a2.7 2.7 0 0 1-3-3Zm2.1-7.1c4.8 0 8.6 2.8 10.4 7l.2.5-.2.5a12.8 12.8 0 0 1-3.2 4.2L17.9 15a10.6 10.6 0 0 0 2.7-3.5C19 7.9 15.9 5.8 12 5.8c-.8 0-1.5.1-2.2.3L8.5 4.8A12 12 0 0 1 12 4Z"/>
        </svg>`;
    }

    return `
      <svg viewBox="0 0 24 24" width="20" height="20"
           aria-hidden="true" focusable="false">
        <path fill="currentColor"
          d="M12 5c4.8 0 8.6 2.8 10.4 7l.2.5-.2.5C20.6 17.2 16.8 20 12 20S3.4 17.2 1.6 13l-.2-.5.2-.5C3.4 7.8 7.2 5 12 5Zm0 1.8c-3.9 0-7 2.1-8.6 5.7 1.6 3.6 4.7 5.7 8.6 5.7s7-2.1 8.6-5.7C19 8.9 15.9 6.8 12 6.8Zm0 2.2a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Zm0 1.8a1.7 1.7 0 1 0 0 3.4 1.7 1.7 0 0 0 0-3.4Z"/>
      </svg>`;
  }

  function restoreSelection(input, start, end) {
    try {
      input.focus({ preventScroll: true });
    } catch {
      input.focus();
    }

    if (start !== null && end !== null) {
      try {
        input.setSelectionRange(start, end);
      } catch {
        // Selection APIs may be unavailable for an unusual input type.
      }
    }
  }

  function installPasswordToggle(input) {
    if (
      !(input instanceof HTMLInputElement) ||
      input.dataset.pmkPasswordToggle === READY
    ) {
      return;
    }

    const currentType = input.getAttribute("type")?.toLowerCase();
    if (currentType !== "password" && currentType !== "text") {
      return;
    }

    input.dataset.pmkPasswordToggle = READY;

    let wrapper = input.closest(".pmk-password-field");
    if (!wrapper) {
      wrapper = document.createElement("div");
      wrapper.className = "pmk-password-field";
      input.parentNode.insertBefore(wrapper, input);
      wrapper.appendChild(input);
    }

    if (wrapper.querySelector(".pmk-password-toggle")) {
      return;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "pmk-password-toggle";
    button.setAttribute("aria-pressed", "false");
    button.setAttribute("aria-label", "Show password");
    button.setAttribute("title", "Show password");
    button.innerHTML = eyeIcon(false);

    button.addEventListener("pointerdown", (event) => {
      event.preventDefault();
    });

    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();

      const start = input.selectionStart;
      const end = input.selectionEnd;
      const show = input.type === "password";

      input.type = show ? "text" : "password";
      button.setAttribute("aria-pressed", String(show));
      button.setAttribute(
        "aria-label",
        show ? "Hide password" : "Show password",
      );
      button.setAttribute(
        "title",
        show ? "Hide password" : "Show password",
      );
      button.innerHTML = eyeIcon(show);

      restoreSelection(input, start, end);
    });

    wrapper.appendChild(button);
  }

  function scanPasswordFields(root = document) {
    root
      .querySelectorAll('input[type="password"], input[data-pmk-password-toggle]')
      .forEach(installPasswordToggle);
  }

  function replaceCommercialGateway() {
    const oldButton = document.getElementById(
      "login-offers-registration-button",
    );
    const oldPanel = document.getElementById("commercial-offers-panel");

    if (oldPanel) {
      oldPanel.hidden = true;
    }

    const host = document.getElementById("login-commercial-actions");
    if (!host || host.dataset.pmkAligned === READY) {
      return;
    }

    host.dataset.pmkAligned = READY;
    host.innerHTML = "";

    const row = document.createElement("div");
    row.className = "pmk-auth-link-row";

    const createAccount = document.createElement("a");
    createAccount.className = "pmk-auth-link primary";
    createAccount.href = "/register.html";
    createAccount.textContent = "Create account";
    createAccount.setAttribute(
      "aria-label",
      "Create a Processual Maestro account",
    );

    const viewPlans = document.createElement("a");
    viewPlans.className = "pmk-auth-link";
    viewPlans.href = "/pricing";
    viewPlans.textContent = "View subscription plans";
    viewPlans.setAttribute(
      "aria-label",
      "View Processual Maestro subscription options",
    );

    row.append(createAccount, viewPlans);
    host.appendChild(row);

    if (oldButton) {
      oldButton.remove();
    }
  }

  function refresh(root = document) {
    scanPasswordFields(root);
    replaceCommercialGateway();
  }

  function start() {
    refresh();

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node instanceof Element) {
            if (node.matches('input[type="password"]')) {
              installPasswordToggle(node);
            }
            scanPasswordFields(node);
          }
        }
      }
      replaceCommercialGateway();
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
    });

    window.setTimeout(refresh, 0);
    window.setTimeout(refresh, 250);
    window.setTimeout(refresh, 1000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
