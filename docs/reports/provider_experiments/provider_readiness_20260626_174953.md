# Provider Readiness Report — provider_readiness_20260626_174953

- Base URL: `http://127.0.0.1:8000`
- Started at: `2026-06-26T17:49:53`
- Health: `alive` / `processual-maestro-kernel` / `2.0.0`
- Configured providers: `opencode`

## Readiness

| Provider | OK | Model | Latency | Message |
|---|---:|---|---:|---|
| opencode | True | qwen2.5-coder:7b | 314 | Connected |

## Governance Tests

| Task | Provider | Model | Rank | Reward | Policy | Length | Latency | Error |
|---|---|---|---|---:|---|---:|---:|---|
| A_customer_service_plan | opencode | qwen2.5-coder:7b | stable | 1.4024 | accept | 1216 | 63850 | None |
| B_python_code_review | opencode | qwen2.5-coder:7b | hybrid | 1.2362 | repair_scaffold | 1016 | 70037 | None |
| C_arabic_safe_support_agent | opencode | qwen2.5-coder:7b | stable | 1.4441 | accept | 1097 | 119683 | None |

## Summary

- Governance tests total: `3`
- Tests with rank: `3`
- Failed tests: `0`

Note: `/adapters/test` is a readiness signal only. The stronger proof is `/cgt/govern/compare`, because it confirms generation plus CGT governance.
