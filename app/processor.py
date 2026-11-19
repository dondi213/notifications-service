import logging
from collections.abc import Callable

from app.channels import DeliveryError, dispatch
from app.repository import NotificationRepository

logger = logging.getLogger(__name__)


def process_notification(
    repo: NotificationRepository,
    notification_id: str,
    *,
    is_last_attempt: bool,
    send: Callable[[dict], None] = dispatch,
) -> str:
    """Deliver one notification and record the outcome.

    Kept separate from Celery so the logic can be unit-tested without a broker.
    Raises DeliveryError when the caller should retry.
    """
    notification = repo.mark_processing(notification_id)
    if notification is None:
        logger.warning("notification_not_found", extra={"notification_id": notification_id})
        return "missing"

    try:
        send(notification)
    except DeliveryError as exc:
        log_extra = {
            "notification_id": notification_id,
            "attempt": notification["attempts"],
            "error": str(exc),
        }
        if is_last_attempt:
            repo.mark_failed(notification_id, str(exc))
            logger.error("notification_failed", extra=log_extra)
            return "failed"
        repo.mark_retrying(notification_id, str(exc))
        logger.warning("notification_retrying", extra=log_extra)
        raise

    repo.mark_sent(notification_id)
    return "sent"
