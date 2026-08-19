"use strict";

(function registrationController() {
  const form = document.getElementById("registration-form");
  const status = document.getElementById("registration-status");
  const submit = document.getElementById("registration-submit");
  const modeFieldset = document.getElementById("registration-mode-fieldset");
  const organizationField = document.getElementById("organization-name-field");
  const organizationInput = document.getElementById("registration-organization-name");
  const passwordInput = document.getElementById("registration-password");
  const passwordMinimum = document.getElementById("password-minimum");

  if (!form || !status || !submit) {
    return;
  }

  function selectedMode() {
    const selected = form.querySelector('input[name="registration_mode"]:checked');
    return selected ? selected.value : "individual";
  }

  function queryValue(name) {
    const value = new URLSearchParams(window.location.search).get(name);
    const normalized = String(value || "").trim();
    return normalized || null;
  }

  function selectedPlanId() {
    return queryValue("plan_id");
  }

  function selectedBillingPeriod() {
    const period = queryValue("billing_period");
    return period === "monthly" || period === "annual" ? period : null;
  }

  function setStatus(message, state) {
    status.textContent = message;
    status.dataset.state = state;
  }

  function syncMode() {
    const organization = selectedMode() === "organization";
    organizationField.hidden = !organization;
    organizationInput.required = organization;

    if (!organization) {
      organizationInput.value = "";
    }
  }

  async function loadRegistrationConfig() {
    try {
      const response = await fetch("/auth/registration/config", {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });

      if (!response.ok) {
        throw new Error("Registration configuration unavailable.");
      }

      const config = await response.json();
      const minimum = Number(config.password_min_length || 12);
      const maximum = Number(config.password_max_length || 1024);
      const allowedModes = Array.isArray(config.registration_modes)
        ? config.registration_modes
        : ["individual", "organization"];

      passwordInput.minLength = minimum;
      passwordInput.maxLength = maximum;
      passwordMinimum.textContent = String(minimum);

      modeFieldset
        .querySelectorAll('input[name="registration_mode"]')
        .forEach((input) => {
          input.disabled = !allowedModes.includes(input.value);
        });

      syncMode();
    } catch (_error) {
      setStatus(
        "Registration settings are temporarily unavailable. The safe defaults remain active.",
        "error",
      );
    }
  }

  function payloadForMode(mode) {
    const formData = new FormData(form);
    const payload = {
      email: String(formData.get("email") || "").trim(),
      full_name: String(formData.get("full_name") || "").trim(),
      password: String(formData.get("password") || ""),
      accepted_terms_version: String(
        formData.get("accepted_terms_version") || "current",
      ),
    };

    if (mode === "organization") {
      payload.organization_name = String(
        formData.get("organization_name") || "",
      ).trim();
    }

    const planId = selectedPlanId();
    if (planId) {
      payload.selected_plan_id = planId;
      payload.billing_period = selectedBillingPeriod();
    }

    return payload;
  }

  async function submitRegistration(event) {
    event.preventDefault();

    if (!form.reportValidity()) {
      setStatus("Review the highlighted registration fields.", "error");
      return;
    }

    const planId = selectedPlanId();
    if (planId && !selectedBillingPeriod()) {
      setStatus(
        "This plan registration link is incomplete. Return to Plans and select monthly or annual billing.",
        "error",
      );
      return;
    }

    const mode = selectedMode();
    const endpoint =
      mode === "organization"
        ? "/auth/register/organization"
        : "/auth/register";

    submit.disabled = true;
    setStatus("Submitting your registration request...", "loading");

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payloadForMode(mode)),
      });

      if (response.status === 429) {
        setStatus(
          "Too many registration attempts. Please try again later.",
          "error",
        );
        return;
      }

      if (response.status === 503) {
        setStatus(
          "Registration service is temporarily unavailable.",
          "error",
        );
        return;
      }

      if (!response.ok) {
        setStatus("Invalid registration request.", "error");
        return;
      }

      const result = await response.json();

      if (result.status === "accepted") {
        setStatus(
          "Registration request accepted. Check your email to continue.",
          "success",
        );

        const email = encodeURIComponent(
          String(new FormData(form).get("email") || "").trim(),
        );

        window.setTimeout(() => {
          window.location.assign(`/verify-email?email=${email}`);
        }, 900);

        return;
      }

      setStatus(
        "Registration request accepted. Check your email to continue.",
        "success",
      );
    } catch (_error) {
      setStatus(
        "Registration could not be submitted. Check your connection and retry.",
        "error",
      );
    } finally {
      submit.disabled = false;
    }
  }

  modeFieldset.addEventListener("change", syncMode);
  form.addEventListener("submit", submitRegistration);
  loadRegistrationConfig();
})();
