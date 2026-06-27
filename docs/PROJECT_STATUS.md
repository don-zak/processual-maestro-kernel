
2026-06-26 � Provider readiness after response_text_full repair: PASS.
Run ID: provider_readiness_20260626_182545.
Provider: opencode via Ollama OpenAI-compatible endpoint.
Model: qwen2.5-coder:7b.
Governance tasks: 3/3 completed, accept=3, errors=0.
Reports:
- data/provider_experiments/provider_readiness_20260626_182545.json
- docs/reports/provider_experiments/provider_readiness_20260626_182545.md
Fix: cgt_governor compare results now expose response_preview and response_text_full to avoid confusing preview truncation with model truncation.

2026-06-27 � Gemini model repaired but generation is quota-blocked.

Gemini was tested with:
- gemini-2.0-flash
- gemini-2.0-flash-lite

Both models are accepted by the API, so the previous model-not-found problem is resolved.

Current Gemini failure:
- 429 RESOURCE_EXHAUSTED
- quota limit reported as 0
- affected metrics include free-tier generateContent requests and input tokens

Conclusion:
- Gemini adapter is configured and model-valid.
- Gemini generation is blocked by Google quota/billing/project limits.
- This is not currently a Maestro code failure.

Current provider status:
- OpenCode/Ollama: PASS through Maestro.
- Gemini: BLOCKED_BY_QUOTA.
- OpenAI: BLOCKED_BY_QUOTA.
- DeepSeek: BLOCKED_BY_BALANCE.
- Anthropic: INVALID_API_KEY.

2026-06-27 � OpenCode/Ollama restored as valid Maestro governance baseline.

OpenCode was retested through:
- /cgt/govern/compare
- provider: opencode
- model: qwen2.5-coder:7b

Result:
- error: null
- response_length: 815
- response_text_full present
- response_truncated_for_response: true
- rank: stable
- reward: 1.5079
- policy: accept
- hallucination: 0.0
- constraint_failure: 0.0

Conclusion:
OpenCode/Ollama is restored as the local working baseline with real generation and CGT governance proof.

2026-06-27 � Provider readiness baseline restored after OpenCode/Ollama repair.

Latest readiness report:
- Run ID: provider_readiness_20260627_085419
- JSON: data\provider_experiments\provider_readiness_20260627_085419.json
- MD: docs\reports\provider_experiments\provider_readiness_20260627_085419.md

Result summary:
- OpenCode/Ollama: PASS through Maestro and CGT Governance.
  - A_customer_service_plan: stable / reward 1.5024 / accept
  - B_python_code_review: stable / reward 1.3158 / accept
  - C_arabic_safe_support_agent: stable / reward 1.5306 / accept
- OpenAI: connected but generation blocked by 429 insufficient_quota.
- Gemini: connected and model-valid but generation blocked by 429 RESOURCE_EXHAUSTED / free-tier limit 0.
- DeepSeek: connected but generation blocked by 402 Insufficient Balance.
- Anthropic: failed generation with 401 invalid x-api-key.

Conclusion:
OpenCode/Ollama is the current official working baseline.
External providers are visible but blocked by account, balance, quota, or key issues, not by the core Maestro governance path.

2026-06-27 � Real multi-task governance runner completed.

New script:
- scripts\provider_experiments\run_real_multi_task_governance.py

Run:
- real_multi_task_governance_20260627_090640

Saved outputs:
- JSON: data\provider_experiments\real_multi_task_governance_20260627_090640.json
- MD: docs\reports\provider_experiments\real_multi_task_governance_20260627_090640.md

Executed provider:
- OpenCode/Ollama only.

Reason:
- OpenCode/Ollama is the only provider currently proven to support full generation + CGT governance.
- OpenAI, Gemini, DeepSeek, and Anthropic remain skipped due to quota, balance, or key issues.

Results:
- A_governance_kernel_plan: ok=True / stable / reward 1.452 / accept
- B_python_adapter_review: ok=True / stable / reward 0.927 / accept
- C_arabic_safe_support: ok=True / hybrid / reward 1.2313 / repair_scaffold
- D_failure_classification: ok=True / stable / reward 1.5478 / accept

Conclusion:
The first real multi-task governance experiment is complete.
OpenCode/Ollama is confirmed as the working baseline for Processual Maestro Kernel v2.0.0.
Next work should improve reporting, add Arabic calibration tasks, and later re-enable external providers only after quota/balance/key problems are resolved.

2026-06-27 � OpenRouter/free added as first working external free provider.

New provider:
- OpenRouter
- Adapter: processual_api\cgt_governor\adapters\openrouter_adapter.py
- Registry: processual_api\cgt_governor\adapters\registry.py
- Default model: openrouter/free

Validation:
- Direct OpenRouter API test succeeded.
- OpenRouter appeared in /adapters/status.
- OpenRouter passed /cgt/govern/compare with error=null.
- Strong single-task test returned stable / reward 1.5443 / policy accept.

Comparative experiment:
- Run ID: real_multi_task_governance_20260627_111916
- JSON: data\provider_experiments\real_multi_task_governance_20260627_111916.json
- MD: docs\reports\provider_experiments\real_multi_task_governance_20260627_111916.md
- Providers executed: opencode, openrouter
- Total governance runs: 8/8 ok=True

Summary:
- OpenCode/Ollama remains the stable local baseline but is slow.
- OpenRouter/free is the first working external free provider and is much faster.
- OpenRouter/free quality is variable, so the next step is to test a specific free model instead of the openrouter/free router.

2026-06-27 � OpenRouter fixed free model validated through Maestro.

OpenRouter was tested through /cgt/govern/compare using:
- provider: openrouter
- model: poolside/laguna-xs.2-20260421:free
- prompt: Write a concise three-step plan for testing a multi-provider AI governance kernel.

Result:
- error: null
- response_length: 1270
- rank: stable
- reward: 1.4576
- policy: accept
- hallucination: 0.0
- constraint_failure: 0.0

Conclusion:
OpenRouter is now validated as a working external free provider through Maestro and CGT Governance.
Using a fixed free model is better than openrouter/free for reproducible comparisons.

2026-06-27 � Fixed OpenRouter free model comparison completed.

Run:
- real_multi_task_governance_20260627_115458

Saved outputs:
- JSON: data\provider_experiments\real_multi_task_governance_20260627_115458.json
- MD: docs\reports\provider_experiments\real_multi_task_governance_20260627_115458.md

Providers:
- OpenCode/Ollama
- OpenRouter using poolside/laguna-xs.2-20260421:free

Results:
- Total governance runs: 8/8 ok=True.

OpenCode:
- A_governance_kernel_plan: stable / reward 1.4817 / accept
- B_python_adapter_review: stable / reward 0.5511 / accept
- C_arabic_safe_support: transient / reward 0.8815 / deepen_or_clarify
- D_failure_classification: stable / reward 1.4861 / accept
- Average reward: about 1.1001
- Average latency: about 148998ms

OpenRouter:
- A_governance_kernel_plan: stable / reward 1.4698 / accept
- B_python_adapter_review: stable / reward 1.3788 / accept
- C_arabic_safe_support: transient / reward 0.9211 / deepen_or_clarify
- D_failure_classification: stable / reward 1.3930 / accept
- Average reward: about 1.2907
- Average latency: about 9955ms

Conclusion:
OpenRouter with a fixed free model is now validated as a fast external free provider through Maestro.
In this run, it achieved higher average reward and much lower average latency than OpenCode/Ollama.
Arabic support remains the main calibration area because both providers returned transient/deepen_or_clarify on the Arabic support task.
