import json
from fastapi.testclient import TestClient

from idp.api.main import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"


def test_extract_rejects_non_pdf():
    res = client.post("/extract", files={"file": ("test.txt", b"hello", "text/plain")})
    assert res.status_code == 400
