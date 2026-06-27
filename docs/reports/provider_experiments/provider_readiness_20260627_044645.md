# Provider Readiness Report — provider_readiness_20260627_044645

- Base URL: `http://127.0.0.1:8000`
- Started at: `2026-06-27T04:46:45`
- Health: `alive` / `processual-maestro-kernel` / `2.0.0`
- Configured providers: `openai, anthropic, gemini, deepseek, opencode`

## Readiness

| Provider | OK | Model | Latency | Message |
|---|---:|---|---:|---|
| openai | True | gpt-4o-mini | 2430 | Connected |
| anthropic | False | claude-sonnet4.6 | 1217 | Unreachable |
| gemini | True | gemini-1.5-flash | 2324 | Connected |
| deepseek | True | deepseek-chat | 876 | Connected |
| opencode | False | qwen2.5-coder:7b | 7724 | Unreachable |

## Governance Tests

| Task | Provider | Model | Rank | Reward | Policy | Length | Latency | Error |
|---|---|---|---|---:|---|---:|---:|---|
| A_customer_service_plan | openai | gpt-4o-mini | None | None | None | 0 | 2523 | Adapter error: RateLimitError: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, read the docs: https://platform.openai.com/docs/guides/error-codes/api-errors.', 'type': 'insufficient_quota', 'param': None, 'code': 'insufficient_quota'}} |
| A_customer_service_plan | anthropic | claude-sonnet4.6 | None | None | None | 0 | 646 | Adapter error: AuthenticationError: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CcT5YSEvubv7rsMbQf8HJ'} |
| A_customer_service_plan | gemini | gemini-1.5-flash | None | None | None | 0 | 908 | Adapter error: ClientError: 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1beta, or is not supported for generateContent. Call ModelService.ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}} |
| A_customer_service_plan | deepseek | deepseek-chat | None | None | None | 0 | 1011 | Adapter error: APIStatusError: Error code: 402 - {'error': {'message': 'Insufficient Balance', 'type': 'unknown_error', 'param': None, 'code': 'invalid_request_error'}} |
| A_customer_service_plan | opencode | qwen2.5-coder:7b | None | None | None | 0 | 7625 | Adapter error: APIConnectionError: Connection error. |
| B_python_code_review | openai | gpt-4o-mini | None | None | None | 0 | 2406 | Adapter error: RateLimitError: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, read the docs: https://platform.openai.com/docs/guides/error-codes/api-errors.', 'type': 'insufficient_quota', 'param': None, 'code': 'insufficient_quota'}} |
| B_python_code_review | anthropic | claude-sonnet4.6 | None | None | None | 0 | 601 | Adapter error: AuthenticationError: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CcT5ZNTkZZhwjsdF89ARs'} |
| B_python_code_review | gemini | gemini-1.5-flash | None | None | None | 0 | 909 | Adapter error: ClientError: 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1beta, or is not supported for generateContent. Call ModelService.ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}} |
| B_python_code_review | deepseek | deepseek-chat | None | None | None | 0 | 990 | Adapter error: APIStatusError: Error code: 402 - {'error': {'message': 'Insufficient Balance', 'type': 'unknown_error', 'param': None, 'code': 'invalid_request_error'}} |
| B_python_code_review | opencode | qwen2.5-coder:7b | None | None | None | 0 | 7577 | Adapter error: APIConnectionError: Connection error. |
| C_arabic_safe_support_agent | openai | gpt-4o-mini | None | None | None | 0 | 2410 | Adapter error: RateLimitError: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, read the docs: https://platform.openai.com/docs/guides/error-codes/api-errors.', 'type': 'insufficient_quota', 'param': None, 'code': 'insufficient_quota'}} |
| C_arabic_safe_support_agent | anthropic | claude-sonnet4.6 | None | None | None | 0 | 807 | Adapter error: AuthenticationError: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}, 'request_id': 'req_011CcT5aJPxTGUXbTxP5yc6x'} |
| C_arabic_safe_support_agent | gemini | gemini-1.5-flash | None | None | None | 0 | 885 | Adapter error: ClientError: 404 NOT_FOUND. {'error': {'code': 404, 'message': 'models/gemini-1.5-flash is not found for API version v1beta, or is not supported for generateContent. Call ModelService.ListModels to see the list of available models and their supported methods.', 'status': 'NOT_FOUND'}} |
| C_arabic_safe_support_agent | deepseek | deepseek-chat | None | None | None | 0 | 987 | Adapter error: APIStatusError: Error code: 402 - {'error': {'message': 'Insufficient Balance', 'type': 'unknown_error', 'param': None, 'code': 'invalid_request_error'}} |
| C_arabic_safe_support_agent | opencode | qwen2.5-coder:7b | None | None | None | 0 | 7754 | Adapter error: APIConnectionError: Connection error. |

## Summary

- Governance tests total: `15`
- Tests with rank: `0`
- Failed tests: `15`

Note: `/adapters/test` is a readiness signal only. The stronger proof is `/cgt/govern/compare`, because it confirms generation plus CGT governance.
