import pytest


def test_create_email_notification_is_queued(client, queued, email_payload):
    res = client.post("/notifications", json=email_payload)

    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "pending"
    assert body["attempts"] == 0
    assert body["metadata"] == {"user_id": 42}
    assert queued == [body["id"]]


def test_create_webhook_notification(client, queued):
    res = client.post(
        "/notifications",
        json={"channel": "webhook", "recipient": "https://example.com/hook", "message": "Order shipped"},
    )
    assert res.status_code == 202
    assert len(queued) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"channel": "email", "recipient": "not-an-email", "subject": "Hi", "message": "x"},
        {"channel": "email", "recipient": "ana@example.com", "message": "no subject"},
        {"channel": "webhook", "recipient": "not-a-url", "message": "x"},
        {"channel": "sms", "recipient": "5512345678", "message": "x"},
        {"channel": "email", "recipient": "ana@example.com", "subject": "Hi", "message": ""},
    ],
)
def test_invalid_payloads_rejected(client, queued, payload):
    assert client.post("/notifications", json=payload).status_code == 422
    assert queued == []


def test_get_notification(client, email_payload):
    created = client.post("/notifications", json=email_payload).json()
    res = client.get(f"/notifications/{created['id']}")
    assert res.status_code == 200
    assert res.json()["recipient"] == "ana@example.com"


@pytest.mark.parametrize("bad_id", ["123", "000000000000000000000000"])
def test_get_unknown_notification(client, bad_id):
    assert client.get(f"/notifications/{bad_id}").status_code == 404


def test_list_filters_by_status_and_channel(client, repo, email_payload):
    sent = client.post("/notifications", json=email_payload).json()
    client.post(
        "/notifications",
        json={"channel": "webhook", "recipient": "https://example.com/hook", "message": "x"},
    )
    repo.mark_sent(sent["id"])

    by_status = client.get("/notifications?status=sent").json()
    assert [n["id"] for n in by_status] == [sent["id"]]

    by_channel = client.get("/notifications?channel=webhook").json()
    assert len(by_channel) == 1
    assert by_channel[0]["channel"] == "webhook"


def test_list_rejects_unknown_status(client):
    assert client.get("/notifications?status=lost").status_code == 422


def test_retry_failed_notification(client, repo, queued, email_payload):
    created = client.post("/notifications", json=email_payload).json()
    repo.mark_failed(created["id"], "provider down")

    res = client.post(f"/notifications/{created['id']}/retry")

    assert res.status_code == 202
    assert res.json()["status"] == "pending"
    assert queued == [created["id"], created["id"]]


def test_retry_only_failed_notifications(client, email_payload):
    created = client.post("/notifications", json=email_payload).json()
    assert client.post(f"/notifications/{created['id']}/retry").status_code == 409


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "mongo": True, "redis": True}


def test_health_degraded(client):
    from app.main import app, get_health_checks

    def broken():
        raise ConnectionError("redis down")

    app.dependency_overrides[get_health_checks] = lambda: {"mongo": lambda: True, "redis": broken}
    res = client.get("/health")
    assert res.status_code == 503
    assert res.json()["redis"] is False
