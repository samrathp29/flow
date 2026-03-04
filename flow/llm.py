"""Thin LLM wrapper supporting Anthropic and OpenAI APIs."""

import logging

import anthropic
import openai

from flow.config import FlowConfig

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when an LLM call fails after all retries."""


class LLM:
    """Provider-agnostic LLM caller with retry-once semantics."""

    def __init__(self, config: FlowConfig):
        self.provider = config.llm_provider
        self.model = config.llm_model
        self.api_key = config.api_key

    def call(self, system_prompt: str, user_message: str) -> str:
        """Call the configured LLM. Retries once on failure."""
        dispatch = {
            "anthropic": self._call_anthropic,
            "openai": self._call_openai,
        }
        fn = dispatch.get(self.provider)
        if fn is None:
            raise LLMError(f"Unsupported LLM provider: {self.provider}")

        last_err = None
        for attempt in range(2):
            try:
                return fn(system_prompt, user_message).strip()
            except Exception as e:
                last_err = e
                if attempt == 0:
                    logger.warning("LLM call failed (attempt 1), retrying: %s", e)

        raise LLMError(f"LLM call failed after 2 attempts: {last_err}") from last_err

    def _call_anthropic(self, system_prompt: str, user_message: str) -> str:
        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0.1,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    def _call_openai(self, system_prompt: str, user_message: str) -> str:
        client = openai.OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            temperature=0.1,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content
