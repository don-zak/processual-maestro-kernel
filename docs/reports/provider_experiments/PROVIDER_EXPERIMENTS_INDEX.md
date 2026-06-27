# Provider Experiments Index

Root:
C:\Users\zaksam\Desktop\المايسترو  كرنل\processual_maestro_kernel_v2.0.0_production_ready\processual_maestro_kernel_CLEAN_LOCAL_REFERENCE_READY_FOR_DOCKER_AGENT_TESTS

## JSON reports
- provider_readiness_20260626_182545.json | 16701 bytes | 06/26/2026 18:28:51
- provider_readiness_20260626_174953.json | 11746 bytes | 06/26/2026 17:54:07
- provider_readiness_20260626_173817.json | 11721 bytes | 06/26/2026 17:41:58

## Markdown reports
- provider_readiness_20260626_182545.md | 1103 bytes | 06/26/2026 18:28:51
- provider_readiness_20260626_174953.md | 1113 bytes | 06/26/2026 17:54:07
- provider_readiness_20260626_173817.md | 1102 bytes | 06/26/2026 17:41:58

## real_multi_task_governance_20260627_090640

- JSON: data\provider_experiments\real_multi_task_governance_20260627_090640.json
- MD: docs\reports\provider_experiments\real_multi_task_governance_20260627_090640.md
- Provider executed: OpenCode/Ollama
- Successful governance runs: 4/4
- Result: OpenCode/Ollama confirmed as current real multi-task governance baseline.

## real_multi_task_governance_20260627_111916

- JSON: data\provider_experiments\real_multi_task_governance_20260627_111916.json
- MD: docs\reports\provider_experiments\real_multi_task_governance_20260627_111916.md
- Providers executed: OpenCode/Ollama + OpenRouter/free
- Governance runs: 8/8 ok=True
- Result: first successful local-vs-external-free-provider comparison.
- Main finding: OpenCode is slower but more stable; OpenRouter/free is faster but more variable.

## real_multi_task_governance_20260627_115458

- JSON: data\provider_experiments\real_multi_task_governance_20260627_115458.json
- MD: docs\reports\provider_experiments\real_multi_task_governance_20260627_115458.md
- Providers executed: OpenCode/Ollama + OpenRouter fixed free model
- OpenRouter model: poolside/laguna-xs.2-20260421:free
- Governance runs: 8/8 ok=True
- Main finding: OpenRouter fixed free model produced higher average reward and much lower latency in this run.
- Calibration note: Arabic support task remained transient/deepen_or_clarify for both providers.
