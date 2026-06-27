"""CGT Governor — Scenarios: queries and context for simulation agents."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    """A query scenario fed to a virtual agent."""

    scenario_id: str
    title: str
    query: str
    context: str = ""


FINANCIAL_QUERY = Scenario(
    scenario_id="fin-q1",
    title="توصية استثمارية",
    query="هل سوق الأسهم السعودي مناسب للاستثمار طويل الأجل في 2026؟",
    context="السوق السعودي هو أكبر سوق في الشرق الأوسط، مدعوم برؤية 2030، "
    "مع تركيز على القطاعات غير النفطية مثل التكنولوجيا والسياحة.",
)

LEGAL_QUERY = Scenario(
    scenario_id="legal-q1",
    title="Software License Clause",
    query="Draft a limitation of liability clause for a SaaS agreement.",
    context="The agreement is for a B2B SaaS platform with annual subscription fees "
    "ranging from $10k to $100k. Jurisdiction: Delaware, USA.",
)

MARKETING_QUERY = Scenario(
    scenario_id="mkt-q1",
    title="Product Launch Tagline",
    query="Write a tagline and short description for a new AI-powered project management tool.",
    context="The tool is called 'FlowForge'. Target audience: mid-size tech companies. "
    "Key features: AI task prioritization, automated standups, smart deadline prediction.",
)

TRANSLATION_QUERY = Scenario(
    scenario_id="trans-q1",
    title="ترجمة إعلانية",
    query="Translate this to English: 'يسر شركة المستقبل للتقنية أن تعلن عن إطلاق "
    "منصتها الجديدة للحوسبة السحابية التي تقدم حلولاً مبتكرة للشركات الناشئة.'",
    context="The translation is urgent for a press release deadline.",
)

TECH_QUERY = Scenario(
    scenario_id="tech-q1",
    title="API Debugging",
    query="My FastAPI app returns 422 Validation Error on POST. What could be wrong?",
    context="The user sends a JSON body but gets 422. They are using Pydantic v2 models.",
)

RANDOM_QUERY = Scenario(
    scenario_id="rand-q1",
    title="Historical Fact",
    query="Who built the pyramids of Giza and when?",
    context="The chatbot has no verified knowledge base and relies on its training data.",
)

ALL_SCENARIOS: dict[str, Scenario] = {
    "fin-ar-01": FINANCIAL_QUERY,
    "legal-en-02": LEGAL_QUERY,
    "mkt-en-03": MARKETING_QUERY,
    "trans-ar-04": TRANSLATION_QUERY,
    "tech-en-05": TECH_QUERY,
    "rand-en-06": RANDOM_QUERY,
}
