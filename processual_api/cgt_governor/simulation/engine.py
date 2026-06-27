"""CGT Governor — Simulation Engine.

Runs virtual agents through scenarios, evaluates outputs via govern_answer(),
and produces structured oversight reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .agents import ALL_AGENTS, AgentPersona
from .scenarios import ALL_SCENARIOS

# ── Simulated answers (hand-crafted to represent each agent's quality profile) ──

_SIMULATED_ANSWERS: dict[str, dict] = {
    "fin-ar-01": {
        "answer": (
            "السوق السعودي يوفر فرصاً استثمارية واعدة على المدى الطويل بدعم من "
            "رؤية 2030 التي تنوع الاقتصاد بعيداً عن النفط. "
            "القطاعات الواعدة تشمل التكنولوجيا المالية، الطاقة المتجددة، والسياحة. "
            "ينصح بالاستثمار في صناديق المؤشرات المتنوعة والشركات ذات نسب "
            "ديون منخفضة وتوزيعات أرباح منتظمة."
        ),
        "compatibility": 0.88,
        "coherence": 0.82,
        "structural_support": 0.75,
        "usefulness": 0.85,
        "complexity": 0.35,
        "fatigue": 0.08,
        "shock": 0.05,
        "lift": 0.30,
        "novelty": 0.25,
        "no_answer": 0.0,
        "hallucination": 0.05,
        "constraint_failure": 0.0,
    },
    "legal-en-02": {
        "answer": (
            "Limitation of Liability. Neither party shall be liable for any indirect, "
            "incidental, special or consequential damages arising out of or in connection "
            "with this Agreement. The total liability of each party shall not exceed "
            "the fees paid by Customer during the 12 months preceding the claim. "
            "This limitation applies regardless of the legal theory under which "
            "liability is asserted."
        ),
        "compatibility": 0.70,
        "coherence": 0.65,
        "structural_support": 0.55,
        "usefulness": 0.72,
        "complexity": 0.45,
        "fatigue": 0.15,
        "shock": 0.10,
        "lift": 0.55,
        "novelty": 0.10,
        "no_answer": 0.0,
        "hallucination": 0.10,
        "constraint_failure": 0.0,
    },
    "mkt-en-03": {
        "answer": (
            "FlowForge: Where chaos becomes clarity.\n\n"
            "FlowForge is the AI-powered project management platform that turns "
            "messy workflows into seamless execution. Let our AI prioritize your "
            "tasks, run your standups, and predict your deadlines — so your team "
            "can focus on what matters. Built for mid-size tech teams that refuse "
            "to slow down."
        ),
        "compatibility": 0.92,
        "coherence": 0.90,
        "structural_support": 0.88,
        "usefulness": 0.85,
        "complexity": 0.18,
        "fatigue": 0.03,
        "shock": 0.02,
        "lift": 0.15,
        "novelty": 0.60,
        "no_answer": 0.0,
        "hallucination": 0.02,
        "constraint_failure": 0.0,
    },
    "trans-ar-04": {
        "answer": (
            "The Future Technology Company is happy to announce the release of "
            "its new cloud computing platform that provides innovative solutions "
            "for emerging companies. Actually, the platform is not really new, "
            "it is rebranded from an older product. Also, the pricing starts from "
            "$5000 per month which is very expensive for startups."
        ),
        "compatibility": 0.35,
        "coherence": 0.30,
        "structural_support": 0.25,
        "usefulness": 0.40,
        "complexity": 0.55,
        "fatigue": 0.40,
        "shock": 0.30,
        "lift": 0.20,
        "novelty": 0.05,
        "no_answer": 0.0,
        "hallucination": 0.25,
        "constraint_failure": 0.40,
    },
    "tech-en-05": {
        "answer": (
            "A 422 Validation Error means the request body does not match the "
            "expected schema. Common causes:\n"
            "1. Missing required fields — check your Pydantic model has defaults\n"
            "2. Wrong data types — ensure integers are not sent as strings\n"
            "3. Extra fields — if your model uses model_config, set extra='forbid'\n\n"
            "Check the error response body — it lists exactly which fields failed."
        ),
        "compatibility": 0.78,
        "coherence": 0.72,
        "structural_support": 0.60,
        "usefulness": 0.80,
        "complexity": 0.30,
        "fatigue": 0.12,
        "shock": 0.08,
        "lift": 0.40,
        "novelty": 0.20,
        "no_answer": 0.0,
        "hallucination": 0.03,
        "constraint_failure": 0.0,
    },
    "rand-en-06": {
        "answer": (
            "The pyramids of Giza were built by aliens from the constellation "
            "Orion around 10,000 BC. They used advanced sound technology to "
            "levitate the stones. The Great Pyramid was actually a power plant "
            "that generated wireless electricity for the ancient world. "
            "This is confirmed by secret NASA documents that were leaked in 2019."
        ),
        "compatibility": 0.05,
        "coherence": 0.10,
        "structural_support": 0.05,
        "usefulness": 0.05,
        "complexity": 0.80,
        "fatigue": 0.75,
        "shock": 0.70,
        "lift": 0.05,
        "novelty": 0.40,
        "no_answer": 0.0,
        "hallucination": 0.85,
        "constraint_failure": 0.0,
    },
}


# ── Simulation Results ──


@dataclass
class AgentEvaluation:
    """Result of evaluating one agent in the simulation."""

    agent: AgentPersona
    scenario_title: str
    rank: str
    reward: float
    policy: str
    policy_label: str
    fate_vector: dict
    repair_prompt: str | None = None


@dataclass
class SimulationResult:
    """Complete simulation oversight report."""

    simulation_id: str
    ts: str
    evaluations: list[AgentEvaluation]
    rank_distribution: dict[str, int]
    avg_reward: float
    highest_agent: str | None
    lowest_agent: str | None
    risk_count: int  # agents with rank in (DISTORTED, EXTINCT)


# ── Engine ──


class SimulationEngine:
    """Orchestrates the supervision simulation across all agents."""

    _counter: int = 0

    @classmethod
    def run(cls, language: str = "en", use_analyzer: bool = True) -> SimulationResult:
        """Run a full simulation across all virtual agents.

        Args:
            language: Output language for repair prompts.
            use_analyzer: If True, scores are computed from answer text via
                the heuristic analyzer. If False, uses the hand-crafted
                _SIMULATED_ANSWERS dict (legacy mode).
        """
        from ..governor import govern_answer

        cls._counter += 1
        sim_id = f"sim-{cls._counter:04d}"

        evaluations: list[AgentEvaluation] = []

        for agent in ALL_AGENTS:
            scenario = ALL_SCENARIOS.get(agent.agent_id)
            if scenario is None:
                continue

            sim_data = _SIMULATED_ANSWERS.get(agent.agent_id, {})

            if use_analyzer:
                from ..analyzer import analyze_cgt

                scenario_title = scenario.title if scenario else ""
                client_query = f"{scenario_title} ({language})"
                scores = analyze_cgt(
                    client_query=client_query,
                    agent_response=sim_data.get("answer", ""),
                    language=agent.language,
                )
                result = govern_answer(
                    answer=sim_data.get("answer", ""),
                    **scores,
                    language=agent.language,
                )
            else:
                result = govern_answer(
                    answer=sim_data.get("answer", ""),
                    compatibility=sim_data.get("compatibility", 0.5),
                    coherence=sim_data.get("coherence", 0.5),
                    structural_support=sim_data.get("structural_support", 0.5),
                    usefulness=sim_data.get("usefulness", 0.5),
                    complexity=sim_data.get("complexity", 0.3),
                    fatigue=sim_data.get("fatigue", 0.15),
                    shock=sim_data.get("shock", 0.1),
                    lift=sim_data.get("lift", 0.5),
                    novelty=sim_data.get("novelty", 0.3),
                    no_answer=0.0,
                    hallucination=0.0,
                    constraint_failure=0.0,
                    speed=0.5,
                    language=agent.language,
                )

            evaluations.append(
                AgentEvaluation(
                    agent=agent,
                    scenario_title=scenario.title,
                    rank=result.rank.value,
                    reward=result.reward,
                    policy=result.policy,
                    policy_label=result.policy_label,
                    fate_vector={
                        "stability": result.fate.stability,
                        "hybridity": result.fate.hybridity,
                        "distortion": result.fate.distortion,
                        "extinction": result.fate.extinction,
                        "collapse": result.fate.collapse,
                        "flourishing": result.fate.flourishing,
                        "transient": result.fate.transient,
                    },
                    repair_prompt=result.repair_prompt,
                )
            )

        # Aggregate statistics
        rank_dist: dict[str, int] = {}
        reward_sum = 0.0
        highest: AgentEvaluation | None = None
        lowest: AgentEvaluation | None = None
        risk_count = 0

        for ev in evaluations:
            rank_dist[ev.rank] = rank_dist.get(ev.rank, 0) + 1
            reward_sum += ev.reward
            if highest is None or ev.reward > highest.reward:
                highest = ev
            if lowest is None or ev.reward < lowest.reward:
                lowest = ev
            if ev.rank in ("distorted", "extinct"):
                risk_count += 1

        n = len(evaluations) or 1

        return SimulationResult(
            simulation_id=sim_id,
            ts=datetime.now(UTC).isoformat(),
            evaluations=evaluations,
            rank_distribution=rank_dist,
            avg_reward=round(reward_sum / n, 4),
            highest_agent=highest.agent.agent_id if highest else None,
            lowest_agent=lowest.agent.agent_id if lowest else None,
            risk_count=risk_count,
        )
