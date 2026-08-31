"""OpenAI-compatible chat completion provider.

Works with any OpenAI-compatible API:
  - HuggingFace Inference API (free tier, models like Mistral)
  - OpenRouter (free models available)
  - Local Ollama
  - Any OpenAI-compatible endpoint

Uses httpx for HTTP calls (already a project dependency).
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.ai.base import (
    AIProvider,
    AIPermissionError,
    AIProviderError,
    AITimeoutError,
)
from app.ai.prompts import SYSTEM_PROMPT, build_insight_prompt


class OpenAICompatProvider(AIProvider):
    """Provider using an OpenAI-compatible chat completion API.

    Configuration:
        api_url: Full endpoint URL (e.g. https://api-inference.huggingface.co/models/...)
        api_key: Bearer token (optional for some providers)
        model: Model identifier
        timeout: Request timeout in seconds
        max_tokens: Max completion tokens
    """

    def __init__(
        self,
        api_url: str,
        api_key: str | None = None,
        model: str = "mistralai/Mistral-7B-Instruct-v0.3",
        timeout: int = 60,
        max_tokens: int = 1024,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_tokens = max_tokens

    @property
    def provider_name(self) -> str:
        if "huggingface" in self._api_url or "hf" in self._api_url:
            return "huggingface"
        if "openrouter" in self._api_url:
            return "openrouter"
        return "openai_compat"

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_insight(self, context: dict[str, Any]) -> dict[str, Any]:
        """Call the chat completion API and parse the structured response."""
        if not self._api_key:
            raise AIPermissionError(
                f"No API key configured for {self.provider_name}. "
                "Set the appropriate environment variable."
            )

        user_message = build_insight_prompt(
            profile_summary=context.get("profile_summary", {}),
            opportunity_summary=context.get("opportunity_summary", {}),
            match_result=context.get("match_result", {}),
        )

        # Build OpenAI-compatible request
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": self._max_tokens,
            "temperature": 0.3,  # Low temperature for deterministic-ish output
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._api_url,
                    json=payload,
                    headers=headers,
                    timeout=self._timeout,
                )

            if response.status_code == 429:
                raise AITimeoutError(f"{self.provider_name}: rate limited (429)")

            response.raise_for_status()
            data = response.json()

            # Extract the assistant message content
            content = _extract_content(data)
            if content is None:
                raise AIProviderError(
                    f"{self.provider_name}: no content in response"
                )

            # Parse JSON from the response
            parsed = _parse_json_from_text(content)
            if parsed is None:
                raise AIProviderError(
                    f"{self.provider_name}: could not parse JSON from response"
                )

            # Validate and return
            parsed["provider"] = self.provider_name
            parsed["model"] = self._model
            return parsed

        except httpx.TimeoutException as exc:
            raise AITimeoutError(
                f"{self.provider_name}: request timed out ({self._timeout}s)"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AIProviderError(
                f"{self.provider_name}: HTTP {exc.response.status_code}"
            ) from exc
        except (AIPermissionError, AITimeoutError, AIProviderError):
            raise
        except Exception as exc:
            raise AIProviderError(
                f"{self.provider_name}: {type(exc).__name__}: {exc}"
            ) from exc


def _extract_content(data: dict[str, Any]) -> str | None:
    """Extract assistant message content from OpenAI-compatible response."""
    # Standard OpenAI format: choices[0].message.content
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

    # Some providers use "generated_text" (e.g. HF text generation)
    generated = data.get("generated_text")
    if isinstance(generated, str) and generated.strip():
        return generated.strip()

    return None


def _parse_json_from_text(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from AI response text.

    The AI might wrap JSON in markdown code blocks or include
    surrounding text. This function tries to find and parse the
    JSON object.
    """
    # Try to find JSON in a code block
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try to find a JSON object directly
    json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Try the entire text as JSON
    try:
        result = json.loads(text.strip())
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    return None
