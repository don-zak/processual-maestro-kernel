"""Google Gemini Adapter"""

from __future__ import annotations

import os

from .base import BaseLLMAdapter


class GeminiAdapter(BaseLLMAdapter):
    """Adapter for Google Gemini API."""

    @property
    def provider_name(self) -> str:
        return "Gemini"

    @property
    def default_model(self) -> str:
        return os.environ.get("GEMINI_DEFAULT_MODEL", "gemini-2.0-flash")

    def is_configured(self) -> bool:
        return bool(os.environ.get("GEMINI_API_KEY", ""))

    async def is_available(self) -> bool:
        if not self.is_configured():
            return False
        try:
            import google.genai as genai

            api_key = os.environ.get("GEMINI_API_KEY") or ""
            client = genai.Client(api_key=api_key)
            await client.aio.models.list()
            return True
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Gemini adapter is not configured: GEMINI_API_KEY is not set")

        import google.genai as genai

        client = genai.Client(api_key=api_key)

        model = kwargs.get("model") or self.default_model
        contents = [system_prompt, prompt] if system_prompt else [prompt]
        response = await client.aio.models.generate_content(
            model=model,
            contents="\n\n".join(contents),
            config={"temperature": kwargs.get("temperature", 0.7)},
        )
        return response.text or ""
