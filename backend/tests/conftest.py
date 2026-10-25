import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(autouse=True)
def ensure_app_lifespan():
    # Existing test modules use module-level clients; enter lifespan so schema/seed setup runs.
    with TestClient(app):
        yield

import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
