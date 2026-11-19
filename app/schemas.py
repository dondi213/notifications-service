from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, HttpUrl, TypeAdapter, model_validator

Channel = Literal["email", "webhook"]
Status = Literal["pending", "processing", "retrying", "sent", "failed"]

_email = TypeAdapter(EmailStr)
_url = TypeAdapter(HttpUrl)


class NotificationCreate(BaseModel):
    channel: Channel
    recipient: str = Field(min_length=3, max_length=500, description="Email or webhook URL")
    subject: str | None = Field(default=None, max_length=200)
    message: str = Field(min_length=1, max_length=5000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_recipient(self) -> "NotificationCreate":
        if self.channel == "email":
            try:
                _email.validate_python(self.recipient)
            except ValueError:
                raise ValueError("recipient must be a valid email address") from None
            if not self.subject:
                raise ValueError("subject is required for email notifications")
        else:
            try:
                _url.validate_python(self.recipient)
            except ValueError:
                raise ValueError("recipient must be a valid http(s) URL") from None
        return self


class NotificationOut(BaseModel):
    id: str
    channel: Channel
    recipient: str
    subject: str | None
    message: str
    metadata: dict[str, Any]
    status: Status
    attempts: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None

    @classmethod
    def from_doc(cls, doc: dict) -> "NotificationOut":
        data = {k: v for k, v in doc.items() if k != "_id"}
        return cls(id=str(doc["_id"]), **data)
