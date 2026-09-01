from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.api as api_module
from app.api import app


def test_health():
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok"
    }


def test_admin_run_scan_rejects_missing_token(
    monkeypatch,
):
    monkeypatch.setattr(
        api_module,
        "get_settings",
        lambda: SimpleNamespace(
            admin_token="test-admin-token"
        ),
    )

    client = TestClient(app)

    response = client.post(
        "/admin/run-scan"
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "unauthorized"
    }


def test_admin_run_scan_rejects_wrong_token(
    monkeypatch,
):
    monkeypatch.setattr(
        api_module,
        "get_settings",
        lambda: SimpleNamespace(
            admin_token="test-admin-token"
        ),
    )

    client = TestClient(app)

    response = client.post(
        "/admin/run-scan",
        headers={
            "X-Admin-Token": "wrong-token"
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "unauthorized"
    }


def test_admin_run_scan_rejects_when_admin_token_not_configured(
    monkeypatch,
):
    monkeypatch.setattr(
        api_module,
        "get_settings",
        lambda: SimpleNamespace(
            admin_token=""
        ),
    )

    client = TestClient(app)

    response = client.post(
        "/admin/run-scan",
        headers={
            "X-Admin-Token": "anything"
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "unauthorized"
    }


def test_admin_run_scan_accepts_correct_token(
    monkeypatch,
):
    monkeypatch.setattr(
        api_module,
        "get_settings",
        lambda: SimpleNamespace(
            admin_token="test-admin-token"
        ),
    )

    class FakeRunner:
        def run(self):
            return None

    monkeypatch.setattr(
        api_module,
        "LiveRunner",
        FakeRunner,
    )

    client = TestClient(app)

    response = client.post(
        "/admin/run-scan",
        headers={
            "X-Admin-Token":
                "test-admin-token"
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "candidate": None,
    }
