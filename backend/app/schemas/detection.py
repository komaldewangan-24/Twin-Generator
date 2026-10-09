from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

Coordinate = Annotated[float, Field(allow_inf_nan=False)]
Metres = Annotated[float, Field(gt=0, le=200, allow_inf_nan=False)]


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



class CalibrateRequest(BaseModel):
    """Either two points in the 3D view and their real distance, or the room's real sides."""

    a: list[Coordinate] | None = Field(default=None, min_length=3, max_length=3)
    b: list[Coordinate] | None = Field(default=None, min_length=3, max_length=3)
    real_m: Metres | None = None
    longer_side_m: Metres | None = None
    shorter_side_m: Metres | None = None

    @model_validator(mode="after")
    def _one_way(self):
        by_points = self.a is not None or self.b is not None or self.real_m is not None
        by_room = self.longer_side_m is not None or self.shorter_side_m is not None
        if by_points == by_room:
            raise ValueError("Send either two points and their real distance (a, b, real_m) or the room sides (longer_side_m).")
        if by_points and not (self.a and self.b and self.real_m):
            raise ValueError("Two points and their real distance are all needed: a, b and real_m.")
        if by_room and not self.longer_side_m:
            raise ValueError("longer_side_m is needed (shorter_side_m is optional).")
        return self
