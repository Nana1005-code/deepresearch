"""Model adapter: bounded output and safe response diagnostics for both modes."""
from __future__ import annotations

import logging
from hello_agents import HelloAgentsLLM

logger = logging.getLogger(__name__)


class ModelOutputError(RuntimeError):
    """The model returned no usable answer or an incomplete answer."""


def require_text(text: str | None, stage: str) -> str:
    if not text or not text.strip():
        logger.error("Empty model output after cleaning: stage=%s", stage)
        raise ModelOutputError(f"{stage}失败：模型没有返回可用正文，请检查模型服务和 LLM_MAX_TOKENS 设置后重试。")
    return text.strip()


class ResearchLLM(HelloAgentsLLM):
    """Keep diagnostics local to each call because task summaries run concurrently."""

    def _request_options(self, kwargs, *, stream):
        options = dict(kwargs)
        options.update(model=self.model, stream=stream)
        options.setdefault("temperature", self.temperature)
        options["max_tokens"] = options.get("max_tokens") or self.max_tokens or 8192
        return options

    def _validate_output(self, content, finish_reason, limit, mode, usage=None):
        # Never log prompts, generated text, reasoning text, or credentials.
        logger.info(
            "LLM response mode=%s model=%s max_tokens=%s finish_reason=%s content_chars=%s completion_tokens=%s",
            mode, self.model, limit, finish_reason, len(content),
            getattr(usage, "completion_tokens", None),
        )
        if finish_reason == "length":
            raise ModelOutputError(
                f"模型输出被截断（finish_reason=length，max_tokens={limit}），未将不完整内容作为结果。"
                "请提高 LLM_MAX_TOKENS 或缩短研究范围后重试。"
            )
        if finish_reason == "content_filter":
            raise ModelOutputError("模型服务拦截了本次输出（content_filter），请调整研究内容后重试。")
        if finish_reason is None:
            raise ModelOutputError("模型响应未正常结束，未将不完整内容作为结果，请重试。")
        require_text(content, "模型生成")

    def invoke(self, messages, **kwargs):
        options = self._request_options(kwargs, stream=False)
        response = self._client.chat.completions.create(messages=messages, **options)
        choice = response.choices[0] if response.choices else None
        content = (choice.message.content or "") if choice else ""
        self._validate_output(content, choice.finish_reason if choice else None,
                              options["max_tokens"], "sync", getattr(response, "usage", None))
        return content

    def stream_invoke(self, messages, **kwargs):
        options = self._request_options(kwargs, stream=True)
        response = self._client.chat.completions.create(messages=messages, **options)
        parts = []
        finish_reason = None
        usage = None
        try:
            for chunk in response:
                if getattr(chunk, "usage", None) is not None:
                    usage = chunk.usage
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.finish_reason is not None:
                    finish_reason = choice.finish_reason
                content = choice.delta.content or ""
                if content:
                    parts.append(content)
                    yield content
        finally:
            response.close()
        self._validate_output("".join(parts), finish_reason, options["max_tokens"], "stream", usage)
