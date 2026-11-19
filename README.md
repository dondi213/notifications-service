# Notifications Service

An asynchronous notification service: the API accepts email and webhook notifications, stores them in **MongoDB**, and a **Celery** worker delivers them in the background through a **Redis** queue, with automatic retries and exponential backoff.

## Features

- `POST /notifications` returns **202 Accepted** immediately; delivery happens in the worker
- Channels: **email** (simulated provider) and **webhook** (HTTP POST with JSON)
- **Automatic retries** with exponential backoff (2s, 4s, 8s, 16s, 32s); then the notification is marked `failed`
- **Manual retry** endpoint for failed notifications
- Status tracking: `pending → processing → sent` or `retrying → failed`, with attempt count and last error
- **Structured JSON logs** (one JSON object per line), ready for log aggregation tools
- **Health check** that verifies MongoDB and Redis (`503` when degraded)
- Tests with mongomock and `httpx.MockTransport`: no MongoDB, Redis or network needed
- Docker Compose with API, worker, MongoDB and Redis; CI with GitHub Actions

## Tech stack

Python 3.12 · FastAPI · Celery · Redis 7 · MongoDB 7 (PyMongo) · httpx · pytest · Docker

## Architecture

```
Client ──POST──► FastAPI ──insert──► MongoDB
                   │                    ▲
                   └─enqueue id─► Redis │ update status
                                   │    │
                                   ▼    │
                             Celery worker ──► Email provider / Webhook URL
                                   │
                         error ──► retry with backoff (max 5) ──► failed
```

## Getting started

```bash
docker compose up --build
```

- API and docs: http://localhost:8000/docs
- Worker logs: `docker compose logs -f worker`

## Try it

```bash
# Email (succeeds)
curl -X POST http://localhost:8000/notifications -H "Content-Type: application/json" \
  -d '{"channel": "email", "recipient": "ana@example.com", "subject": "Welcome", "message": "Hi Ana!"}'

# Email that always fails: watch the retries in the worker logs
curl -X POST http://localhost:8000/notifications -H "Content-Type: application/json" \
  -d '{"channel": "email", "recipient": "down@fail.test", "subject": "Test", "message": "Retry me"}'

# Webhook: get a free test URL at https://webhook.site
curl -X POST http://localhost:8000/notifications -H "Content-Type: application/json" \
  -d '{"channel": "webhook", "recipient": "https://webhook.site/<your-id>", "message": "Order shipped"}'

curl http://localhost:8000/notifications?status=failed
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest --cov=app
ruff check .
```

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/notifications` | Queue a notification (`202`) |
| GET | `/notifications` | List (`?status=`, `?channel=`, `?skip=`, `?limit=`) |
| GET | `/notifications/{id}` | Notification detail and delivery status |
| POST | `/notifications/{id}/retry` | Re-queue a `failed` notification |
| GET | `/health` | MongoDB and Redis health |

## Design decisions

- **Delivery logic is a plain function** (`processor.py`), separate from Celery, so it's unit-tested without a broker.
- **`task_acks_late`**: if a worker crashes mid-delivery, the task returns to the queue instead of being lost.
- **Only the id goes through the queue**, not the whole notification: MongoDB is the single source of truth.
- **The repository pattern** keeps MongoDB queries in one place.
- **Validation depends on the channel**: email recipients must be valid addresses with a subject; webhooks need an http(s) URL.
