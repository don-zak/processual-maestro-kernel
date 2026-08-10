const endpoint =
  document.querySelector('meta[name="maestro-plan-catalog-endpoint"]')
    ?.getAttribute("content") ?? "/billing/public-plan-journey";

const grid = document.querySelector("#plans-grid");
const status = document.querySelector("#plans-status");

function money(value) {
  if (value === null || value === undefined || value === "") return "Assessment";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "Assessment";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: amount % 1 ? 2 : 0,
    maximumFractionDigits: 2,
  }).format(amount);
}

function quota(value) {
  if (value === null || value === undefined || value === "") return "Quota defined during assessment";
  const amount = Number(value);
  return Number.isFinite(amount)
    ? `${new Intl.NumberFormat("en-US").format(amount)} Maestro units / month`
    : "Quota defined during assessment";
}

function discountPercent(plan) {
  const amount = Number(plan.annual_discount_percent);
  return Number.isFinite(amount) && amount > 0 ? amount : null;
}

function createPlanCard(plan) {
  const link = document.createElement("a");
  link.className = "plan-choice-card";
  link.href = `/offer/${encodeURIComponent(plan.plan_id)}`;
  link.dataset.planId = plan.plan_id;

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
  price.textContent = plan.monthly_price_usd
    ? `${money(plan.monthly_price_usd)} / month`
    : "Pricing after assessment";

  const annual = document.createElement("p");
  annual.className = "plan-annual";
  const discount = discountPercent(plan);
  annual.textContent = plan.annual_price_usd
    ? `${money(plan.annual_price_usd)} / year${discount ? ` - save ${discount}%` : ""}`
    : "Commercial terms defined after assessment";

  const quotaText = document.createElement("p");
  quotaText.className = "plan-quota";
  quotaText.textContent = quota(plan.included_quota_units);

  const members = document.createElement("p");
  members.className = "plan-members";
  members.textContent = "Unlimited members within quota";

  const action = document.createElement("span");
  action.className = "plan-card-action";
  action.textContent = "View full plan details";

  link.append(audience, name, description, price, annual, quotaText, members, action);
  return link;
}

async function loadPlans() {
  try {
    const response = await fetch(endpoint, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("catalog_unavailable");

    const payload = await response.json();
    if (!Array.isArray(payload.plans) || payload.plans.length === 0) {
      throw new Error("catalog_empty");
    }

    grid.replaceChildren(...payload.plans.map(createPlanCard));
    grid.setAttribute("aria-busy", "false");
  } catch {
    status.textContent = "Plans are temporarily unavailable. Please try again later.";
    grid.setAttribute("aria-busy", "false");
  }
}

loadPlans();