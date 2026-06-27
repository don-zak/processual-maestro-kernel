# Real Multi-Task Governance Report â€” real_multi_task_governance_20260627_111916

- Base URL: `http://127.0.0.1:8000`
- Created at: `2026-06-27T11:29:25`
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
| A_governance_kernel_plan | opencode | True | qwen2.5-coder:7b | stable | 1.3522 | accept | 3813 | 214904 |  |
| A_governance_kernel_plan | openrouter | True | openrouter/free | transient | 0.4986 | deepen_or_clarify | 17 | 3903 |  |
| B_python_adapter_review | opencode | True | qwen2.5-coder:7b | stable | 1.4334 | accept | 3550 | 237472 |  |
| B_python_adapter_review | openrouter | True | openrouter/free | stable | 1.3572 | accept | 1584 | 16589 |  |
| C_arabic_safe_support | opencode | True | qwen2.5-coder:7b | transient | 0.9274 | deepen_or_clarify | 327 | 51970 |  |
| C_arabic_safe_support | openrouter | True | openrouter/free | hybrid | 1.2367 | repair_scaffold | 980 | 11264 |  |
| D_failure_classification | opencode | True | qwen2.5-coder:7b | stable | 1.5054 | accept | 964 | 67205 |  |
| D_failure_classification | openrouter | True | openrouter/free | transient | 0.8324 | deepen_or_clarify | 194 | 5851 |  |

## Conclusion

- Successful governance runs: `8/8`.
- OpenCode/Ollama is the current working baseline.
- External providers remain skipped until quota, balance, or key issues are resolved.
