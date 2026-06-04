from typing import Any

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.bridge.pydantic import Field, PrivateAttr
from openai import AsyncOpenAI, OpenAI

from config import Settings


class OpenAICompatibleEmbedding(BaseEmbedding):
    """Embeddings via any OpenAI-compatible API (SiliconFlow, OpenRouter, etc.)."""

    api_key: str = Field(exclude=True)
    api_base: str
    dimensions: int | None = None

    _client: OpenAI = PrivateAttr()
    _async_client: AsyncOpenAI = PrivateAttr()

    def __init__(
        self,
        model: str,
        api_key: str,
        api_base: str,
        dimensions: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model_name=model,
            api_key=api_key,
            api_base=api_base,
            dimensions=dimensions,
            **kwargs,
        )
        self._client = OpenAI(api_key=api_key, base_url=api_base)
        self._async_client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    def _embedding_kwargs(self) -> dict[str, Any]:
        if self.dimensions and self.model_name.startswith("text-embedding-3"):
            return {"dimensions": self.dimensions}
        return {}

    def _embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(
            model=self.model_name,
            input=text,
            **self._embedding_kwargs(),
        )
        return response.data[0].embedding

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._embed(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._embed(text)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        response = await self._async_client.embeddings.create(
            model=self.model_name,
            input=query,
            **self._embedding_kwargs(),
        )
        return response.data[0].embedding


def create_embed_model(settings: Settings) -> OpenAICompatibleEmbedding:
    return OpenAICompatibleEmbedding(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key or settings.deepseek_api_key,
        api_base=settings.embedding_base_url or settings.deepseek_base_url,
        dimensions=settings.embedding_dimensions,
    )
