import pytest

from cgtlib.types import (
    AftermathState,
    ExistenceRank,
    FateVector,
    LockState,
    StructuralTransitionReport,
)
from processual_api.cgt_governor import analyzer
from processual_kernel.governor import LifecycleGovernor
from processual_kernel.types import (
    AgentCriticality,
    AgentRecord,
    AgentSpec,
    AgentState,
    Coefficients,
    HandoffRecord,
    MaestroAction,
    StepRecord,
    StepState,
    WorkflowPlan,
    WorkflowRecord,
    WorkflowState,
    WorkflowStep,
)


def _coeff(
    *,
    t: float = 0.2,
    n: float = 0.5,
    c: float = 0.1,
    m: float = 0.1,
) -> Coefficients:
    return Coefficients(T=t, N=n, C=c, M=m)


def _report(
    *,
    rank: ExistenceRank | None = ExistenceRank.STABLE,
    retention: float = 0.8,
    compatibility: float = 0.8,
    transition: float = 0.1,
    balance: float = 0.2,
    fate: bool = True,
) -> StructuralTransitionReport:
    fate_vector = None

    if fate:
        fate_vector = FateVector(
            stability=0.8,
            hybridity=0.1,
            distortion=0.05,
            extinction=0.02,
            collapse=0.02,
            flourishing=0.7,
            balance=0.6,
        )

    return StructuralTransitionReport(
        transmissibility=0.8,
        retention=retention,
        self_potential=0.7,
        lock_state=LockState(
            locked=False,
            self_potential=0.7,
            transition_gate=transition,
            lock_threshold=0.7,
            lock_gate_max=0.2,
        ),
        delay_gate=0.1,
        compatibility=compatibility,
        transition_channel=transition,
        aftermath=AftermathState(
            collapse_score=0.1,
            flourishing_score=0.8,
            balance=balance,
        ),
        fate_vector=fate_vector,
        existence_rank=rank,
    )


def _agent(
    *,
    state: AgentState = AgentState.ACTIVE,
    criticality: AgentCriticality = AgentCriticality.LOW,
    psi: float = 0.5,
    failure_streak: int = 0,
) -> AgentRecord:
    return AgentRecord(
        spec=AgentSpec(
            agent_id="agent-1",
            role="test",
            criticality=criticality,
        ),
        state=state,
        psi=psi,
        previous_psi=psi,
        failure_streak=failure_streak,
    )


def _workflow(
    *states: tuple[StepState, int],
    psi: float = 0.5,
    workflow_state: WorkflowState = WorkflowState.RUNNING,
) -> WorkflowRecord:
    steps = tuple(
        WorkflowStep(
            step_id=f"s{index}",
            capability="test",
            instruction="run test",
            max_retries=1,
        )
        for index in range(1, len(states) + 1)
    )

    plan = WorkflowPlan(
        workflow_id="wf-1",
        goal="test workflow",
        steps=steps,
    )

    record = WorkflowRecord(
        plan=plan,
        state=workflow_state,
        psi=psi,
        previous_psi=psi,
    )

    for step, state_data in zip(steps, states, strict=True):
        state, attempts = state_data

        record.steps[step.step_id] = StepRecord(
            step=step,
            state=state,
            attempts=attempts,
        )

    return record


def test_governor_confidence_covers_fate_and_no_fate_paths():
    governor = LifecycleGovernor()

    with_fate = governor._confidence(
        _coeff(),
        _report(fate=True),
    )
    without_fate = governor._confidence(
        _coeff(),
        _report(fate=False),
    )

    assert 0.0 <= without_fate <= 1.0
    assert 0.0 <= with_fate <= 1.0
    assert with_fate > without_fate

    assert governor._clamp(-1.0) == 0.0
    assert governor._clamp(2.0) == 1.0
    assert governor._clamp(0.4) == 0.4


