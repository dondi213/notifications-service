import httpx
import pytest

from app.channels import DeliveryError, send_email, send_webhook
from app.processor import process_notification


def make_notification(repo, **overrides):
    data = {
        "channel": "email",
        "recipient": "ana@example.com",
        "subject": "Hi",
        "message": "Hello",
        "metadata": {},
        **overrides,
    }
    return str(repo.create(data)["_id"])


def failing_sender(_notification):
    raise DeliveryError("provider down")


def test_successful_delivery_marks_sent(repo):
    notification_id = make_notification(repo)
    sent = []

    result = process_notification(repo, notification_id, is_last_attempt=False, send=sent.append)

    doc = repo.get(notification_id)
    assert result == "sent"
    assert doc["status"] == "sent"
    assert doc["attempts"] == 1
    assert doc["sent_at"] is not None
    assert len(sent) == 1


def test_failure_marks_retrying_and_raises(repo):
    notification_id = make_notification(repo)

    with pytest.raises(DeliveryError):
        process_notification(repo, notification_id, is_last_attempt=False, send=failing_sender)

    doc = repo.get(notification_id)
    assert doc["status"] == "retrying"
    assert doc["last_error"] == "provider down"


def test_failure_on_last_attempt_marks_failed(repo):
    notification_id = make_notification(repo)

    result = process_notification(repo, notification_id, is_last_attempt=True, send=failing_sender)

    assert result == "failed"
    assert repo.get(notification_id)["status"] == "failed"


def test_attempts_are_counted(repo):
    notification_id = make_notification(repo)
    for _ in range(2):
        with pytest.raises(DeliveryError):
            process_notification(repo, notification_id, is_last_attempt=False, send=failing_sender)
    process_notification(repo, notification_id, is_last_attempt=False, send=lambda n: None)

    doc = repo.get(notification_id)
    assert doc["attempts"] == 3
    assert doc["status"] == "sent"
    assert doc["last_error"] is None


def test_missing_notification(repo):
    assert process_notification(repo, "000000000000000000000000", is_last_attempt=False) == "missing"


# ---------- Channels ----------
def test_simulated_email_failure():
    with pytest.raises(DeliveryError):
        send_email({"_id": "1", "recipient": "down@fail.test", "subject": "x"})


def test_webhook_posts_json_payload():
    received = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received["url"] = str(request.url)
        received["json"] = request.read().decode()
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    send_webhook(
        {"_id": "abc", "recipient": "https://example.com/hook", "message": "Hello", "metadata": {}},
        client=client,
    )

    assert received["url"] == "https://example.com/hook"
    assert '"message":"Hello"' in received["json"].replace(" ", "")


def test_webhook_server_error_raises_delivery_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    with pytest.raises(DeliveryError):
        send_webhook({"_id": "abc", "recipient": "https://example.com/hook", "message": "x"}, client=client)
