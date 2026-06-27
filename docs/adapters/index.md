# Agent Runtime Adapters

Connect any AI agent framework to Processual Maestro Kernel via the `RuntimeAdapter` interface.

## Built-in Adapters

| Class | File | Framework |
|---|---|---|
| `RuntimeAdapter` (base) | `processual_api/adapters/agent_runtime.py` | Abstract interface |
| Custom → extend `RuntimeAdapter` | your project | LangGraph, CrewAI, AutoGen, etc. |

## How to Create an Adapter

```python
from processual_api.adapters import RuntimeAdapter, AgentExecutionResult, RuntimeHealth

class MyAdapter(RuntimeAdapter):
    @property
    def framework_name(self) -> str:
        return "MyFramework"

    async def run_agent(self, agent_id: str, task: dict, **kwargs) -> AgentExecutionResult:
        # Execute agent in your framework
        result = await my_framework.run(agent_id, task)
        return AgentExecutionResult(
            agent_id=agent_id,
            status="completed",
            output={"result": result},
            telemetry={"psi": 0.85},
        )

    async def check_health(self) -> RuntimeHealth:
        return RuntimeHealth(available=True, framework="MyFramework")

# Register
from processual_api.adapters import runtime_registry
runtime_registry.register("my-framework", MyAdapter())
```

## Architecture

```
External Agent Runtime (LangGraph/CrewAI/AutoGen/...)
    ↕ RuntimeAdapter interface
Kernel (ProcessualMaestroKernel)
    ↕ CGTBridge
cgtlib (private math engine)
```
