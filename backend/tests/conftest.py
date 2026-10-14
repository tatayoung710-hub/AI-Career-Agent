import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import build_engine, get_db
from app.main import app
from app.models import Base


@pytest.fixture
def client():
    engine = build_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def registered(client):
    response = client.post("/api/v1/auth/register", json={
        "email": "career-test@example.invalid", "password": "test-password-123",
    })
    assert response.status_code == 201
    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def make_resume(fact_id: str, *, text="协助整理课程资料"):
    return {
        "basics": {"name": "", "email": "", "phone": "", "location": ""},
        "summary": {"text": text, "fact_ids": [fact_id]},
        "education": [], "experience": [], "skills": [], "interests": [],
    }
