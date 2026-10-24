import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# The API is auth-protected (see app/api/deps.py:require_auth). The test
# token must be set BEFORE the app (and its cached settings) is imported,
# so it goes first, ahead of any `app.*` import. This is a test-only value
# and is never used outside the test suite.
TEST_AUTH_TOKEN = "opportunityos-test-token"
os.environ["API_AUTH_TOKEN"] = TEST_AUTH_TOKEN

# ── Test-database isolation (CRITICAL) ────────────────────────────────────
# Tests must NEVER run against the development database. Several suites
# create and delete rows with their own committed sessions, and the
# dashboard/timeline suites have cleanup helpers that DELETE entire tables
# and commit. Against a populated dev database this both breaks tests that
# assume an empty schema AND permanently destroys real data (observed: a
# full pytest run deleted 322 real ingested opportunities, companies, leads
# and drafts from the dev database).
#
# Therefore, before any `app.*` import creates the engine, we:
#   1. derive a dedicated test database name (default: opportunityos_test),
#   2. refuse to run if it would collide with the configured dev database,
#   3. create the test database if missing,
#   4. export DATABASE_URL pointing at it (env var beats .env in pydantic),
#   5. provision its schema with the real alembic migrations (idempotent).
API_DIR = Path(__file__).resolve().parents[1]


def _prepare_test_database() -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    # Read settings WITHOUT populating get_settings()' lru_cache. The cache
    # must stay cold until AFTER the DATABASE_URL override below, otherwise
    # app.db.session / alembic would keep the dev URL forever (this exact
    # bug made an earlier "isolation" attempt silently run every test
    # against the development database).
    from app.core.config import Settings

    dev_settings = Settings()
    dev_url = make_url(dev_settings.database_url)
    test_db_name = os.environ.get("OPPORTUNITYOS_TEST_DB", "opportunityos_test")

    if dev_url.database == test_db_name:
        raise RuntimeError(
            "Refusing to run tests: DATABASE_URL already points at the test "
            f"database name {test_db_name!r} while configured as the app "
            "database. Set DATABASE_URL to your development database; "
            "pytest substitutes the test database automatically."
        )

    test_url = dev_url.set(database=test_db_name)

    # Create the test database if it does not exist yet.
    admin = create_engine(dev_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"),
                {"n": test_db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    finally:
        admin.dispose()

    # All subsequent `app.*` imports (engine, alembic env.py) read this.
    # NOTE: `str(url)` masks the password as "***" in SQLAlchemy 2.x — that
    # literal was previously exported and every connection failed auth.
    # render_as_string(hide_password=False) is the only faithful form.
    os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)

    # Defensive: if get_settings() was somehow already cached (e.g. by a
    # plugin), drop the cache so the override above is picked up.
    from app.core.config import get_settings

    get_settings.cache_clear()

    # Guarantee a FRESH schema on every pytest run. Tests that use their
    # own (non-fixture) sessions commit for real; without this wipe their
    # rows accumulate across runs and break count-based assertions
    # (observed: 23 failures from rows committed by the previous run).
    # This also proves no state can survive from run to run.
    wiper = create_engine(test_url, isolation_level="AUTOCOMMIT")
    try:
        with wiper.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    finally:
        wiper.dispose()

    # Provision schema with the real migrations — run against the wiped DB.
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(API_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    command.upgrade(alembic_cfg, "head")


_prepare_test_database()

from app.db.session import engine  # noqa: E402  (after DATABASE_URL override)
from app.main import app  # noqa: E402

# ── Fail-loud isolation guard ──────────────────────────────────────────
# If the engine ever points at the wrong database, tests would silently
# read and DELETE real data. Refuse to run instead.
assert engine.url.database == (
    os.environ.get("OPPORTUNITYOS_TEST_DB", "opportunityos_test")
), (
    "Test isolation broken: engine points at "
    f"{engine.url.database!r}, not the dedicated test database. "
    "Refusing to run tests against a non-test database."
)


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
    with TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Authorization": f"Bearer {TEST_AUTH_TOKEN}"},
    ) as c:
        yield c
    app.dependency_overrides.clear()
