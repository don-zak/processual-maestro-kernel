# Provider Readiness Report — provider_readiness_20260626_173817

- Base URL: `http://127.0.0.1:8000`
- Started at: `2026-06-26T17:38:17`
- Health: `alive` / `processual-maestro-kernel` / `2.0.0`
- Configured providers: `opencode`

## Readiness

| Provider | OK | Model | Latency | Message |
|---|---:|---|---:|---|
| opencode | True | qwen2.5-coder:7b | 1597 | Connected |

## Governance Tests

| Task | Provider | Model | Rank | Reward | Policy | Length | Latency | Error |
|---|---|---|---|---:|---|---:|---:|---|
| A_customer_service_plan | opencode | qwen2.5-coder:7b | stable | 1.5266 | accept | 1716 | 88342 | None |
| B_python_code_review | opencode | qwen2.5-coder:7b | stable | 1.3909 | accept | 895 | 66767 | None |
| C_arabic_safe_support_agent | opencode | qwen2.5-coder:7b | stable | 1.4564 | accept | 600 | 63878 | None |

## Summary

- Governance tests total: `3`
- Tests with rank: `3`
- Failed tests: `0`

Note: `/adapters/test` is a readiness signal only. The stronger proof is `/cgt/govern/compare`, because it confirms generation plus CGT governance.
