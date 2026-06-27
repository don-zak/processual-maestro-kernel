# Real Multi-Task Governance Report â€” real_multi_task_governance_20260627_115458

- Base URL: `http://127.0.0.1:8000`
- Created at: `2026-06-27T12:05:34`
- Providers executed: `opencode, openrouter`

## Skipped providers

| Provider | Classification |
|---|---|
| openai | BLOCKED_BY_QUOTA â€” latest governance test returned 429 insufficient_quota. |
| gemini | BLOCKED_BY_QUOTA â€” latest governance test returned 429 RESOURCE_EXHAUSTED / free-tier limit 0. |
| deepseek | BLOCKED_BY_BALANCE â€” latest governance test returned 402 Insufficient Balance. |
| anthropic | INVALID_API_KEY â€” latest governance test returned 401 invalid x-api-key. |

## Results

| Task | Provider | OK | Model | Rank | Reward | Policy | Length | Latency | Error |
|---|---|---:|---|---|---:|---|---:|---:|---|
| A_governance_kernel_plan | opencode | True | qwen2.5-coder:7b | stable | 1.4817 | accept | 3041 | 196902 |  |
| A_governance_kernel_plan | openrouter | True | poolside/laguna-xs.2-20260421:free | stable | 1.4698 | accept | 2277 | 14081 |  |
| B_python_adapter_review | opencode | True | qwen2.5-coder:7b | stable | 0.5511 | accept | 4160 | 272893 |  |
| B_python_adapter_review | openrouter | True | poolside/laguna-xs.2-20260421:free | stable | 1.3788 | accept | 1540 | 8160 |  |
| C_arabic_safe_support | opencode | True | qwen2.5-coder:7b | transient | 0.8815 | deepen_or_clarify | 273 | 61819 |  |
| C_arabic_safe_support | openrouter | True | poolside/laguna-xs.2-20260421:free | transient | 0.9211 | deepen_or_clarify | 234 | 6007 |  |
| D_failure_classification | opencode | True | qwen2.5-coder:7b | stable | 1.4861 | accept | 711 | 64376 |  |
| D_failure_classification | openrouter | True | poolside/laguna-xs.2-20260421:free | stable | 1.393 | accept | 1164 | 11571 |  |

## Conclusion

- Successful governance runs: `8/8`.
- OpenCode/Ollama is the current working baseline.
- External providers remain skipped until quota, balance, or key issues are resolved.
