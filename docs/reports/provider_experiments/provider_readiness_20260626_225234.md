# Provider Readiness Report — provider_readiness_20260626_225234

- Base URL: `http://127.0.0.1:8000`
- Started at: `2026-06-26T22:52:34`
- Health: `alive` / `processual-maestro-kernel` / `2.0.0`
- Configured providers: `openai, anthropic, gemini, deepseek, opencode`

## Readiness

| Provider | OK | Model | Latency | Message |
|---|---:|---|---:|---|
| openai | True | gpt-4o-mini | 2774 | Connected |
| anthropic | False | claude-3-5-haiku-latest | 1 | Unreachable |
| gemini | False | gemini-2.0-flash | 1 | Unreachable |
| deepseek | True | deepseek-chat | 880 | Connected |
| opencode | False | qwen2.5-coder:7b | 7649 | Unreachable |

## Governance Tests

| Task | Provider | Model | Rank | Reward | Policy | Length | Latency | Error |
|---|---|---|---|---:|---|---:|---:|---|
| A_customer_service_plan | openai | gpt-4o-mini | None | None | None | 0 | 4111 | Adapter error: RateLimitError |
| A_customer_service_plan | anthropic | claude-3-5-haiku-latest | None | None | None | 0 | 1 | Adapter error: ModuleNotFoundError |
| A_customer_service_plan | gemini | gemini-2.0-flash | None | None | None | 0 | 1 | Adapter error: ModuleNotFoundError |
| A_customer_service_plan | deepseek | deepseek-chat | None | None | None | 0 | 975 | Adapter error: APIStatusError |
| A_customer_service_plan | opencode | qwen2.5-coder:7b | None | None | None | 0 | 7775 | Adapter error: APIConnectionError |
| B_python_code_review | openai | gpt-4o-mini | None | None | None | 0 | 2622 | Adapter error: RateLimitError |
| B_python_code_review | anthropic | claude-3-5-haiku-latest | None | None | None | 0 | 1 | Adapter error: ModuleNotFoundError |
| B_python_code_review | gemini | gemini-2.0-flash | None | None | None | 0 | 1 | Adapter error: ModuleNotFoundError |
| B_python_code_review | deepseek | deepseek-chat | None | None | None | 0 | 1012 | Adapter error: APIStatusError |
| B_python_code_review | opencode | qwen2.5-coder:7b | None | None | None | 0 | 7769 | Adapter error: APIConnectionError |
| C_arabic_safe_support_agent | openai | gpt-4o-mini | None | None | None | 0 | 2701 | Adapter error: RateLimitError |
| C_arabic_safe_support_agent | anthropic | claude-3-5-haiku-latest | None | None | None | 0 | 1 | Adapter error: ModuleNotFoundError |
| C_arabic_safe_support_agent | gemini | gemini-2.0-flash | None | None | None | 0 | 1 | Adapter error: ModuleNotFoundError |
| C_arabic_safe_support_agent | deepseek | deepseek-chat | None | None | None | 0 | 1007 | Adapter error: APIStatusError |
| C_arabic_safe_support_agent | opencode | qwen2.5-coder:7b | None | None | None | 0 | 7865 | Adapter error: APIConnectionError |

## Summary

- Governance tests total: `15`
- Tests with rank: `0`
- Failed tests: `15`

Note: `/adapters/test` is a readiness signal only. The stronger proof is `/cgt/govern/compare`, because it confirms generation plus CGT governance.
