import os
import shutil
import sys
from pathlib import Path

# Ensure project root is on sys.path so `import app` succeeds when running plain `pytest`.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test.db")
os.environ.setdefault("UPLOAD_DIR", "./test_uploads")
os.environ.setdefault("RSS_FEED_URL", "https://example.com/rss.xml")

from app.config import get_settings
from app.db import Base, get_session
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_environment():
    get_settings.cache_clear()
    settings = get_settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(settings.upload_dir, ignore_errors=True)
    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.replace("sqlite+pysqlite:///", "")
        if db_path and Path(db_path).exists():
            Path(db_path).unlink()


@pytest.fixture
def engine():
    settings = get_settings()
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(engine) -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, expire_on_commit=False, future=True)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session):
    def override_get_session():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise
        finally:
            db_session.expunge_all()

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


__all__ = ["client", "db_session"]
