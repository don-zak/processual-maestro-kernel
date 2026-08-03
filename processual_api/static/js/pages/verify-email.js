"use strict";

(function verificationController() {
  const status = document.getElementById("verification-status");
  const resendForm = document.getElementById("verification-resend-form");
  const resendButton = document.getElementById("verification-resend-button");
  const emailInput = document.getElementById("verification-email");
  const parameters = new URLSearchParams(window.location.search);

  if (!status || !resendForm || !resendButton || !emailInput) {
    return;
  }

  function showState(name, message) {
    document
      .querySelectorAll("[data-verification-state]")
      .forEach((section) => {
        section.dataset.active =
          section.dataset.verificationState === name ? "true" : "false";
      });

    status.textContent = message;
    status.dataset.state = name;
  }

  async function processVerification(token) {
    showState("processing", "Processing the verification request...");

    try {
      const response = await fetch("/auth/verify-email", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ token }),
      });

      if (response.status === 429) {
        showState(
          "rate-limited",
          "Verification attempts are temporarily limited.",
        );
        return;
      }

      if (response.status === 503) {
        showState(
          "unavailable",
          "Verification service is temporarily unavailable.",
        );
        return;
      }

      if (!response.ok) {
        showState("invalid", "The verification request could not be processed.");
        return;
      }

      const result = await response.json();

      if (result.status === "processed") {
        showState(
          "verified",
          "Verification processed. You may continue to sign in.",
        );
        return;
      }

      showState(
        "already-used",
        "Verification was processed. Continue to sign in.",
      );
    } catch (_error) {
      showState(
        "unavailable",
        "Verification could not be completed. Check your connection.",
      );
    }
  }

  async function resendVerification(event) {
    event.preventDefault();

    if (!resendForm.reportValidity()) {
      status.textContent = "Enter a valid email address.";
      return;
    }

    resendButton.disabled = true;
    status.textContent = "Requesting another verification email...";

    try {
      const response = await fetch("/auth/verification/resend", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: emailInput.value.trim(),
        }),
      });

      if (response.status === 429) {
        showState(
          "rate-limited",
          "Please wait before requesting another verification email.",
        );
        return;
      }

      if (response.status === 503) {
        showState(
          "unavailable",
          "Verification email delivery is temporarily unavailable.",
        );
        return;
      }

      if (!response.ok) {
        status.textContent = "The resend request could not be accepted.";
        return;
      }

      showState(
        "pending",
        "Request accepted. Check your email for the verification link.",
      );
    } catch (_error) {
      showState(
        "unavailable",
        "The resend request could not be completed.",
      );
    } finally {
      resendButton.disabled = false;
    }
  }

  const email = parameters.get("email");
  const token = parameters.get("token");

  if (email) {
    emailInput.value = email;
  }

  resendForm.addEventListener("submit", resendVerification);

  if (token) {
    processVerification(token);
  } else {
    showState(
      "pending",
      "Waiting for a verification link. You may request another email below.",
    );
  }
})();
