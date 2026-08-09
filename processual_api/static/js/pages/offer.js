const endpoint =
  document.querySelector('meta[name="maestro-plan-catalog-endpoint"]')
    ?.getAttribute("content") ?? "/billing/public-plan-journey";

const byId = (id) => document.getElementById(id);

function selectedPlanId() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  return parts.length === 2 && parts[0] === "offer"
    ? decodeURIComponent(parts[1])
    : null;
}

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

function discountPercent(plan) {
  const amount = Number(plan.annual_discount_percent);
  return Number.isFinite(amount) && amount > 0 ? amount : null;
}

function replaceList(element, values) {
  const items = Array.isArray(values) ? values : [];
  element.replaceChildren(...items.map((value) => {
    const item = document.createElement("li");
    item.textContent = String(value);
    return item;
  }));
}

function render(plan) {
  byId("offer-title").textContent = plan.display_name;
  byId("offer-audience").textContent = plan.audience;
  byId("offer-description").textContent = plan.description;

  byId("offer-quota").textContent = plan.included_quota_units !== null && plan.included_quota_units !== undefined
    ? `${new Intl.NumberFormat("en-US").format(plan.included_quota_units)} units / month`
    : "Capacity defined during assessment";

  const monthly = money(plan.monthly_price_usd);
  const annual = money(plan.annual_price_usd);
  const annualDiscount = discountPercent(plan);
  const assessmentOnly =
    plan.requires_assessment || !plan.registration_available;

  byId("offer-monthly-price").textContent = monthly
    ? `${monthly} / month`
    : "Pricing defined during assessment";

  const annualPrice = byId("offer-annual-price");
  const annualSavings = byId("offer-savings");
  annualPrice.hidden = assessmentOnly;
  annualSavings.hidden = assessmentOnly;

  if (assessmentOnly) {
    annualPrice.textContent = "";
    annualSavings.textContent = "";
  } else {
    annualPrice.textContent = `${annual} / year`;
    annualSavings.textContent = annualDiscount
      ? `Save ${annualDiscount}% on the base annual plan.`
      : "Annual billing uses the published base plan price.";
  }

  replaceList(byId("offer-features"), plan.features);
  byId("offer-byok-summary").textContent = plan.byok?.summary || "";
  replaceList(byId("offer-exclusions"), plan.byok?.excluded_costs);

  const addOns = Array.isArray(plan.quota_add_ons) ? plan.quota_add_ons : [];
  const addOnCards = addOns.map((item) => {
    const card = document.createElement("article");
    card.className = "add-on-card";
    const title = document.createElement("h3");
    title.textContent = item.display_name;
    const units = document.createElement("p");
    units.className = "add-on-value";
    units.textContent = `${new Intl.NumberFormat("en-US").format(item.units)} units`;
    const price = document.createElement("p");
    price.className = "add-on-price";
    price.textContent = `${money(item.price_usd)} per package`;
    const terms = document.createElement("p");
    terms.className = "muted";
    terms.textContent = "Purchased separately when needed. No recurring commitment. Annual subscription discount does not apply.";
    const state = document.createElement("p");
    state.className = "commercial-warning";
    state.textContent = item.purchase_enabled ? "Available for active subscriptions." : "Price preview only. Purchase activation remains disabled.";
    card.append(title, units, price, terms, state);
    return card;
  });
  byId("offer-add-ons").replaceChildren(...addOnCards);
  if (addOnCards.length === 0) {
    byId("offer-add-ons").textContent = "No public quota package is available for this assessment-only plan.";
  }

  const duration = plan.trial?.duration_days;
  const terminationPolicy = plan.trial?.termination_policy;
  byId("offer-trial-duration").textContent =
    terminationPolicy === "30_days_or_agreed_quota_exhausted"
      ? "Trial duration: one month or until the agreed quota is exhausted, whichever occurs first."
      : duration
        ? `Trial duration: ${duration} days`
        : "Trial duration and evaluation quota are agreed during assessment.";
  replaceList(byId("offer-trial-criteria"), plan.trial?.success_criteria);

  const actions = byId("offer-actions");
  if (plan.requires_assessment || !plan.registration_available) {
    const assessment = document.createElement("a");
    assessment.className = "primary-action";
    assessment.textContent = "Request plan assessment";
    assessment.href = `/apply?plan_id=${encodeURIComponent(plan.plan_id)}&journey=assessment`;
    actions.replaceChildren(assessment);
  } else {
    const monthly = document.createElement("a");
    monthly.className = "primary-action";
    monthly.textContent = `Start monthly subscription - ${money(plan.monthly_price_usd)} / month`;
    monthly.href = `${plan.registration_path}?plan_id=${encodeURIComponent(plan.plan_id)}&billing_period=monthly`;
    const annual = document.createElement("a");
    annual.className = "secondary-action";
    annual.textContent = `Start annual subscription - ${money(plan.annual_price_usd)} / year`;
    annual.href = `${plan.registration_path}?plan_id=${encodeURIComponent(plan.plan_id)}&billing_period=annual`;
    actions.replaceChildren(monthly, annual);
  }

  byId("offer-status").hidden = true;
  byId("offer-content").hidden = false;
}

async function loadOffer() {
  const planId = selectedPlanId();
  if (!planId) {
    byId("offer-status").textContent = "This plan could not be found.";
    return;
  }

  try {
    const response = await fetch(endpoint, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("catalog_unavailable");

    const payload = await response.json();
    const plan = payload.plans.find((item) => item.plan_id === planId);
    if (!plan) {
      byId("offer-title").textContent = "Plan unavailable";
      byId("offer-status").textContent = "This plan could not be found.";
      return;
    }

    render(plan);
  } catch {
    byId("offer-title").textContent = "Offer unavailable";
    byId("offer-status").textContent =
      "This offer is temporarily unavailable. Please try again later.";
  }
}

loadOffer();