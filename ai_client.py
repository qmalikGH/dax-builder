"""
ai_client.py
============
Abstraction layer for multiple AI providers.

Supported providers (set via .env):
    AI_PROVIDER=anthropic   → Anthropic Claude (default)
    AI_PROVIDER=azure       → Azure OpenAI
    AI_PROVIDER=ollama      → Local Ollama instance

All providers expose the same interface:
    client = get_client()
    response = client.chat(messages, system_prompt=None)
    # returns a plain string with the assistant reply
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic").lower()
AI_MODEL    = os.getenv("AI_MODEL", "claude-sonnet-4-5")


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BaseAIClient:
    def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
    ) -> str:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Anthropic (Claude)
# ---------------------------------------------------------------------------

class AnthropicClient(BaseAIClient):
    def __init__(self):
        try:
            import anthropic as _anthropic
        except ImportError as e:
            raise ImportError("Run: pip install anthropic") from e

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Set it as an environment variable, in a .env file (local), "
                "or in Streamlit Cloud under Settings → Secrets."
            )

        self._client = _anthropic.Anthropic(api_key=api_key)
        self._model  = AI_MODEL

    def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
    ) -> str:
        kwargs = {
            "model":      self._model,
            "max_tokens": 4096,
            "messages":   messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self._client.messages.create(**kwargs)
        return response.content[0].text


# ---------------------------------------------------------------------------
# Azure OpenAI
# ---------------------------------------------------------------------------

class AzureOpenAIClient(BaseAIClient):
    def __init__(self):
        try:
            from openai import AzureOpenAI
        except ImportError as e:
            raise ImportError("Run: pip install openai") from e

        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key  = os.getenv("AZURE_OPENAI_API_KEY")
        api_ver  = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

        if not endpoint or not api_key:
            raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set in .env")

        self._client     = AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_ver)
        self._deployment = AI_MODEL  # must match your Azure deployment name

    def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
    ) -> str:
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=all_messages,
            max_tokens=4096,
        )
        return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Ollama (local)
# ---------------------------------------------------------------------------

class OllamaClient(BaseAIClient):
    def __init__(self):
        try:
            import requests as _requests
            self._requests = _requests
        except ImportError as e:
            raise ImportError("Run: pip install requests") from e

        self._base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._model    = AI_MODEL  # e.g. "llama3", "mistral", "codellama"

    def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
    ) -> str:
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        payload = {
            "model":    self._model,
            "messages": all_messages,
            "stream":   False,
        }
        resp = self._requests.post(
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "anthropic": AnthropicClient,
    "azure":     AzureOpenAIClient,
    "ollama":    OllamaClient,
}


def get_client() -> BaseAIClient:
    """Return the correct AI client based on AI_PROVIDER in .env."""
    cls = _PROVIDERS.get(AI_PROVIDER)
    if cls is None:
        raise ValueError(
            f"Unknown AI_PROVIDER '{AI_PROVIDER}'. "
            f"Valid options: {list(_PROVIDERS.keys())}"
        )
    return cls()


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Provider : {AI_PROVIDER}")
    print(f"Model    : {AI_MODEL}")
    client = get_client()
    reply = client.chat(
        messages=[{"role": "user", "content": "Say 'DAX Builder ready' and nothing else."}]
    )
    print(f"Reply    : {reply}")
