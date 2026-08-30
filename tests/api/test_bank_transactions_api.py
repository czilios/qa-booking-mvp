from datetime import date
from decimal import Decimal

from app.repositories.bank_transaction_repository import (
    BankTransactionRepository,
)

def test_bank_transactions_ui_get(
    api_client,
):
    response = api_client.get("/ui/bank-transactions")

    assert response.status_code == 200
    assert "Dodaj wpływ" in response.text
    assert "Data wpływu" in response.text
    assert "Źródło" in response.text
    assert "Domek" in response.text
    assert "Kwota" in response.text

def test_bank_transactions_ui_get_for_month(
    api_client,
    db_connection,
    created_bank_transaction_cleanup,
):
    repository = BankTransactionRepository(db_connection)

    july_id = repository.create(
        transaction_date=date(2026, 7, 15),
        source_id=1,
        cottage_id=2,
        amount=Decimal("500.00"),
        notes= "testing",
    )

    august_id = repository.create(
        transaction_date=date(2026, 8, 15),
        source_id=2,
        cottage_id=2,
        amount=Decimal("2427.05"),
        notes= "testing",
    )

    created_bank_transaction_cleanup.extend(
        [july_id, august_id]
    )

    db_connection.commit()

    response = api_client.get(
    "/ui/bank-transactions?month=8&year=2026&notes=testing"
)

    assert response.status_code == 200
    assert "2 427,05" in response.text
    assert "500,00" not in response.text

def test_bank_transactions_ui_get_for_month_with_no_transactions(
    api_client,
):
    response = api_client.get(
        "/ui/bank-transactions?month=9&year=2026&notes=testing"
    )

    assert response.status_code == 200
    assert "Brak wpływów" in response.text

def test_bank_transactions_ui_post_creates_transaction(
    api_client,
    db_connection,
    created_bank_transaction_cleanup,
):
    response = api_client.post(
        "/ui/bank-transactions",
        data={
            "transaction_date": "2026-08-28",
            "source_id": "1",
            "cottage_id": "3",
            "amount": "800.00",
            "description": "Przelew Direct",
            "notes": "UI test",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/ui/bank-transactions?month=8&year=2026"
    )

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                transaction_date,
                source_id,
                cottage_id,
                amount,
                description,
                notes
            FROM bank_transactions
            WHERE transaction_date = %s
              AND source_id = %s
              AND cottage_id = %s
              AND amount = %s
              AND description = %s
              AND notes = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                date(2026, 8, 28),
                1,
                3,
                Decimal("800.00"),
                "Przelew Direct",
                "UI test",
            ),
        )

        transaction = cursor.fetchone()

    assert transaction is not None
    assert transaction["transaction_date"] == date(2026, 8, 28)
    assert transaction["source_id"] == 1
    assert transaction["cottage_id"] == 3
    assert transaction["amount"] == Decimal("800.00")
    assert transaction["description"] == "Przelew Direct"
    assert transaction["notes"] == "UI test"

    created_bank_transaction_cleanup.append(transaction["id"])

def test_bank_transactions_ui_post_creates_transaction_with_no_cottage(
    api_client,
    db_connection,
    created_bank_transaction_cleanup,
):
    response = api_client.post(
        "/ui/bank-transactions",
        data={
            "transaction_date": "2026-08-28",
            "source_id": "2",
            "amount": "1500.00",
            "description": "Przelew PayPal",
            "notes": "UI test no cottage",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/ui/bank-transactions?month=8&year=2026"
    )
    with db_connection.cursor() as cursor:
        cursor.execute(
        """
        SELECT
            id,
            transaction_date,
            source_id,
            cottage_id,
            amount,
            description,
            notes
        FROM bank_transactions
        WHERE transaction_date = %s
          AND source_id = %s
          AND cottage_id IS NULL
          AND amount = %s
          AND description = %s
          AND notes = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            date(2026, 8, 28),
            2,
            Decimal("1500.00"),
            "Przelew PayPal",
            "UI test no cottage",
        ),
    )
        transaction = cursor.fetchone()
        assert transaction is not None
        assert transaction["transaction_date"] == date(2026, 8, 28)
        assert transaction["source_id"] == 2
        assert transaction["cottage_id"] is None
        assert transaction["amount"] == Decimal("1500.00")
        assert transaction["description"] == "Przelew PayPal"
        assert transaction["notes"] == "UI test no cottage"

        created_bank_transaction_cleanup.append(transaction["id"])   

def test_bank_transactions_ui_post_rejects_zero_amount(
    api_client,
):
    response = api_client.post(
        "/ui/bank-transactions",
        data={
            "transaction_date": "2026-08-28",
            "source_id": "1",
            "cottage_id": "3",
            "amount": "0.00",
            "description": "Invalid transaction",
            "notes": "Negative UI test",
        },
    )

    assert response.status_code == 400

def test_bank_transactions_ui_post_rejects_negative_amount(
    api_client,
):
    response = api_client.post(
        "/ui/bank-transactions",
        data={
            "transaction_date": "2026-08-28",
            "source_id": "1",
            "cottage_id": "3",
            "amount": "-213.00",
            "description": "Invalid transaction",
            "notes": "Negative UI test",
        },
    )

    assert response.status_code == 400