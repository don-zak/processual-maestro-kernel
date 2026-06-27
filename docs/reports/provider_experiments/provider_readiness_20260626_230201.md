# Provider Readiness Report — provider_readiness_20260626_230201

- Base URL: `http://127.0.0.1:8000`
- Started at: `2026-06-26T23:02:01`
- Health: `alive` / `processual-maestro-kernel` / `2.0.0`
- Configured providers: `openai, anthropic, gemini, deepseek, opencode`

## Readiness

| Provider | OK | Model | Latency | Message |
|---|---:|---|---:|---|
| openai | True | gpt-4o-mini | 3395 | Connected |
| anthropic | False | claude-3-5-haiku-latest | 1379 | Unreachable |
| gemini | True | gemini-2.0-flash | 2547 | Connected |
| deepseek | True | deepseek-chat | 863 | Connected |
| opencode | False | qwen2.5-coder:7b | 7640 | Unreachable |

## Governance Tests

| Task | Provider | Model | Rank | Reward | Policy | Length | Latency | Error |
|---|---|---|---|---:|---|---:|---:|---|
| A_customer_service_plan | openai | gpt-4o-mini | None | None | None | 0 | 4742 | Adapter error: RateLimitError |
| A_customer_service_plan | anthropic | claude-3-5-haiku-latest | None | None | None | 0 | 759 | Adapter error: AuthenticationError |
| A_customer_service_plan | gemini | gemini-2.0-flash | None | None | None | 0 | 922 | Adapter error: ClientError |
| A_customer_service_plan | deepseek | deepseek-chat | None | None | None | 0 | 1108 | Adapter error: APIStatusError |
| A_customer_service_plan | opencode | qwen2.5-coder:7b | None | None | None | 0 | 7793 | Adapter error: APIConnectionError |
| B_python_code_review | openai | gpt-4o-mini | None | None | None | 0 | 4822 | Adapter error: RateLimitError |
| B_python_code_review | anthropic | claude-3-5-haiku-latest | None | None | None | 0 | 813 | Adapter error: AuthenticationError |
| B_python_code_review | gemini | gemini-2.0-flash | None | None | None | 0 | 1117 | Adapter error: ClientError |
| B_python_code_review | deepseek | deepseek-chat | None | None | None | 0 | 1240 | Adapter error: APIStatusError |
| B_python_code_review | opencode | qwen2.5-coder:7b | None | None | None | 0 | 7718 | Adapter error: APIConnectionError |
| C_arabic_safe_support_agent | openai | gpt-4o-mini | None | None | None | 0 | 2495 | Adapter error: RateLimitError |
| C_arabic_safe_support_agent | anthropic | claude-3-5-haiku-latest | None | None | None | 0 | 625 | Adapter error: AuthenticationError |
| C_arabic_safe_support_agent | gemini | gemini-2.0-flash | None | None | None | 0 | 970 | Adapter error: ClientError |
| C_arabic_safe_support_agent | deepseek | deepseek-chat | None | None | None | 0 | 1058 | Adapter error: APIStatusError |
| C_arabic_safe_support_agent | opencode | qwen2.5-coder:7b | None | None | None | 0 | 7786 | Adapter error: APIConnectionError |

## Summary

- Governance tests total: `15`
- Tests with rank: `0`
- Failed tests: `15`

Note: `/adapters/test` is a readiness signal only. The stronger proof is `/cgt/govern/compare`, because it confirms generation plus CGT governance.
