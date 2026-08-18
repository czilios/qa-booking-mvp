from app.repositories.cottage_repository import CottageRepository


def test_get_active_cottage_ids(db_connection):
    repository = CottageRepository(db_connection)

    cottage_ids = repository.get_active_cottage_ids()

    assert cottage_ids == [1, 2, 3, 4, 5, 6]