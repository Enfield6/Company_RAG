import base64
import json
import logging

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.documents.types import ParsedElement

logger = logging.getLogger(__name__)


class ImageEnricher:
    def __init__(
        self,
        base_url: str | None,
        api_key: str | None,
        model: str | None,
    ) -> None:
        self.enabled = bool(base_url and api_key and model)
        self._model = (
            ChatOpenAI(
                base_url=base_url,
                api_key=api_key or "missing-qwen-api-key",
                model=model or "",
                temperature=0,
            )
            if self.enabled
            else None
        )

    async def enrich(self, element: ParsedElement) -> None:
        previous_text = element.metadata.get("previous_text", "")
        next_text = element.metadata.get("next_text", "")
        if not self._model or not element.image_bytes:
            self._apply_fallback(element, previous_text, next_text)
            return

        media_type = element.image_content_type or "image/png"
        encoded = base64.b64encode(element.image_bytes).decode("ascii")
        prompt = (
            "你在处理公司内部知识文档。结合页码、标题和图片前后文理解图片，不得臆造。"
            '返回严格 JSON：{"caption":"图片的业务含义","ocr":"可见文字"}。\n'
            f"前文：{previous_text or '无'}\n后文：{next_text or '无'}"
        )
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{encoded}"}},
            ]
        )
        try:
            response = await self._model.ainvoke([message])
            raw = response.content if isinstance(response.content, str) else str(response.content)
            raw = raw.strip().removeprefix("```json").removesuffix("```").strip()
            result = json.loads(raw)
            element.image_caption = str(result.get("caption", "")).strip()
            element.image_ocr = str(result.get("ocr", "")).strip()
            element.metadata["caption_source"] = "vision_model"
        except Exception:
            logger.warning("Vision enrichment failed; using document context", exc_info=True)
            self._apply_fallback(element, previous_text, next_text)

    def _apply_fallback(self, element: ParsedElement, previous_text: str, next_text: str) -> None:
        if element.image_caption:
            element.metadata["caption_source"] = "word_alt_text"
            return
        element.image_caption = self._context_caption(previous_text, next_text)
        element.metadata["caption_source"] = "context_fallback"

    @staticmethod
    def _context_caption(previous_text: str, next_text: str) -> str:
        context = " ".join(part for part in (previous_text, next_text) if part).strip()
        if not context:
            return "文档图片（尚未配置视觉模型，暂无可用邻近文字）。"
        return f"与以下邻近段落相关：{context[:600]}"
