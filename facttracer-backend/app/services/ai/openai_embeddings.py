from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.admin.settings import get_effective_setting


class OpenAIEmbeddingService:
    def __init__(self, db: Session | None = None) -> None:
        self.settings = get_settings()
        self.ai_processing_enabled = bool(get_effective_setting(db, "ai_processing_enabled"))
        self.api_key = get_effective_setting(db, "openai_api_key")
        self.embedding_model = get_effective_setting(db, "openai_embedding_model")
        self.embedding_dimensions = get_effective_setting(db, "openai_embedding_dimensions")
        self._client: OpenAI | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.ai_processing_enabled and self.api_key)

    @property
    def client(self) -> OpenAI:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, timeout=20)
        return self._client

    def embed_text(self, text: str) -> list[float] | None:
        text = (text or "").strip()
        if not self.enabled or not text:
            return None
        kwargs: dict = {
            "input": text,
            "model": self.embedding_model,
        }
        if self.embedding_dimensions:
            kwargs["dimensions"] = self.embedding_dimensions
        try:
            response = self.client.embeddings.create(**kwargs)
            return response.data[0].embedding
        except Exception:
            return None