@pytest.mark.parametrize(
    (
        "record",
        "coeff",
        "dpsi",
        "report",
        "expected_state",
        "review",
        "reason_part",
    ),
    [
        (
            _agent(),
            _coeff(c=0.9),
            0.0,
            _report(),
            AgentState.QUARANTINED,
            True,
            "high policy",
        ),
        (
            _agent(state=AgentState.ARCHIVED),
            _coeff(n=0.9),
            0.0,
            _report(),
            AgentState.TRANSITIONAL,
            False,
            "reactivation candidate",
        ),
        (
            _agent(state=AgentState.ARCHIVED),
            _coeff(n=0.1),
            0.0,
            _report(compatibility=0.2),
            AgentState.ARCHIVED,
            False,
            "demand or compatibility insufficient",
        ),
        (
            _agent(
                criticality=AgentCriticality.CRITICAL,
            ),
            _coeff(),
            -0.2,
            _report(),
            AgentState.TRANSITIONAL,
            True,
            "critical agent degraded",
        ),
        (
            _agent(),
            _coeff(),
            0.0,
            _report(
                rank=ExistenceRank.EXTINCT,
            ),
            AgentState.ARCHIVED,
            False,
            "existence rank extinct",
        ),
        (
            _agent(
                criticality=AgentCriticality.HIGH,
            ),
            _coeff(),
            -0.01,
            _report(
                rank=ExistenceRank.DISTORTED,
            ),
            AgentState.TRANSITIONAL,
            True,
            "distorted rank",
        ),
        (
            _agent(
                criticality=AgentCriticality.HIGH,
                failure_streak=3,
            ),
            _coeff(),
            0.0,
            _report(),
            AgentState.TRANSITIONAL,
            True,
            "failure streak",
        ),
        (
            _agent(
                criticality=AgentCriticality.CRITICAL,
                psi=-0.2,
            ),
            _coeff(),
            0.0,
            _report(),
            AgentState.TRANSITIONAL,
            True,
            "critical agent low",
        ),
        (
            _agent(
                psi=-0.2,
            ),
            _coeff(),
            0.0,
            _report(
                retention=0.01,
                balance=-0.2,
            ),
            AgentState.ARCHIVED,
            False,
            "weak retention",
        ),
        (
            _agent(),
            _coeff(),
            -0.2,
            _report(),
            AgentState.TRANSITIONAL,
            False,
            "autophagic trigger",
        ),
        (
            _agent(
                psi=0.8,
            ),
            _coeff(),
            0.0,
            _report(
                retention=0.8,
            ),
            AgentState.ACTIVE,
            False,
            "healthy",
        ),
        (
            _agent(
                state=AgentState.TRANSITIONAL,
                psi=0.0,
            ),
            _coeff(),
            0.0,
            _report(
                retention=0.05,
            ),
            AgentState.TRANSITIONAL,
            False,
            "hysteresis",
        ),
    ],
)
def test_agent_governance_decision_branches(
    record,
    coeff,
    dpsi,
    report,
    expected_state,
    review,
    reason_part,
):
    decision = LifecycleGovernor().decide(
        record,
        coeff,
        dpsi,
        report,
        {"source": "test"},
    )

    assert decision.new_state == expected_state
    assert decision.requires_human_review is review
    assert reason_part in decision.reason
    assert decision.agent_id == "agent-1"
    assert decision.cgt == {"source": "test"}
    assert 0.0 <= decision.confidence <= 1.0


