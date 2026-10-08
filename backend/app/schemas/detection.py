from typing import Literal

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: Literal["user", "ai"]
    text: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


class ChatFocus(BaseModel):
    cls: str = Field(alias="class")
    index: int

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    question: str
    answer: str
    focus: ChatFocus | None = None
