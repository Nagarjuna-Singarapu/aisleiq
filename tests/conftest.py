import os
import tempfile
from typing import Generator

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Use in-memory SQLite for tests (StaticPool shares a single connection)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("VIDEO_DIR", tempfile.mkdtemp())
os.environ.setdefault("FRAMES_DIR", tempfile.mkdtemp())
os.environ.setdefault("EXPORT_DIR", tempfile.mkdtemp())

from app.models import db_models  # noqa: F401 — ensure all models are registered
from app.database import Base, get_db
from app.main import create_app

_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=_TEST_ENGINE)
_TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)


@pytest.fixture(scope="session")
def test_engine():
    yield _TEST_ENGINE


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = _TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI test client with its own isolated in-memory DB per test."""
    from sqlalchemy.pool import StaticPool as _SP
    fresh_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=_SP,
    )
    Base.metadata.create_all(bind=fresh_engine)
    FreshSession = sessionmaker(autocommit=False, autoflush=False, bind=fresh_engine)

    app = create_app()

    def override_get_db():
        s = FreshSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    fresh_engine.dispose()


@pytest.fixture
def blank_video_path(tmp_path) -> str:
    """Create a small valid MP4 file with blank frames."""
    path = str(tmp_path / "test_blank.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, 10.0, (320, 240))
    for _ in range(30):  # 3 seconds at 10 fps
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return path


@pytest.fixture
def person_video_path(tmp_path) -> str:
    """Create a small MP4 where frames contain a white rectangle (simulating a person)."""
    path = str(tmp_path / "test_person.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, 10.0, (320, 240))
    for _ in range(30):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.rectangle(frame, (100, 50), (150, 200), (255, 255, 255), -1)
        writer.write(frame)
    writer.release()
    return path


@pytest.fixture
def corrupt_video_path(tmp_path) -> str:
    """Create a file that looks like MP4 but isn't."""
    path = str(tmp_path / "corrupt.mp4")
    with open(path, "wb") as f:
        f.write(b"THIS IS NOT A VALID VIDEO FILE")
    return path

