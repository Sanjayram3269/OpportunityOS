import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import engine
from app.main import app


@pytest.fixture()
def db(monkeypatch):
    """Yield a transactional session, rolling back after each test.

    Patches ``app.db.session.SessionLocal`` and ``app.automation.scheduler.SessionLocal``
    so that services which call ``SessionLocal()`` internally get this test's session.
    This ensures all DB writes (including ``db.commit()`` calls inside services)
    stay within the test's transaction and are rolled back on teardown.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    # Patch SessionLocal everywhere it is imported so services use the
    # test's session rather than creating independent sessions that
    # would bypass the test's transactional boundary.
    def _session_factory():
        return session

    monkeypatch.setattr("app.db.session.SessionLocal", _session_factory)
    monkeypatch.setattr("app.automation.scheduler.SessionLocal", _session_factory)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    """Provide a TestClient wired to the test db session."""
    from app.api.deps import get_db

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()
