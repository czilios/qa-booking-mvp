from datetime import date

from app.repositories.block_repository import BlockRepository


def test_get_active_blocks(db_connection):
    repository = BlockRepository(db_connection)

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO blocks (
                cottage_id,
                start_date,
                end_date,
                reason
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                1,
                date(2027, 7, 10),
                date(2027, 7, 17),
                "Test block",
            ),
        )

    blocks = repository.get_active_blocks()

    assert len(blocks) == 1
    assert blocks[0]["cottage_id"] == 1
    assert blocks[0]["start_date"] == date(2027, 7, 10)
    assert blocks[0]["end_date"] == date(2027, 7, 17)