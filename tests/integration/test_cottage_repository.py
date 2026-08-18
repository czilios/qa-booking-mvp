from app.repositories.cottage_repository import CottageRepository


def test_get_active_cottage_ids(db_connection):
    repository = CottageRepository(db_connection)

    cottage_ids = repository.get_active_cottage_ids()

    assert cottage_ids == [1, 2, 3, 4, 5, 6]

def test_get_cottage_by_id(db_connection):
    repository = CottageRepository(db_connection)

    cottage = repository.get_by_id(1)

    assert cottage["id"] == 1
    assert cottage["capacity"] == 4
    assert cottage["active"] == 1