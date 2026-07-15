from pydantic import BaseModel


class LLMHealthResponse(BaseModel):
    provider: str
    model: str
    connected: bool