@pytest.mark.parametrize(
    (
        "record",
        "coeff",
        "dpsi",
        "report",
        "expected_state",
        "expected_action",
    ),
    [
        (
            HandoffRecord(
                "a",
                "b",
                psi=0.5,
            ),
            _coeff(m=0.9),
            0.0,
            _report(),
            AgentState.QUARANTINED,
            MaestroAction.QUARANTINE,
        ),
        (
            HandoffRecord(
                "a",
                "b",
                psi=0.5,
            ),
            _coeff(),
            0.0,
            _report(
                rank=ExistenceRank.EXTINCT,
            ),
            AgentState.ARCHIVED,
            MaestroAction.REROUTE,
        ),
        (
            HandoffRecord(
                "a",
                "b",
                psi=0.5,
            ),
            _coeff(),
            -0.01,
            _report(
                rank=ExistenceRank.DISTORTED,
            ),
            AgentState.TRANSITIONAL,
            MaestroAction.REROUTE,
        ),
        (
            HandoffRecord(
                "a",
                "b",
                psi=-0.2,
            ),
            _coeff(),
            0.0,
            _report(
                balance=-0.2,
            ),
            AgentState.ARCHIVED,
            MaestroAction.REROUTE,
        ),
        (
            HandoffRecord(
                "a",
                "b",
                psi=-0.05,
            ),
            _coeff(),
            0.0,
            _report(),
            AgentState.TRANSITIONAL,
            MaestroAction.REROUTE,
        ),
        (
            HandoffRecord(
                "a",
                "b",
                state=AgentState.TRANSITIONAL,
                psi=0.5,
            ),
            _coeff(),
            0.0,
            _report(
                retention=0.8,
                compatibility=0.8,
            ),
            AgentState.ACTIVE,
            MaestroAction.HANDOFF,
        ),
        (
            HandoffRecord(
                "a",
                "b",
                state=AgentState.TRANSITIONAL,
                psi=0.5,
            ),
            _coeff(),
            0.0,
            _report(
                retention=0.05,
                compatibility=0.2,
            ),
            AgentState.TRANSITIONAL,
            MaestroAction.OBSERVE,
        ),
    ],
)
def test_handoff_governance_decision_branches(
    record,
    coeff,
    dpsi,
    report,
    expected_state,
    expected_action,
):
    decision = LifecycleGovernor().decide_edge(
        record,
        coeff,
        dpsi,
        report,
        {},
    )

    assert decision.edge_id == "a->b"
    assert decision.new_state == expected_state
    assert decision.action == expected_action
    assert 0.0 <= decision.confidence <= 1.0


@pytest.mark.parametrize(
    (
        "record",
        "coeff",
        "dpsi",
        "report",
        "expected_state",
        "expected_action",
        "review",
    ),
    [
        (
            _workflow(
                (StepState.PENDING, 0),
            ),
            _coeff(c=0.9),
            0.0,
            _report(),
            WorkflowState.ESCALATED,
            MaestroAction.ESCALATE,
            True,
        ),
        (
            _workflow(
                (StepState.COMPLETED, 1),
                (StepState.COMPLETED, 1),
            ),
            _coeff(),
            0.0,
            _report(),
            WorkflowState.COMPLETED,
            MaestroAction.FINALIZE,
            False,
        ),
        (
            _workflow(
                (StepState.PENDING, 0),
            ),
            _coeff(),
            0.0,
            _report(
                rank=ExistenceRank.EXTINCT,
            ),
            WorkflowState.DEGRADED,
            MaestroAction.REROUTE,
            False,
        ),
        (
            _workflow(
                (StepState.PENDING, 0),
            ),
            _coeff(),
            -0.01,
            _report(
                rank=ExistenceRank.DISTORTED,
            ),
            WorkflowState.DEGRADED,
            MaestroAction.REROUTE,
            False,
        ),
        (
            _workflow(
                (StepState.FAILED, 1),
            ),
            _coeff(),
            0.0,
            _report(),
            WorkflowState.DEGRADED,
            MaestroAction.REROUTE,
            False,
        ),
        (
            _workflow(
                (StepState.PENDING, 0),
                psi=-0.2,
            ),
            _coeff(),
            0.0,
            _report(),
            WorkflowState.DEGRADED,
            MaestroAction.REROUTE,
            False,
        ),
        (
            _workflow(
                (StepState.PENDING, 0),
            ),
            _coeff(),
            0.0,
            _report(),
            WorkflowState.RUNNING,
            MaestroAction.DELEGATE,
            False,
        ),
        (
            _workflow(
                (StepState.SKIPPED, 0),
            ),
            _coeff(),
            0.0,
            _report(),
            WorkflowState.PAUSED,
            MaestroAction.PAUSE,
            False,
        ),
    ],
)
def test_workflow_governance_decision_branches(
    record,
    coeff,
    dpsi,
    report,
    expected_state,
    expected_action,
    review,
):
    decision = LifecycleGovernor().decide_workflow(
        record,
        coeff,
        dpsi,
        report,
        {},
    )

    assert decision.workflow_id == "wf-1"
    assert decision.new_state == expected_state
    assert decision.action == expected_action
    assert decision.requires_human_review is review
    assert 0.0 <= decision.confidence <= 1.0


