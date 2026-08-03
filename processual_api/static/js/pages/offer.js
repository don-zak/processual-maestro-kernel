const catalogEndpoint =
  document
    .querySelector('meta[name="maestro-plan-catalog-endpoint"]')
    ?.getAttribute("content") ?? "/billing/public-plan-journey";

const title = document.querySelector("#offer-title");
const description = document.querySelector("#offer-description");
const card = document.querySelector("#offer-card");
const status = document.querySelector("#offer-status");
const content = document.querySelector("#offer-content");
const price = document.querySelector("#offer-price");
const providerNote = document.querySelector("#provider-note");
const action = document.querySelector("#offer-action");

function selectedPlanId() {
  const parts = window.location.pathname.split("/").filter(Boolean);

  if (parts.length !== 2 || parts[0] !== "offer") {
    return null;
  }

  return decodeURIComponent(parts[1]);
}

function formatMonthlyPrice(value) {
  const amount = Number(value);

  if (!Number.isFinite(amount)) {
    return null;
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
}

function renderOffer(plan, payload) {
  title.textContent = plan.display_name;
  description.textContent = plan.description;

  providerNote.textContent = payload.provider_cost_included
    ? ""
    : "Provider and API usage costs are not included.";

  if (plan.requires_assessment || !plan.registration_available) {
    price.textContent = "Pricing after assessment";
    action.textContent = "Request assessment";
    action.href = `/apply?plan_id=${encodeURIComponent(
      plan.plan_id,
    )}&journey=assessment`;
  } else {
    const formatted = formatMonthlyPrice(plan.monthly_price_usd);

    if (!formatted) {
      throw new Error("invalid_price");
    }

    price.textContent = `${formatted} / month`;
    action.textContent = "Start registration";
    action.href = `/register?plan_id=${encodeURIComponent(plan.plan_id)}`;
  }

  status.hidden = true;
  content.hidden = false;
  card.setAttribute("aria-busy", "false");
}

async function loadOffer() {
  const planId = selectedPlanId();

  if (!planId) {
    status.textContent = "This plan could not be found.";
    card.setAttribute("aria-busy", "false");
    return;
  }

  try {
    const response = await fetch(catalogEndpoint, {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error("catalog_unavailable");
    }

    const payload = await response.json();
    const plan = payload.plans.find((item) => item.plan_id === planId);

    if (!plan) {
      title.textContent = "Plan unavailable";
      status.textContent = "This plan could not be found.";
      card.setAttribute("aria-busy", "false");
      return;
    }

    renderOffer(plan, payload);
  } catch {
    title.textContent = "Offer unavailable";
    status.textContent =
      "This offer is temporarily unavailable. Please try again later.";
    card.setAttribute("aria-busy", "false");
  }
}

loadOffer();
