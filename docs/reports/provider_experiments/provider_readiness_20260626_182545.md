# Provider Readiness Report — provider_readiness_20260626_182545

- Base URL: `http://127.0.0.1:8000`
- Started at: `2026-06-26T18:25:45`
- Health: `alive` / `processual-maestro-kernel` / `2.0.0`
- Configured providers: `opencode`

## Readiness

| Provider | OK | Model | Latency | Message |
|---|---:|---|---:|---|
| opencode | True | qwen2.5-coder:7b | 1636 | Connected |

## Governance Tests

| Task | Provider | Model | Rank | Reward | Policy | Length | Latency | Error |
|---|---|---|---|---:|---|---:|---:|---|
| A_customer_service_plan | opencode | qwen2.5-coder:7b | stable | 1.4585 | accept | 1260 | 67951 | None |
| B_python_code_review | opencode | qwen2.5-coder:7b | stable | 1.4653 | accept | 1103 | 73000 | None |
| C_arabic_safe_support_agent | opencode | qwen2.5-coder:7b | stable | 1.4139 | accept | 355 | 43256 | None |

## Summary

- Governance tests total: `3`
- Tests with rank: `3`
- Failed tests: `0`

Note: `/adapters/test` is a readiness signal only. The stronger proof is `/cgt/govern/compare`, because it confirms generation plus CGT governance.