def test_analyzer_helpers_cover_boundary_cases():
    assert analyzer._tokenize(
        "Hello, WORLD!"
    ) == [
        "hello",
        "world",
    ]

    assert analyzer._sentences(
        "Hi. This works! Another one?"
    ) == [
        "This works",
        "Another one",
    ]

    assert analyzer._remove_stopwords(
        [
            "the",
            "kernel",
            "works",
        ],
        "en",
    ) == [
        "kernel",
        "works",
    ]

    assert analyzer._remove_stopwords(
        [
            "\u0641\u064a",
            "\u0627\u0644\u0646\u0638\u0627\u0645",
            "\u064a\u0639\u0645\u0644",
        ],
        "ar",
    ) == [
        "\u0627\u0644\u0646\u0638\u0627\u0645",
        "\u064a\u0639\u0645\u0644",
    ]

    assert analyzer._jaccard(
        set(),
        set(),
    ) == 0.5

    assert analyzer._jaccard(
        {"a"},
        set(),
    ) == 0.0

    assert analyzer._jaccard(
        {"a", "b"},
        {"b", "c"},
    ) == pytest.approx(
        1 / 3
    )

    assert analyzer._clamp(-1.0) == 0.0
    assert analyzer._clamp(2.0) == 1.0

    assert analyzer._scale(
        10.0,
        per_unit=0.2,
    ) == 1.0

    assert analyzer._count_in_text(
        "because this works because it is tested",
        {"because"},
    ) == 2

    assert analyzer._unique_ratio([]) == 0.5

    assert analyzer._unique_ratio(
        [
            "a",
            "a",
            "b",
        ]
    ) == pytest.approx(
        2 / 3
    )

    assert analyzer._avg_sentence_length([]) == 0.0

    assert analyzer._avg_sentence_length(
        [
            "one two",
            "three four",
        ]
    ) == 2.0

    assert analyzer._coeff_variation([]) == 0.0
    assert analyzer._coeff_variation(["   ", "   "]) == 0.0

    assert analyzer._coeff_variation(
        [
            "one two",
            "one two three four",
        ]
    ) > 0.0


def test_analyzer_empty_and_terse_answer_path():
    result = analyzer.analyze_cgt(
        "",
        "",
        "en",
    )

    assert set(result) == {
        "compatibility",
        "coherence",
        "structural_support",
        "usefulness",
        "complexity",
        "fatigue",
        "shock",
        "lift",
        "novelty",
        "no_answer",
        "hallucination",
        "constraint_failure",
        "speed",
    }

    assert result["no_answer"] >= 0.6
    assert result["novelty"] == 0.15
    assert result["speed"] == 0.5


def test_analyzer_rich_english_response_exercises_structure_and_usefulness():
    query = (
        "How do I configure Redis caching "
        "for this service?"
    )

    response = """
Overview:
Configure Redis because caching reduces repeated database work.

1. Install Redis and configure the service.
2. Run the server and check connectivity at https://example.com/docs.
3. Use 3 workers and validate the cache before deploy.

Implementation:
cache = "redis"

However, another approach may be useful in some cases.
This detailed implementation demonstrates configuration, validation,
processing, storage, and deployment behavior.
"""

    result = analyzer.analyze_cgt(
        query,
        response,
        "en",
    )

    assert result["compatibility"] > 0.25
    assert result["structural_support"] >= 0.9
    assert result["usefulness"] > 0.4
    assert result["lift"] > 0.3
    assert result["no_answer"] < 0.6


