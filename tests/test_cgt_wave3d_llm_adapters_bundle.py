from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from processual_api.cgt_governor.adapters.anthropic_adapter import AnthropicAdapter
from processual_api.cgt_governor.adapters.deepseek_adapter import DeepSeekAdapter
from processual_api.cgt_governor.adapters.gemini_adapter import GeminiAdapter
from processual_api.cgt_governor.adapters.openai_adapter import OpenAIAdapter
from processual_api.cgt_governor.adapters.openai_compatible_adapter import GenericOpenAICompatibleAdapter
from processual_api.cgt_governor.adapters.opencode_adapter import OpenCodeAdapter
from processual_api.cgt_governor.adapters.openrouter_adapter import OpenRouterAdapter


class _Models:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.list_calls = 0

    async def list(self):
        self.list_calls += 1
        if self.fail:
            raise RuntimeError("offline")
        return []


class _Completions:
    def __init__(self, text: str = "answer") -> None:
        self.text = text
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.text))]
        )


class _OpenAIClient:
    instances: list["_OpenAIClient"] = []
    fail_models = False
    response_text = "answer"

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.models = _Models(fail=self.fail_models)
        self.chat = SimpleNamespace(completions=_Completions(self.response_text))
        type(self).instances.append(self)


@pytest.fixture(autouse=True)
def _reset_fake_client() -> None:
    _OpenAIClient.instances.clear()
    _OpenAIClient.fail_models = False
    _OpenAIClient.response_text = "answer"


def _install_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=_OpenAIClient))


@pytest.mark.asyncio
async def test_openai_adapter_configuration_availability_and_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = OpenAIAdapter()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_DEFAULT_MODEL", raising=False)

    assert adapter.provider_name == "OpenAI"
    assert adapter.default_model == "gpt-4o"
    assert adapter.is_configured() is False
    assert await adapter.is_available() is False
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await adapter.generate("hello")

    monkeypatch.setenv("OPENAI_API_KEY", "real-key")
    monkeypatch.setenv("OPENAI_DEFAULT_MODEL", "default-model")
    _install_openai(monkeypatch)

    assert adapter.is_configured() is True
    assert adapter.default_model == "default-model"
    assert await adapter.is_available() is True

    result = await adapter.generate(
        "hello",
        system_prompt="system",
        model="override-model",
        temperature=0.2,
        max_tokens=99,
    )
    assert result == "answer"
    client = _OpenAIClient.instances[-1]
    assert client.kwargs == {"api_key": "real-key"}
    call = client.chat.completions.calls[-1]
    assert call["model"] == "override-model"
    assert call["temperature"] == 0.2
    assert call["max_tokens"] == 99
    assert call["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "hello"},
    ]


@pytest.mark.asyncio
async def test_openai_adapter_availability_failure_and_empty_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "real-key")
    _install_openai(monkeypatch)
    adapter = OpenAIAdapter()

    _OpenAIClient.fail_models = True
    assert await adapter.is_available() is False
    _OpenAIClient.fail_models = False
    _OpenAIClient.response_text = ""
    assert await adapter.generate("hello") == ""


@pytest.mark.asyncio
async def test_deepseek_adapter_all_major_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = DeepSeekAdapter()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_DEFAULT_MODEL", raising=False)

    assert adapter.provider_name == "DeepSeek"
    assert adapter.default_model == "deepseek-chat"
    assert adapter.is_configured() is False
    assert await adapter.is_available() is False
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        await adapter.generate("p")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "real-ds-key")
    monkeypatch.setenv("DEEPSEEK_DEFAULT_MODEL", "deepseek-custom")
    _install_openai(monkeypatch)
    assert await adapter.is_available() is True
    result = await adapter.generate("p", system_prompt="s")
    assert result == "answer"
    client = _OpenAIClient.instances[-1]
    assert client.kwargs["base_url"] == DeepSeekAdapter.BASE_URL
    assert client.chat.completions.calls[-1]["model"] == "deepseek-custom"

    _OpenAIClient.fail_models = True
    assert await adapter.is_available() is False


