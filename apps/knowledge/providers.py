import hashlib
import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.utils.module_loading import import_string
from openai import APIConnectionError, APIStatusError, OpenAI

from .exceptions import ProviderConfigurationError, RetryableProviderError


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated: bool = False


@dataclass(frozen=True)
class ChatDelta:
    text: str = ""
    usage: ProviderUsage | None = None


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str

    def embed(self, inputs: list[str]) -> list[list[float]]: ...


class ChatProvider(Protocol):
    provider_name: str
    model_name: str

    def stream(self, messages: list[dict[str, str]]) -> Iterator[ChatDelta]: ...


class SiliconFlowEmbeddingProvider:
    provider_name = "siliconflow"

    def __init__(self):
        self.model_name = settings.SILICONFLOW_EMBEDDING_MODEL
        if not settings.SILICONFLOW_API_KEY:
            raise ProviderConfigurationError("缺少 SILICONFLOW_API_KEY，无法执行向量化")
        self.client = OpenAI(
            api_key=settings.SILICONFLOW_API_KEY, base_url=settings.SILICONFLOW_API_BASE
        )

    def embed(self, inputs: list[str]) -> list[list[float]]:
        try:
            response = self.client.embeddings.create(model=self.model_name, input=inputs)
        except (APIConnectionError, APIStatusError) as exc:
            raise RetryableProviderError(str(exc)) from exc
        vectors = [item.embedding for item in response.data]
        if any(len(vector) != settings.VECTOR_DIMENSIONS for vector in vectors):
            raise ProviderConfigurationError(
                f"Embedding 维度与 VECTOR_DIMENSIONS={settings.VECTOR_DIMENSIONS} 不一致"
            )
        return vectors


class DeterministicEmbeddingProvider:
    """Local, keyless provider used only by tests and offline demos."""

    provider_name = "deterministic"
    model_name = "deterministic-1024"

    def embed(self, inputs: list[str]) -> list[list[float]]:
        output = []
        for item in inputs:
            digest = hashlib.sha512(item.encode("utf-8")).digest()
            vector = [((digest[index % len(digest)] / 255) * 2 - 1) for index in range(1024)]
            norm = math.sqrt(sum(value * value for value in vector))
            output.append([value / norm for value in vector])
        return output


class DemoChatProvider:
    """Keyless, predictable replies for the Docker-free local learning mode."""

    provider_name = "knowflow-demo"
    model_name = "local-demo-chat"

    def stream(self, messages: list[dict[str, str]]) -> Iterator[ChatDelta]:
        prompt = messages[-1]["content"] if messages else ""
        question = prompt.rsplit("问题：", maxsplit=1)[-1].strip()
        response = (
            "这是 KnowFlow 本地演示回答。当前使用离线向量与模拟模型，因此不会调用 "
            "DeepSeek 或 SiliconFlow。已根据已检索的文档片段回答你的问题："
            f"{question}。正式环境请关闭本地演示模式并配置 API Key。"
        )
        for start in range(0, len(response), 24):
            yield ChatDelta(text=response[start : start + 24])
        yield ChatDelta(
            usage=ProviderUsage(
                input_tokens=max(1, len(prompt) // 4),
                output_tokens=max(1, len(response) // 4),
                estimated=True,
            )
        )


class DeepSeekChatProvider:
    provider_name = "deepseek"

    def __init__(self):
        self.model_name = settings.DEEPSEEK_MODEL
        if not settings.DEEPSEEK_API_KEY:
            raise ProviderConfigurationError("缺少 DEEPSEEK_API_KEY，无法生成回答")
        self.client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_API_BASE)

    def stream(self, messages: list[dict[str, str]]) -> Iterator[ChatDelta]:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            for event in response:
                text = event.choices[0].delta.content if event.choices else ""
                usage = None
                if event.usage:
                    usage = ProviderUsage(
                        input_tokens=event.usage.prompt_tokens,
                        output_tokens=event.usage.completion_tokens,
                    )
                if text or usage:
                    yield ChatDelta(text=text or "", usage=usage)
        except (APIConnectionError, APIStatusError) as exc:
            raise RetryableProviderError(str(exc)) from exc


def get_embedding_provider() -> EmbeddingProvider:
    return import_string(settings.EMBEDDING_PROVIDER)()


def get_chat_provider() -> ChatProvider:
    return import_string(settings.CHAT_PROVIDER)()
