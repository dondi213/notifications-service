from datetime import UTC, datetime

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.collection import Collection


def _now() -> datetime:
    return datetime.now(UTC)


def _oid(notification_id: str) -> ObjectId | None:
    return ObjectId(notification_id) if ObjectId.is_valid(notification_id) else None


class NotificationRepository:
    """All MongoDB access lives here; the API and the worker never touch the collection directly."""

    def __init__(self, collection: Collection):
        self.collection = collection

    def create(self, data: dict) -> dict:
        now = _now()
        doc = {
            **data,
            "status": "pending",
            "attempts": 0,
            "last_error": None,
            "created_at": now,
            "updated_at": now,
            "sent_at": None,
        }
        result = self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def get(self, notification_id: str) -> dict | None:
        oid = _oid(notification_id)
        return self.collection.find_one({"_id": oid}) if oid else None

    def list(
        self, *, status: str | None = None, channel: str | None = None, skip: int = 0, limit: int = 20
    ) -> list[dict]:
        query = {}
        if status:
            query["status"] = status
        if channel:
            query["channel"] = channel
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        return list(cursor)

    def _update(self, notification_id: str, update: dict) -> dict | None:
        oid = _oid(notification_id)
        if oid is None:
            return None
        update.setdefault("$set", {})["updated_at"] = _now()
        return self.collection.find_one_and_update({"_id": oid}, update, return_document=ReturnDocument.AFTER)

    def mark_processing(self, notification_id: str) -> dict | None:
        return self._update(notification_id, {"$set": {"status": "processing"}, "$inc": {"attempts": 1}})

    def mark_sent(self, notification_id: str) -> dict | None:
        return self._update(
            notification_id, {"$set": {"status": "sent", "sent_at": _now(), "last_error": None}}
        )

    def mark_retrying(self, notification_id: str, error: str) -> dict | None:
        return self._update(notification_id, {"$set": {"status": "retrying", "last_error": error}})

    def mark_failed(self, notification_id: str, error: str) -> dict | None:
        return self._update(notification_id, {"$set": {"status": "failed", "last_error": error}})

    def reset_for_retry(self, notification_id: str) -> dict | None:
        return self._update(notification_id, {"$set": {"status": "pending", "attempts": 0}})
