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

  function installMfaReviewState() {
    if (queryValue("review_mfa") !== "1") return;
    if (document.getElementById("registration-mfa-review")) return;

    const style = document.createElement("style");
    style.id = "registration-mfa-review-style";
    style.textContent = `
      #registration-mfa-review {
        min-width: 0;
        width: 100%;
        display: grid;
        gap: 14px;
        margin-top: 22px;
        padding: 18px;
        border: 1px solid #365b7f;
        border-radius: 14px;
        background: rgba(11, 31, 52, .86);
        overflow-wrap: anywhere;
      }
      #registration-mfa-review .mfa-review-grid {
        min-width: 0;
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
        gap: 12px;
      }
      #registration-mfa-review .mfa-review-step {
        min-width: 0;
        padding: 12px;
        border: 1px solid rgba(59, 88, 118, .55);
        border-radius: 10px;
        background: #0b1929;
      }
      #registration-mfa-review .mfa-review-step strong,
      #registration-mfa-review .mfa-review-step span {
        display: block;
      }
      #registration-mfa-review .mfa-review-step span {
        margin-top: 5px;
        color: var(--muted);
        line-height: 1.45;
      }
      #registration-mfa-review .mfa-review-code {
        width: 100%;
        min-height: 46px;
        margin-top: 8px;
        border: 1px solid var(--line-strong);
        border-radius: 10px;
        background: var(--surface-2);
        color: var(--muted);
        padding: 12px 14px;
        font: inherit;
      }
      #registration-mfa-review .mfa-review-action {
        width: 100%;
        min-height: 44px;
        margin-top: 8px;
        border: 1px solid var(--line-strong);
        border-radius: 10px;
        background: #10253c;
        color: #d8e8fa;
        font: inherit;
        font-weight: 750;
        opacity: .7;
      }
      #registration-mfa-review .mfa-review-truth {
        margin: 0;
        padding: 12px 14px;
        border-left: 3px solid #83c0ff;
        background: #0b1929;
        color: var(--muted);
        line-height: 1.5;
      }
      @media (max-width: 520px) {
        #registration-mfa-review { padding: 14px; }
        #registration-mfa-review .mfa-review-grid { grid-template-columns: minmax(0, 1fr); }
      }
    `;
    document.head.appendChild(style);

    const review = document.createElement("section");
    review.id = "registration-mfa-review";
    review.dataset.reviewOnly = "true";
    review.setAttribute("aria-labelledby", "registration-mfa-review-title");
    review.innerHTML = `
      <div>
        <p class="plan-context-kicker">Review-only layout state</p>
        <h2 id="registration-mfa-review-title" class="plan-context-title">MFA enrollment preview</h2>
        <p class="plan-context-note">
          This preview exists only to verify the post-registration MFA layout. It does not enroll a factor, expose a secret, create a QR code, or call an MFA endpoint.
        </p>
      </div>
      <div class="mfa-review-grid">
        <div class="mfa-review-step">
          <strong>1. Authenticator app</strong>
          <span>Real TOTP enrollment becomes available only after email verification and an authenticated sign-in session.</span>
        </div>
        <div class="mfa-review-step">
          <strong>2. Confirm authenticator code</strong>
          <span>The real confirmation step verifies a TOTP code before MFA becomes active.</span>
          <input class="mfa-review-code" type="text" inputmode="numeric" placeholder="000000" aria-label="MFA code layout preview" disabled>
          <button class="mfa-review-action" type="button" disabled>Confirm MFA</button>
        </div>
      </div>
      <p class="mfa-review-truth">
        Security sequence: register → verify email → sign in → enroll TOTP → confirm TOTP. This review state proves layout only; backend MFA authority remains unchanged.
      </p>
    `;

    status.insertAdjacentElement("afterend", review);
    document.documentElement.dataset.registrationMfaReview = "true";
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
  installMfaReviewState();
  loadSelectedOfferContext();
  loadRegistrationConfig();
})();
