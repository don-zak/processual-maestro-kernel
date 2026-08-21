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
  const passwordVisibility = document.getElementById("registration-password-visibility");
  const planContext = document.getElementById("registration-plan-context");
  const planName = document.getElementById("registration-plan-name");
  const planBilling = document.getElementById("registration-plan-billing");
  const planPrice = document.getElementById("registration-plan-price");
  const planPriceWrap = document.getElementById("registration-plan-price-wrap");
  const planNote = document.getElementById("registration-plan-note");

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

  function money(value) {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return null;
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: amount % 1 ? 2 : 0,
      maximumFractionDigits: 2,
    }).format(amount);
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

  function installPasswordVisibility() {
    if (!passwordInput || !passwordVisibility) return;
    passwordVisibility.addEventListener("click", () => {
      const visible = passwordInput.type === "text";
      passwordInput.type = visible ? "password" : "text";
      passwordVisibility.textContent = visible ? "Show" : "Hide";
      passwordVisibility.setAttribute(
        "aria-label",
        visible ? "Show password" : "Hide password",
      );
      passwordVisibility.setAttribute("aria-pressed", visible ? "false" : "true");
      passwordInput.focus({ preventScroll: true });
    });
  }

  async function loadSelectedOfferContext() {
    const planId = selectedPlanId();
    if (!planId || !planContext) return;

    planContext.hidden = false;
    if (planName) planName.textContent = planId;

    const billing = selectedBillingPeriod();
    if (planBilling) {
      planBilling.textContent = billing
        ? billing.charAt(0).toUpperCase() + billing.slice(1)
        : "Selection required";
    }

    if (!billing) {
      if (planPriceWrap) planPriceWrap.hidden = true;
      if (planNote) {
        planNote.textContent =
          "This offer link is incomplete. Return to Plans and select monthly or annual billing before submitting.";
      }
      return;
    }

    try {
      const response = await fetch("/billing/public-plan-journey", {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error("catalog_unavailable");

      const payload = await response.json();
      const plans = Array.isArray(payload.plans) ? payload.plans : [];
      const plan = plans.find((item) => item.plan_id === planId);
      if (!plan) throw new Error("plan_unavailable");

      if (planName) planName.textContent = plan.display_name || plan.plan_id;
      const rawPrice = billing === "annual"
        ? plan.annual_price_usd
        : plan.monthly_price_usd;
      const formattedPrice = money(rawPrice);

      if (planPriceWrap) planPriceWrap.hidden = !formattedPrice;
      if (planPrice && formattedPrice) {
        planPrice.textContent = `${formattedPrice} / ${billing === "annual" ? "year" : "month"}`;
      }
      if (planNote) {
        planNote.textContent =
          "This selection will be carried into the registration request and revalidated by the backend. Registration alone does not activate payment, entitlement, quota, or checkout.";
      }
    } catch (_error) {
      if (planPriceWrap) planPriceWrap.hidden = true;
      if (planNote) {
        planNote.textContent =
          "Selected offer details are temporarily unavailable. The registration request remains bound to the selected plan and billing period and will be revalidated by the backend.";
      }
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
  installPasswordVisibility();
  loadSelectedOfferContext();
  loadRegistrationConfig();
})();
