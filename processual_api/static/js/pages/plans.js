const catalogEndpoint =
  document
    .querySelector('meta[name="maestro-plan-catalog-endpoint"]')
    ?.getAttribute("content") ?? "/billing/public-plan-journey";

const grid = document.querySelector("#plans-grid");
const status = document.querySelector("#plans-status");

function createPlanCard(plan) {
  const link = document.createElement("a");
  link.className = "plan-choice-card";
  link.href = `/offer/${encodeURIComponent(plan.plan_id)}`;
  link.dataset.planId = plan.plan_id;

  const name = document.createElement("span");
  name.className = "plan-choice-name";
  name.textContent = plan.display_name;

  const arrow = document.createElement("span");
  arrow.className = "plan-choice-arrow";
  arrow.setAttribute("aria-hidden", "true");
  arrow.textContent = "→";

  link.append(name, arrow);
  return link;
}

async function loadPlans() {
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

    if (!Array.isArray(payload.plans) || payload.plans.length === 0) {
      throw new Error("catalog_empty");
    }

    const fragment = document.createDocumentFragment();

    for (const plan of payload.plans) {
      fragment.append(createPlanCard(plan));
    }

    grid.replaceChildren(fragment);
    grid.setAttribute("aria-busy", "false");
  } catch {
    status.textContent =
      "Plans are temporarily unavailable. Please try again later.";
    grid.setAttribute("aria-busy", "false");
  }
}

loadPlans();
