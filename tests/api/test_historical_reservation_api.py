from fastapi.testclient import TestClient

from app.main import app


def test_historical_get_form_is_disabled():
    response = TestClient(app).get("/ui/reservations/historical")

    assert response.status_code == 404


def test_historical_post_endpoint_is_disabled():
    response = TestClient(app).post(
        "/ui/reservations/historical",
        data={
            "cottage_id": "1",
            "source_id": "1",
            "check_in": "2026-07-10",
            "check_out": "2026-07-17",
            "guests_count": "2",
            "total_amount": "2100.00",
        },
    )

    assert response.status_code == 404
