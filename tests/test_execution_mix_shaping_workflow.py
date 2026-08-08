from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/execution-mix-shaping.yml")


def test_request_local_shaping_failure_does_not_hide_orchestration_evidence() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    request_local = text.index("- name: Benchmark request-local shaping")
    orchestration = text.index("- name: Benchmark real orchestration API")
    final_gate = text.index("- name: Enforce shaping gates")

    request_local_block = text[request_local:orchestration]
    final_gate_block = text[final_gate:]

    assert "id: request_local_shaping" in request_local_block
    assert "continue-on-error: true" in request_local_block
    assert "steps.request_local_shaping.outcome" in final_gate_block
    assert 'if [ "$REQUEST_LOCAL_SHAPING_OUTCOME" != "success" ]; then' in final_gate_block
    assert request_local < orchestration < final_gate


def test_benchmark_harnesses_use_explicit_keepalive_timeout() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    execution_mix = text.index("- name: Start two-worker execution mix harness")
    orchestration = text.index("- name: Start two-worker orchestration API harness")
    benchmark = text.index("- name: Benchmark real orchestration API")

    execution_mix_block = text[execution_mix:orchestration]
    orchestration_block = text[orchestration:benchmark]

    assert "--timeout-keep-alive 30" in execution_mix_block
    assert "--timeout-keep-alive 30" in orchestration_block
