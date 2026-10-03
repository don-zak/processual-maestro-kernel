"""Public boundary tests: unavailable or mismatched private admission is closed."""
import pytest
from processual_kernel.admission_port import (
    GovernanceEvidenceUnavailable, SafeAdmissionReceipt, require_admitted,
)

class StubTrustedPrivatePort:
    def __init__(self, *, enabled=True, operational=False):
        self.enabled=enabled
        self.operational=operational
    def require_admitted(self, *, entity_type,entity_id,operational=False):
        return SafeAdmissionReceipt(
            entity_type,entity_id,"a"*64,"calibration-private-v1",
            "governance-evidence-admission/v1",self.enabled,self.operational)

def test_unconfigured_port_is_never_permissive():
    with pytest.raises(GovernanceEvidenceUnavailable,match="trusted_admission_backend_unavailable"):
        require_admitted(None,entity_type="agent",entity_id="one")

def test_observation_receipt_is_not_operational_permission():
    port=StubTrustedPrivatePort()
    assert require_admitted(port,entity_type="agent",entity_id="one").data_admissible
    with pytest.raises(GovernanceEvidenceUnavailable,match="operational_calibration_not_approved"):
        require_admitted(port,entity_type="agent",entity_id="one",operational=True)

def test_invalid_or_wrong_subject_never_authorizes():
    class WrongSubject:
        def require_admitted(self,*,entity_type,entity_id,operational=False):
            return SafeAdmissionReceipt(entity_type,"other","a"*64,"x","v1",True,True)
    with pytest.raises(GovernanceEvidenceUnavailable,match="admission_subject_mismatch"):
        require_admitted(WrongSubject(),entity_type="workflow",entity_id="one",operational=True)
    with pytest.raises(GovernanceEvidenceUnavailable,match="insufficient_evidence"):
        require_admitted(StubTrustedPrivatePort(enabled=False,operational=True),
                         entity_type="agent",entity_id="one",operational=True)

def test_trusted_port_failure_never_reveals_private_error():
    class Broken:
        def require_admitted(self, **kwargs):
            raise RuntimeError("SECRET_INTERNAL_HMAC_OR_RAW_DATA")
    with pytest.raises(GovernanceEvidenceUnavailable,match="trusted_evidence_rejected") as error:
        require_admitted(Broken(),entity_type="agent",entity_id="one")
    assert "SECRET_INTERNAL_HMAC_OR_RAW_DATA" not in str(error.value)