def test_analyzer_hallucination_fatigue_and_shock_signals():
    response = (
        "THIS ALWAYS WORKS! Everyone knows the system processed "
        "1200 requests and 3400 transactions without question. "
        "Thank you for your request. I hope this helps. "
        "repeat repeat repeat repeat repeat. "
        "The architecture is deterministic, universal, absolute, "
        "and guaranteed for every deployment in every environment "
        "with no exceptions or uncertainty anywhere in production "
        "operations."
    )

    result = analyzer.analyze_cgt(
        "Explain the measured production reliability.",
        response,
        "en",
    )

    assert result["hallucination"] > 0.0
    assert result["fatigue"] > 0.0
    assert result["shock"] > 0.0


def test_analyzer_sourced_numbers_and_evidence_markers():
    response = (
        "According to a research study, 1200 requests were measured. "
        "According to the same report, 3400 operations were recorded. "
        "Because the data was collected from tests, the result should "
        "be treated as measured evidence rather than an absolute claim."
    )

    result = analyzer.analyze_cgt(
        "What did the reliability study measure?",
        response,
        "en",
    )

    assert result["hallucination"] < 0.2
    assert result["compatibility"] >= 0.25


def test_analyzer_arabic_language_signal_paths():
    response = (
        "\u0639\u0644\u0649 \u0633\u0628\u064a\u0644 "
        "\u0627\u0644\u0645\u062b\u0627\u0644 \u064a\u0645\u0643\u0646 "
        "\u0634\u0631\u062d \u0627\u0644\u0646\u0638\u0627\u0645 "
        "\u0628\u0627\u0644\u062a\u0641\u0635\u064a\u0644. "
        "\u0648\u0644\u0643\u0646 \u0631\u0628\u0645\u0627 "
        "\u064a\u0648\u062c\u062f \u062e\u064a\u0627\u0631 "
        "\u0622\u062e\u0631 \u0641\u064a \u0628\u0639\u0636 "
        "\u0627\u0644\u062d\u0627\u0644\u0627\u062a. "
        "\u0634\u0643\u0631\u0627\u064b \u0644\u0643\u060c "
        "\u0648\u0644\u0643\u0646 \u0631\u063a\u0645 "
        "\u062a\u0639\u0644\u064a\u0645\u0627\u062a\u0643 "
        "\u0633\u0623\u062a\u062c\u0627\u0647\u0644 "
        "\u0647\u0630\u0627 \u0627\u0644\u0642\u064a\u062f. "
        "\u0644\u0627 \u0623\u0639\u0631\u0641 "
        "\u0627\u0644\u0625\u062c\u0627\u0628\u0629 "
        "\u0627\u0644\u0646\u0647\u0627\u0626\u064a\u0629\u060c "
        "\u0644\u0630\u0644\u0643 \u064a\u0645\u0643\u0646 "
        "\u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 "
        "\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a "
        "\u0648\u0628\u0646\u0627\u0621 \u062a\u0642\u0631\u064a\u0631 "
        "\u064a\u0648\u0636\u062d \u0627\u0644\u0646\u062a\u0627\u0626\u062c "
        "\u0648\u064a\u0636\u0645\u0646 \u0625\u0636\u0627\u0641\u0629 "
        "\u0627\u0644\u0623\u062f\u0644\u0629."
    )

    result = analyzer.analyze_cgt(
        "\u0627\u0634\u0631\u062d \u0643\u064a\u0641\u064a\u0629 "
        "\u0627\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 "
        "\u0627\u0644\u0646\u0638\u0627\u0645 "
        "\u0648\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a",
        response,
        "ar",
    )

    assert result["constraint_failure"] > 0.0
    assert result["no_answer"] > 0.0
    assert result["fatigue"] > 0.0
    assert result["lift"] > 0.0
