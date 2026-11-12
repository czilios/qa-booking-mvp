import pytest

from app import reservation_service


class FakeReservationRepository:
    def __init__(self, connection, events, current_cottage_id):
        self.events = events
        self.current_cottage_id = current_cottage_id
        self.updated = False

    def get_by_id(self, reservation_id):
        self.events.append(("read_reservation", reservation_id))
        return {"id": reservation_id, "cottage_id": 2}

    def get_by_id_for_update(self, reservation_id):
        self.events.append(("lock_reservation", reservation_id))
        return {"id": reservation_id, "cottage_id": self.current_cottage_id}

    def update(self, **kwargs):
        self.events.append(("update_reservation", kwargs["reservation_id"]))
        self.updated = True


class FakeCottageRepository:
    def __init__(self, connection, events):
        self.events = events

    def get_by_id_for_update(self, cottage_id):
        self.events.append(("lock_cottage", cottage_id))
        return {"id": cottage_id, "capacity": 4, "active": True}


class FakeAvailabilityService:
    def __init__(self, **kwargs):
        self.cottage_repository = kwargs["cottage_repository"]
        self.events = self.cottage_repository.events

    def get_available_cottages(self, **kwargs):
        self.events.append(("check_availability", kwargs["reservation_cottage_id"]))
        return [kwargs["reservation_cottage_id"]]


def _configure_fakes(monkeypatch, current_cottage_id=2):
    events = []

    monkeypatch.setattr(
        reservation_service,
        "ReservationRepository",
        lambda connection: FakeReservationRepository(
            connection, events, current_cottage_id
        ),
    )
    monkeypatch.setattr(
        reservation_service,
        "CottageRepository",
        lambda connection: FakeCottageRepository(connection, events),
    )
    monkeypatch.setattr(reservation_service, "BlockRepository", lambda connection: object())
    monkeypatch.setattr(reservation_service, "AvailabilityService", FakeAvailabilityService)
    return events


def test_update_locks_both_cottages_in_id_order_before_reservation(monkeypatch):
    events = _configure_fakes(monkeypatch)

    reservation_service.update_reservation(
        connection=object(),
        reservation_id=42,
        cottage_id=1,
        source_id=1,
        check_in="2030-08-01",
        check_out="2030-08-05",
        guests_count=2,
    )

    assert events == [
        ("read_reservation", 42),
        ("lock_cottage", 1),
        ("lock_cottage", 2),
        ("lock_reservation", 42),
        ("check_availability", 1),
        ("update_reservation", 42),
    ]


def test_update_rejects_source_cottage_change_after_locks(monkeypatch):
    events = _configure_fakes(monkeypatch, current_cottage_id=3)

    with pytest.raises(ValueError, match="Reservation changed while waiting"):
        reservation_service.update_reservation(
            connection=object(),
            reservation_id=42,
            cottage_id=1,
            source_id=1,
            check_in="2030-08-01",
            check_out="2030-08-05",
            guests_count=2,
        )

    assert events == [
        ("read_reservation", 42),
        ("lock_cottage", 1),
        ("lock_cottage", 2),
        ("lock_reservation", 42),
    ]
