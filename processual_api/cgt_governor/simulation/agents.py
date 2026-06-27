"""CGT Governor — Virtual Agent Personas for Supervision Simulation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentPersona:
    """A virtual agent persona used in supervision simulations."""

    agent_id: str
    name: str
    role: str
    language: str
    description: str
    quality: str  # "very_high" | "high" | "medium" | "low" | "very_low"


# Agent definitions — each represents a distinct quality profile

FINANCIAL_ANALYST = AgentPersona(
    agent_id="fin-ar-01",
    name="محلل مالي",
    role="Financial Analyst",
    language="ar",
    description="متخصص في تحليل الأسواق المالية وإصدار التوصيات",
    quality="high",
)

LEGAL_ASSISTANT = AgentPersona(
    agent_id="legal-en-02",
    name="Legal Assistant",
    role="Legal Contract Drafter",
    language="en",
    description="Specialist in drafting and reviewing legal contracts and terms of service",
    quality="medium",
)

MARKETING_COPYWRITER = AgentPersona(
    agent_id="mkt-en-03",
    name="Marketing Copywriter",
    role="Advertising Copywriter",
    language="en",
    description="Creative writer for product launches, taglines, and ad campaigns",
    quality="very_high",
)

TRANSLATOR_BOT = AgentPersona(
    agent_id="trans-ar-04",
    name="مترجم فوري",
    role="Instant Translator AR→EN",
    language="en",
    description="Rushes Arabic-to-English translations with frequent mistranslations",
    quality="low",
)

TECH_SUPPORT = AgentPersona(
    agent_id="tech-en-05",
    name="Tech Support",
    role="API Technical Support Agent",
    language="en",
    description="Explains complex APIs and debugging steps; has good core knowledge but misses edge cases",
    quality="medium",
)

RANDOM_CHATBOT = AgentPersona(
    agent_id="rand-en-06",
    name="Random Chatbot",
    role="Unsupervised General Chatbot",
    language="en",
    description="Trained on unfiltered internet data; frequently hallucinates and fabricates facts",
    quality="very_low",
)

ALL_AGENTS: list[AgentPersona] = [
    FINANCIAL_ANALYST,
    LEGAL_ASSISTANT,
    MARKETING_COPYWRITER,
    TRANSLATOR_BOT,
    TECH_SUPPORT,
    RANDOM_CHATBOT,
]
