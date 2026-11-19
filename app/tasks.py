from celery import Celery

from app.channels import DeliveryError
from app.config import settings
from app.db import get_collection
from app.logging_config import setup_logging
from app.processor import process_notification
from app.repository import NotificationRepository

setup_logging()

celery_app = Celery("notifications", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,  # if a worker dies mid-task, the message goes back to the queue
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_hijack_root_logger=False,  # keep our JSON logs
)


@celery_app.task(bind=True, name="notifications.send", max_retries=settings.max_retries)
def send_notification(self, notification_id: str) -> str:
    repo = NotificationRepository(get_collection())
    is_last_attempt = self.request.retries >= self.max_retries
    try:
        return process_notification(repo, notification_id, is_last_attempt=is_last_attempt)
    except DeliveryError as exc:
        # Exponential backoff: 2s, 4s, 8s, 16s, 32s
        countdown = settings.retry_base_seconds * (2**self.request.retries)
        raise self.retry(exc=exc, countdown=countdown) from exc
