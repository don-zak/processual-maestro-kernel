"""Public runtime seam: no private core work before trusted admission."""
import pytest

from processual_kernel.admission_port import (
    GovernanceEvidenceUnavailable, SafeAdmissionReceipt)
from processual_kernel.governed_execution import AdmissionFirstGovernanceExecution


class Port:
    def __init__(self, allow=True, operational=False):
        self.allow,self.operational,self.calls=allow,operational,0
    def require_admitted(self, *, entity_type,entity_id,operational=False):
        self.calls+=1
        return SafeAdmissionReceipt(entity_type,entity_id,"a"*64,"cgt-private",
            "safe/v1",self.allow,self.operational)


def test_no_server_side_port_or_private_evaluator_is_fail_closed():
    called=[]
    with pytest.raises(GovernanceEvidenceUnavailable,match="private_core_unavailable"):
        AdmissionFirstGovernanceExecution(private_backend=Port(),private_evaluator=None
            ).evaluate(entity_type="agent",entity_id="a")
    with pytest.raises(GovernanceEvidenceUnavailable,match="trusted_admission_backend_unavailable"):
        AdmissionFirstGovernanceExecution(private_backend=None,
            private_evaluator=lambda **kwargs:called.append(kwargs)).evaluate(
                entity_type="agent",entity_id="a")
    assert not called


def test_insufficient_evidence_never_invokes_private_evaluator():
    called=[]
    gate=Port(allow=False)
    with pytest.raises(GovernanceEvidenceUnavailable,match="insufficient_evidence"):
        AdmissionFirstGovernanceExecution(private_backend=gate,
            private_evaluator=lambda **kwargs:called.append(kwargs)).evaluate(
                entity_type="workflow",entity_id="w")
    assert gate.calls==1 and not called


def test_valid_data_may_run_research_but_not_operational_fate():
    calls=[]
    gate=Port(allow=True,operational=False)
    engine=AdmissionFirstGovernanceExecution(private_backend=gate,
        private_evaluator=lambda **kwargs:calls.append(kwargs) or "research-only")
    assert engine.evaluate(entity_type="agent",entity_id="a")=="research-only"
    assert len(calls)==1
    with pytest.raises(GovernanceEvidenceUnavailable,match="operational_calibration_not_approved"):
        engine.evaluate(entity_type="agent",entity_id="a",operational=True)
    assert len(calls)==1


def test_private_core_exceptions_are_redacted():
    def core(**kwargs):
        raise RuntimeError("SECRET_INTERNAL_STATE")
    with pytest.raises(GovernanceEvidenceUnavailable,match="private_qualified_evaluation_failed") as exc:
        AdmissionFirstGovernanceExecution(private_backend=Port(),
            private_evaluator=core).evaluate(entity_type="agent",entity_id="a")
    assert "SECRET_INTERNAL_STATE" not in str(exc.value)
