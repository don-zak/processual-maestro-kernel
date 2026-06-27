from __future__ import annotations

from processual_kernel import CGTBridge, ProcessualMaestroKernel
from processual_kernel.types import Coefficients


class KernelAdapter:
    def __init__(self) -> None:
        self._kernel = ProcessualMaestroKernel()
        self._bridge = CGTBridge()
        self._registrations: dict[str, str] = {}

    def register_agent(self, agent_id: str, role: str) -> None:
        from processual_kernel import AgentSpec

        self._kernel.register_agent(AgentSpec(agent_id, role, capabilities=(role,)))
        self._registrations[agent_id] = role

    def evaluate_agent_transition(
        self,
        agent_id: str,
        previous_coeff: Coefficients,
        current_coeff: Coefficients,
        previous_psi: float,
        current_psi: float,
        dpsi: float = 0.0,
        failure_streak: int = 0,
    ) -> dict:
        report = self._bridge.evaluate(
            agent_id=agent_id,
            previous_coeff=previous_coeff,
            current_coeff=current_coeff,
            previous_psi=previous_psi,
            current_psi=current_psi,
            dpsi=dpsi,
            failure_streak=failure_streak,
        )
        return self._bridge.report_to_dict(report)

    def get_kernel(self) -> ProcessualMaestroKernel:
        return self._kernel

    def get_bridge(self) -> CGTBridge:
        return self._bridge
