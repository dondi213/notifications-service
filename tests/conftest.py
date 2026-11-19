import mongomock
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_enqueuer, get_health_checks, get_repository
from app.repository import NotificationRepository


@pytest.fixture()
def repo():
    # mongomock: an in-memory MongoDB, so tests need no real database.
    collection = mongomock.MongoClient().db.notifications
    return NotificationRepository(collection)


@pytest.fixture()
def queued():
    """Collects the ids that would have been sent to Celery."""
    return []


@pytest.fixture()
def client(repo, queued):
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_enqueuer] = lambda: queued.append
    app.dependency_overrides[get_health_checks] = lambda: {"mongo": lambda: True, "redis": lambda: True}
    # No `with` block: skips the lifespan, which would connect to the real MongoDB.
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def email_payload():
    return {
        "channel": "email",
        "recipient": "ana@example.com",
        "subject": "Welcome",
        "message": "Thanks for signing up!",
        "metadata": {"user_id": 42},
    }
