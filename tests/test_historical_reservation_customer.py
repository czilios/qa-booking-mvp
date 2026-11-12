from fastapi.testclient import TestClient

from app import main


def test_historical_reservation_routes_are_disabled(monkeypatch):
    def unexpected_database_access():
        raise AssertionError("Disabled historical routes must not open a database connection")

    monkeypatch.setattr(main, "get_connection", unexpected_database_access)
    client = TestClient(main.app)

    assert client.get("/ui/reservations/historical").status_code == 404
    assert client.post("/ui/reservations/historical").status_code == 404
