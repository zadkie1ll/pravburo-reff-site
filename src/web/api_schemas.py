"""Response shapes shared by several API modules."""

from pydantic import BaseModel


class OptionOut(BaseModel):
    """One choice of a filter or select: the value to send and the label to show."""

    value: str
    label: str


class OkResponse(BaseModel):
    ok: bool = True
