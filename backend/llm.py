from typing import Any

import tiktoken
from llama_index.core.base.llms.types import LLMMetadata, MessageRole
from llama_index.llms.openai import OpenAI

from config import Settings

# Known DeepSeek models; unknown names fall back to deepseek_context_window.
DEEPSEEK_CONTEXT_WINDOWS: dict[str, int] = {
    "deepseek-v4-pro": 128_000,
    "deepseek-v4-flash": 128_000,
    "deepseek-chat": 64_000,
    "deepseek-reasoner": 64_000,
}


class OpenAICompatibleLLM(OpenAI):
    """OpenAI-compatible LLM for DeepSeek and other third-party chat APIs."""

    context_window: int | None = None

    @property
    def metadata(self) -> LLMMetadata:
        window = self.context_window
        if window is None:
            window = DEEPSEEK_CONTEXT_WINDOWS.get(self.model, 64_000)

        return LLMMetadata(
            context_window=window,
            num_output=self.max_tokens or -1,
            is_chat_model=True,
            is_function_calling_model=True,
            model_name=self.model,
            system_role=MessageRole.SYSTEM,
        )

    @property
    def _tokenizer(self) -> Any:
        try:
            return tiktoken.encoding_for_model(self._get_model_name())
        except KeyError:
            return tiktoken.get_encoding("cl100k_base")


def create_llm(settings: Settings) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        api_base=settings.deepseek_base_url,
        context_window=settings.deepseek_context_window,
        temperature=0.2,
        max_tokens=4096,
    )
