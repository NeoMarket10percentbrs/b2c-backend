from pydantic import BaseModel, Field


class SubscribeRequest(BaseModel):
    events: list[str] | None = Field(default=None)
