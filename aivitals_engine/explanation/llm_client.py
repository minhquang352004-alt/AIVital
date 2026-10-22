import os
from dataclasses import dataclass
from typing import Protocol

import httpx

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-5.4-nano"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_REASONING_EFFORT = "low"


@dataclass(frozen=True)
class LLMCompletion:
    text: str
    model: str


class LLMClient(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletion: ...


class LLMConfigurationError(RuntimeError):
    pass


class LLMRequestError(RuntimeError):
    pass


def optional_float(text: str | None) -> float | None:
    if text is None or not text.strip():
        return None
    return float(text)


class OpenAIChatClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        base_url: str = DEFAULT_OPENAI_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        reasoning_effort: str | None = DEFAULT_REASONING_EFFORT,
        temperature: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise LLMConfigurationError("Thiếu OPENAI_API_KEY")
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._temperature = temperature
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    @classmethod
    def from_environment(cls, transport: httpx.BaseTransport | None = None) -> "OpenAIChatClient":
        return cls(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
            base_url=os.environ.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL),
            reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", DEFAULT_REASONING_EFFORT) or None,
            temperature=optional_float(os.environ.get("OPENAI_TEMPERATURE")),
            transport=transport,
        )

    def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self._reasoning_effort is not None:
            payload["reasoning_effort"] = self._reasoning_effort
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        try:
            response = self._client.post("/chat/completions", json=payload)
        except httpx.HTTPError as exception:
            raise LLMRequestError(f"Không kết nối được OpenAI: {exception}") from exception
        if response.status_code >= 400:
            raise LLMRequestError(f"OpenAI trả lỗi HTTP {response.status_code}")
        body = response.json()
        text = body["choices"][0]["message"].get("content") or ""
        return LLMCompletion(text=text, model=body.get("model", self._model))

    def close(self) -> None:
        self._client.close()