@pytest.mark.asyncio
async def test_opencode_adapter_defaults_explicit_endpoint_and_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = OpenCodeAdapter()
    for name in ("OPENCODE_API_URL", "OPENCODE_API_KEY", "OPENCODE_DEFAULT_MODEL"):
        monkeypatch.delenv(name, raising=False)

    assert adapter.provider_name == "OpenCode"
    assert adapter.base_url == "http://localhost:11434/v1"
    assert adapter.api_key == ""
    assert adapter.default_model == "llama3"
    assert adapter.is_configured() is True
    assert await adapter.is_available() is False

    monkeypatch.setenv("OPENCODE_API_URL", "http://example.test/v1")
    monkeypatch.setenv("OPENCODE_API_KEY", "key")
    monkeypatch.setenv("OPENCODE_DEFAULT_MODEL", "local-model")
    _install_openai(monkeypatch)
    assert await adapter.is_available() is True
    assert await adapter.generate("p") == "answer"
    client = _OpenAIClient.instances[-1]
    assert client.kwargs == {"api_key": "key", "base_url": "http://example.test/v1"}
    assert client.chat.completions.calls[-1]["model"] == "local-model"

    _OpenAIClient.fail_models = True
    assert await adapter.is_available() is False


@pytest.mark.asyncio
async def test_generic_openai_compatible_all_major_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = GenericOpenAICompatibleAdapter()
    for name in ("GENERIC_OPENAI_API_URL", "GENERIC_OPENAI_API_KEY", "GENERIC_OPENAI_DEFAULT_MODEL"):
        monkeypatch.delenv(name, raising=False)

    assert adapter.provider_name == "Generic OpenAI Compatible"
    assert adapter.base_url == ""
    assert adapter.api_key == ""
    assert adapter.default_model == "gpt-compatible"
    assert adapter.is_configured() is False
    assert await adapter.is_available() is False
    with pytest.raises(RuntimeError, match="GENERIC_OPENAI_API_URL"):
        await adapter.generate("p")

    monkeypatch.setenv("GENERIC_OPENAI_API_URL", " http://generic.test/v1 ")
    monkeypatch.setenv("GENERIC_OPENAI_API_KEY", " key ")
    monkeypatch.setenv("GENERIC_OPENAI_DEFAULT_MODEL", "generic-model")
    _install_openai(monkeypatch)
    assert adapter.base_url == "http://generic.test/v1"
    assert adapter.api_key == "key"
    assert await adapter.is_available() is True
    assert await adapter.generate("p", system_prompt="s", temperature=0.1, max_tokens=7) == "answer"
    call = _OpenAIClient.instances[-1].chat.completions.calls[-1]
    assert call["messages"][0] == {"role": "system", "content": "s"}
    assert call["model"] == "generic-model"

    _OpenAIClient.fail_models = True
    assert await adapter.is_available() is False


@pytest.mark.asyncio
async def test_openrouter_configuration_headers_availability_and_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = OpenRouterAdapter()
    for name in (
        "OPENROUTER_API_KEY",
        "OPENROUTER_API_URL",
        "OPENROUTER_DEFAULT_MODEL",
        "OPENROUTER_HTTP_REFERER",
        "OPENROUTER_APP_TITLE",
    ):
        monkeypatch.delenv(name, raising=False)

    assert adapter.provider_name == "OpenRouter"
    assert adapter.default_model == "openrouter/free"
    assert adapter.base_url == "https://openrouter.ai/api/v1"
    assert adapter.is_configured() is False
    assert await adapter.is_available() is False
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        await adapter.generate("p")

    monkeypatch.setenv("OPENROUTER_API_KEY", "router-key")
    monkeypatch.setenv("OPENROUTER_API_URL", "https://router.test/v1")
    monkeypatch.setenv("OPENROUTER_DEFAULT_MODEL", "router-model")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://app.test")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "Test App")
    _install_openai(monkeypatch)

    assert adapter.is_configured() is True
    assert adapter._default_headers() == {"HTTP-Referer": "https://app.test", "X-Title": "Test App"}
    assert await adapter.is_available() is True
    assert await adapter.generate("p", system_prompt="s") == "answer"
    client = _OpenAIClient.instances[-1]
    assert client.kwargs["default_headers"]["X-Title"] == "Test App"
    assert client.chat.completions.calls[-1]["model"] == "router-model"

    _OpenAIClient.fail_models = True
    assert await adapter.is_available() is False


