from pydantic import BaseModel


class DisruptionRequest(BaseModel):
    a: str
    b: str
    reason: str = ""
