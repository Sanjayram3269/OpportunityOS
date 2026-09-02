import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Pool configuration tuned for production.
# pool_pre_ping: verifies connections before use (handles stale connections)
# pool_size: persistent connections in the pool (adjust for production load)
# max_overflow: additional connections beyond pool_size under burst
# pool_recycle: recycle connections after this many seconds (prevents stale)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    echo=settings.debug and settings.is_development,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

logger.info(
    "Database engine configured: pool_size=%d, max_overflow=%d",
    5, 10,
)