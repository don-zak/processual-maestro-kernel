const endpoint =
  document.querySelector('meta[name="maestro-plan-catalog-endpoint"]')
    ?.getAttribute("content") ?? "/billing/public-plan-journey";

const grid = document.querySelector("#plans-grid");
const status = document.querySelector("#plans-status");
const annualBillingNote = document.querySelector("#annual-billing-note");

function money(value) {
  if (value === null || value === undefined || value === "") return null;
  const amount = Number(value);
  if (!Number.isFinite(amount)) return null;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: amount % 1 ? 2 : 0,
    maximumFractionDigits: 2,
  }).format(amount);
}

function quota(value) {
  if (value === null || value === undefined || value === "") {
    return "Quota defined from the approved assessment scope";
  }
  const amount = Number(value);
  return Number.isFinite(amount)
    ? `${new Intl.NumberFormat("en-US").format(amount)} Maestro units / month`
    : "Quota defined from the approved assessment scope";
}

function discountPercent(plan) {
  const amount = Number(plan.annual_discount_percent);
  return Number.isFinite(amount) && amount > 0 ? amount : null;
}

function assessmentPriceLabel(plan) {
  if (plan.commercial_model === "requirements_based_evaluation") {
    return "Evaluation price defined after assessment";
  }
  if (plan.commercial_model === "requirements_based_contract") {
    return "Commercial proposal based on approved requirements";
  }
  return "Pricing after assessment";
}

function assessmentTermsLabel(plan) {
  if (plan.commercial_model === "requirements_based_evaluation") {
    return "One-month evaluation · agreed quota · no public fixed price";
  }
  if (plan.commercial_model === "requirements_based_contract") {
    return "Capacity, integration, support and SLA defined by contract";
  }
  return "Commercial terms defined after assessment";
}

function createPlanCard(plan) {
  const link = document.createElement("a");
  link.className = "plan-choice-card";
  link.href = `/offer/${encodeURIComponent(plan.plan_id)}`;
  link.dataset.planId = plan.plan_id;
  link.dataset.commercialModel = plan.commercial_model || "catalog_subscription";

  const audience = document.createElement("span");
  audience.className = "plan-audience";
  audience.textContent = plan.audience;

  const name = document.createElement("h2");
  name.className = "plan-choice-name";
  name.textContent = plan.display_name;

  const description = document.createElement("p");
  description.className = "plan-description";
  description.textContent = plan.description;

  const price = document.createElement("div");
  price.className = "plan-price";
  const monthly = money(plan.monthly_price_usd);
  price.textContent = monthly
    ? `${monthly} / month`
    : assessmentPriceLabel(plan);

  const annual = document.createElement("p");
  annual.className = "plan-annual";
  const annualPrice = money(plan.annual_price_usd);
  const discount = discountPercent(plan);
  annual.textContent = annualPrice
    ? `${annualPrice} / year${discount ? ` - save ${discount}%` : ""}`
    : assessmentTermsLabel(plan);

  const quotaText = document.createElement("p");
  quotaText.className = "plan-quota";
  quotaText.textContent = quota(plan.included_quota_units);

  const members = document.createElement("p");
  members.className = "plan-members";
  members.textContent = "Unlimited authorized members within quota";

  const action = document.createElement("span");
  action.className = "plan-card-action";
  action.textContent = plan.requires_assessment
    ? "Review assessment and commercial scope"
    : "View full plan details";

  link.append(audience, name, description, price, annual, quotaText, members, action);
  return link;
}

function renderCatalogBillingNote(payload) {
  if (!annualBillingNote) return;
  const discount = Number(payload.annual_discount_percent);
  const discountText = Number.isFinite(discount) && discount > 0
    ? `Eligible annual base-plan billing saves ${discount}%.`
    : "Annual base-plan savings follow the current commercial catalog.";
  annualBillingNote.textContent =
    `${discountText} On-demand quota add-ons are separate and never discounted. ` +
    "Enterprise evaluation and deployment pricing is requirements-based and is not covered by the public annual discount.";
}

async function loadPlans() {
  try {
    const response = await fetch(endpoint, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("catalog_unavailable");

    const payload = await response.json();
    if (!Array.isArray(payload.plans) || payload.plans.length === 0) {
      throw new Error("catalog_empty");
    }

    renderCatalogBillingNote(payload);
    grid.replaceChildren(...payload.plans.map(createPlanCard));
    grid.setAttribute("aria-busy", "false");
  } catch {
    status.textContent = "Plans are temporarily unavailable. Please try again later.";
    grid.setAttribute("aria-busy", "false");
  }
}

loadPlans();