class _AnthropicClient:
    instances: list["_AnthropicClient"] = []
    fail_ping = False
    empty_content = False

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)
        type(self).instances.append(self)

    async def ping(self) -> None:
        if self.fail_ping:
            raise RuntimeError("offline")

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        content = [] if self.empty_content else [SimpleNamespace(text="anthropic-answer")]
        return SimpleNamespace(content=content)


@pytest.mark.asyncio
async def test_anthropic_adapter_configuration_availability_and_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = AnthropicAdapter()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_DEFAULT_MODEL", raising=False)
    assert adapter.provider_name == "Anthropic"
    assert adapter.default_model == "claude-3-5-haiku-latest"
    assert adapter.is_configured() is False
    assert await adapter.is_available() is False
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        await adapter.generate("p")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "anth-key")
    monkeypatch.setenv("ANTHROPIC_DEFAULT_MODEL", "claude-test")
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(AsyncAnthropic=_AnthropicClient))
    _AnthropicClient.fail_ping = False
    assert await adapter.is_available() is True
    assert await adapter.generate("p", system_prompt="s", temperature=0.3, max_tokens=12) == "anthropic-answer"
    call = _AnthropicClient.instances[-1].calls[-1]
    assert call["model"] == "claude-test"
    assert call["system"] == "s"
    assert call["messages"] == [{"role": "user", "content": "p"}]

    _AnthropicClient.fail_ping = True
    assert await adapter.is_available() is False
    _AnthropicClient.fail_ping = False
    _AnthropicClient.empty_content = True
    assert await adapter.generate("p") == ""
    _AnthropicClient.empty_content = False


class _GeminiModels:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def list(self):
        return []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text="gemini-answer")


class _GeminiClient:
    instances: list["_GeminiClient"] = []
    fail_list = False

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        models = _GeminiModels()
        if self.fail_list:
            async def failing_list():
                raise RuntimeError("offline")
            models.list = failing_list  # type: ignore[method-assign]
        self.aio = SimpleNamespace(models=models)
        type(self).instances.append(self)


@pytest.mark.asyncio
async def test_gemini_adapter_configuration_availability_and_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = GeminiAdapter()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_DEFAULT_MODEL", raising=False)
    assert adapter.provider_name == "Gemini"
    assert adapter.default_model == "gemini-2.0-flash"
    assert adapter.is_configured() is False
    assert await adapter.is_available() is False
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        await adapter.generate("p")

    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
    monkeypatch.setenv("GEMINI_DEFAULT_MODEL", "gem-test")
    fake_genai = SimpleNamespace(Client=_GeminiClient)
    fake_google = SimpleNamespace(genai=fake_genai)
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    assert await adapter.is_available() is True
    assert await adapter.generate("p", system_prompt="s", model="gem-override", temperature=0.4) == "gemini-answer"
    call = _GeminiClient.instances[-1].aio.models.calls[-1]
    assert call["model"] == "gem-override"
    assert call["contents"] == "s\n\np"
    assert call["config"] == {"temperature": 0.4}

    _GeminiClient.fail_list = True
    assert await adapter.is_available() is False
    _GeminiClient.fail_list = False
