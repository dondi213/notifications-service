import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Annotated

import redis
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import ensure_indexes, get_client, get_collection
from app.logging_config import setup_logging
from app.repository import NotificationRepository
from app.schemas import Channel, NotificationCreate, NotificationOut, Status
from app.tasks import send_notification

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_indexes(get_collection())
    yield


app = FastAPI(
    title="Notifications Service",
    description="Queues email and webhook notifications and delivers them in the background.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------- Dependencies (overridden in tests) ----------
def get_repository() -> NotificationRepository:
    return NotificationRepository(get_collection())


def get_enqueuer() -> Callable[[str], None]:
    return lambda notification_id: send_notification.delay(notification_id)


def get_health_checks() -> dict[str, Callable[[], bool]]:
    return {
        "mongo": lambda: bool(get_client().admin.command("ping")),
        "redis": lambda: redis.Redis.from_url(settings.redis_url, socket_timeout=2).ping(),
    }


Repo = Annotated[NotificationRepository, Depends(get_repository)]
Enqueue = Annotated[Callable[[str], None], Depends(get_enqueuer)]


# ---------- Routes ----------
@app.post("/notifications", response_model=NotificationOut, status_code=status.HTTP_202_ACCEPTED)
def create_notification(data: NotificationCreate, repo: Repo, enqueue: Enqueue) -> NotificationOut:
    """Returns 202 right away: delivery happens later in the Celery worker."""
    doc = repo.create(data.model_dump())
    notification_id = str(doc["_id"])
    enqueue(notification_id)
    logger.info(
        "notification_queued",
        extra={"notification_id": notification_id, "channel": data.channel},
    )
    return NotificationOut.from_doc(doc)


@app.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    repo: Repo,
    status_filter: Annotated[Status | None, Query(alias="status")] = None,
    channel: Channel | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[NotificationOut]:
    docs = repo.list(status=status_filter, channel=channel, skip=skip, limit=limit)
    return [NotificationOut.from_doc(d) for d in docs]


@app.get("/notifications/{notification_id}", response_model=NotificationOut)
def get_notification(notification_id: str, repo: Repo) -> NotificationOut:
    doc = repo.get(notification_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationOut.from_doc(doc)


@app.post(
    "/notifications/{notification_id}/retry",
    response_model=NotificationOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_notification(notification_id: str, repo: Repo, enqueue: Enqueue) -> NotificationOut:
    """Manually re-queue a notification that ran out of automatic retries."""
    doc = repo.get(notification_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if doc["status"] != "failed":
        raise HTTPException(status_code=409, detail="Only failed notifications can be retried")

    doc = repo.reset_for_retry(notification_id)
    enqueue(notification_id)
    return NotificationOut.from_doc(doc)


@app.get("/health")
def health(checks: Annotated[dict, Depends(get_health_checks)]) -> JSONResponse:
    results = {}
    for name, check in checks.items():
        try:
            results[name] = bool(check())
        except Exception:  # noqa: BLE001 - any failure means "unhealthy"
            results[name] = False
    healthy = all(results.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", **results},
    )
