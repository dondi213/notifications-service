import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class DeliveryError(Exception):
    """A notification could not be delivered (it may succeed if retried)."""


def send_email(notification: dict) -> None:
    """Simulated email provider: logs the email instead of sending it.

    Recipients ending in "@fail.test" simulate a provider outage, to demo the retries.
    To send real emails, replace this with an SMTP or SendGrid/Resend call.
    """
    if notification["recipient"].endswith("@fail.test"):
        raise DeliveryError("Simulated email provider failure")
    logger.info(
        "email_sent",
        extra={
            "notification_id": str(notification["_id"]),
            "to": notification["recipient"],
            "subject": notification.get("subject"),
        },
    )


def send_webhook(notification: dict, client: httpx.Client | None = None) -> None:
    payload = {
        "id": str(notification["_id"]),
        "subject": notification.get("subject"),
        "message": notification["message"],
        "metadata": notification.get("metadata", {}),
    }
    owns_client = client is None
    client = client or httpx.Client(timeout=settings.webhook_timeout_seconds)
    try:
        response = client.post(notification["recipient"], json=payload)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise DeliveryError(f"Webhook delivery failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    logger.info(
        "webhook_sent",
        extra={"notification_id": payload["id"], "status_code": response.status_code},
    )


SENDERS = {"email": send_email, "webhook": send_webhook}


def dispatch(notification: dict) -> None:
    SENDERS[notification["channel"]](notification)
