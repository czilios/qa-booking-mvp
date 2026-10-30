from datetime import date
from html import unescape
from urllib.parse import unquote

from app.repositories.cottage_repository import CottageRepository
from app.repositories.reservation_repository import ReservationRepository
from app.main import estimate_inquiry_stay_price


def test_inquiry_price_estimate_uses_website_season_and_weekend_rates():
    assert estimate_inquiry_stay_price(
        date(2026, 7, 10), date(2026, 7, 17)
    ) == 2400
    assert estimate_inquiry_stay_price(
        date(2026, 6, 4), date(2026, 6, 7)
    ) == 1350


def test_web_inquiry_is_saved_without_creating_a_reservation(
    api_client,
    db_connection,
    created_web_inquiry_cleanup,
):
    with db_connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS count FROM reservations WHERE check_in = %s AND check_out = %s",
            (date(2027, 7, 10), date(2027, 7, 17)),
        )
        reservation_count_before = cursor.fetchone()["count"]

    response = api_client.post(
        "/api/inquiries",
        json={
            "full_name": "Jan Kowalski",
            "phone": "+48600100200",
            "email": "jan@example.com",
            "check_in": "2027-07-10",
            "check_out": "2027-07-17",
            "guests_count": 4,
            "preferred_cottage_id": None,
            "message": "Proszę o informację o terminie.",
            "consent": True,
            "website": "",
        },
    )

    assert response.status_code == 201
    body = response.json()
    created_web_inquiry_cleanup.append(body["id"])
    assert body["status"] == "NEW"
    assert body["availability"] == "AVAILABLE"

    with db_connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, status, check_in, check_out FROM web_inquiries WHERE id = %s",
            (body["id"],),
        )
        inquiry = cursor.fetchone()
        cursor.execute(
            "SELECT COUNT(*) AS count FROM reservations WHERE check_in = %s AND check_out = %s",
            (date(2027, 7, 10), date(2027, 7, 17)),
        )
        reservation_count = cursor.fetchone()["count"]

    assert inquiry["status"] == "NEW"
    assert inquiry["check_in"] == date(2027, 7, 10)
    assert inquiry["check_out"] == date(2027, 7, 17)
    assert reservation_count == reservation_count_before

    admin_response = api_client.get("/ui/inquiries")
    assert admin_response.status_code == 200
    assert "Jan Kowalski" in admin_response.text


def test_web_inquiry_rate_limit_returns_429_after_five_requests(
    api_client,
    created_web_inquiry_cleanup,
):
    payload = {
        "full_name": "Jan Kowalski",
        "phone": "+48600100200",
        "email": "jan@example.com",
        "check_in": "2027-07-10",
        "check_out": "2027-07-17",
        "guests_count": 4,
        "consent": True,
    }

    responses = [
        api_client.post("/api/inquiries", json=payload)
        for _ in range(6)
    ]

    for response in responses[:5]:
        assert response.status_code == 201
        created_web_inquiry_cleanup.append(response.json()["id"])

    assert responses[5].status_code == 429


def test_operator_can_mark_web_inquiry_in_progress(
    api_client,
    db_connection,
    created_web_inquiry_cleanup,
):
    response = api_client.post(
        "/api/inquiries",
        json={
            "full_name": "Jan Kowalski",
            "phone": "+48600100200",
            "email": "jan@example.com",
            "check_in": "2027-07-10",
            "check_out": "2027-07-17",
            "guests_count": 2,
            "consent": True,
        },
    )
    created_web_inquiry_cleanup.append(response.json()["id"])
    inquiry_id = response.json()["id"]

    status_response = api_client.post(
        f"/ui/inquiries/{inquiry_id}/status",
        data={"status": "IN_PROGRESS"},
        follow_redirects=False,
    )

    assert status_response.status_code == 303
    assert f"#inquiry-{inquiry_id}" in status_response.headers["location"]
    with db_connection.cursor() as cursor:
        cursor.execute(
            "SELECT status FROM web_inquiries WHERE id = %s",
            (inquiry_id,),
        )
        assert cursor.fetchone()["status"] == "IN_PROGRESS"

    panel_response = api_client.get(status_response.headers["location"])
    assert panel_response.status_code == 200
    assert "mailto:" not in panel_response.text
    assert f'href="/ui/inquiries/{inquiry_id}/template"' in panel_response.text
    assert "Szablon" in panel_response.text

    template_response = api_client.get(f"/ui/inquiries/{inquiry_id}/template")
    assert template_response.status_code == 200
    assert 'name="total_amount"' in template_response.text
    assert 'name="deposit_amount"' in template_response.text
    assert 'value="2400.00"' in template_response.text
    assert 'value="720.00"' in template_response.text
    assert "Domek" in template_response.text

    generated_response = api_client.get(
        f"/ui/inquiries/{inquiry_id}/template",
        params={
            "total_amount": "2400.00",
            "deposit_amount": "720.00",
            "cottage": "Domek 2",
        },
    )
    assert generated_response.status_code == 200
    assert "2 400,00 zł" in generated_response.text
    assert "720,00 zł" in generated_response.text
    assert "Domek 2" in generated_response.text
    assert "62 1050 1520 1000 0091 3978 0382" in generated_response.text
    assert "Dzień dobry Jan Kowalski" in generated_response.text
    assert "48 godzin od wysłania tej wiadomości" in generated_response.text
    assert "przesłanie potwierdzenia wpłaty" in generated_response.text
    assert "3 zł za osobę za noc" in generated_response.text
    assert "25 zł/doba" in generated_response.text


def test_operator_sending_offer_creates_pending_reservation_and_blocks_cottage(
    api_client,
    db_connection,
    created_reservation_cleanup,
    created_web_inquiry_cleanup,
):
    inquiry_response = api_client.post(
        "/api/inquiries",
        json={
            "full_name": "Anna Nowak",
            "phone": "+48600100300",
            "email": "anna@example.com",
            "check_in": "2050-07-10",
            "check_out": "2050-07-17",
            "guests_count": 2,
            "consent": True,
        },
    )
    inquiry_id = inquiry_response.json()["id"]
    created_web_inquiry_cleanup.append(inquiry_id)
    with db_connection.cursor() as cursor:
        cursor.execute(
            "SELECT available_cottage_ids FROM web_inquiries WHERE id = %s",
            (inquiry_id,),
        )
        cottage_id = int(cursor.fetchone()["available_cottage_ids"].split(",")[0])

    api_client.post(
        f"/ui/inquiries/{inquiry_id}/status",
        data={"status": "IN_PROGRESS"},
    )
    response = api_client.post(
        f"/ui/inquiries/{inquiry_id}/send-payment-request",
        data={
            "cottage_id": cottage_id,
            "total_amount": "2400.00",
            "deposit_amount": "720.00",
            "check_in": "2050-07-10",
            "check_out": "2050-07-17",
            "confirm_sent": "true",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    reservation_id = int(
        response.headers["location"].split("reservation_id=")[1].split("#")[0]
    )
    created_reservation_cleanup["reservation_ids"].append(reservation_id)
    with db_connection.cursor() as cursor:
        cursor.execute(
            "SELECT customer_id, cottage_id, check_in, check_out, status, total_amount, deposit_amount, expires_at "
            "FROM reservations WHERE id = %s",
            (reservation_id,),
        )
        reservation = cursor.fetchone()
        created_reservation_cleanup["customer_ids"].append(reservation["customer_id"])
        cursor.execute(
            "SELECT type, status, amount, due_at FROM payments WHERE reservation_id = %s",
            (reservation_id,),
        )
        payment = cursor.fetchone()
        cursor.execute(
            "SELECT status, reservation_id FROM web_inquiries WHERE id = %s",
            (inquiry_id,),
        )
        inquiry = cursor.fetchone()

    assert reservation["cottage_id"] == cottage_id
    assert reservation["status"] == "PENDING"
    assert str(reservation["total_amount"]) == "2400.00"
    assert str(reservation["deposit_amount"]) == "720.00"
    assert reservation["expires_at"] is not None
    assert payment["type"] == "DEPOSIT"
    assert payment["status"] == "UNPAID"
    assert str(payment["amount"]) == "720.00"
    assert payment["due_at"] == reservation["expires_at"]
    assert inquiry["status"] == "CONVERTED"
    assert inquiry["reservation_id"] == reservation_id

    panel_response = api_client.get(response.headers["location"])
    assert panel_response.status_code == 200
    assert f"Rezerwacja #{reservation_id}" in panel_response.text
    assert "PENDING" in panel_response.text

    duplicate_response = api_client.post(
        f"/ui/inquiries/{inquiry_id}/send-payment-request",
        data={
            "cottage_id": cottage_id,
            "total_amount": "2400.00",
            "deposit_amount": "720.00",
            "check_in": "2050-07-10",
            "check_out": "2050-07-17",
            "confirm_sent": "true",
        },
    )
    assert duplicate_response.status_code == 409

    availability_response = api_client.get(
        "/api/availability",
        params={
            "check_in": "2050-07-10",
            "check_out": "2050-07-17",
            "guests_count": 2,
        },
    )
    assert cottage_id not in availability_response.json()["cottages"]

    second_inquiry = api_client.post(
        "/api/inquiries",
        json={
            "full_name": "Karol Nowy",
            "phone": "+48600100400",
            "email": "karol@example.com",
            "check_in": "2050-07-10",
            "check_out": "2050-07-17",
            "guests_count": 2,
            "preferred_cottage_id": cottage_id,
            "consent": True,
        },
    )
    created_web_inquiry_cleanup.append(second_inquiry.json()["id"])
    assert second_inquiry.json()["preferred_cottage_available"] is False

    with db_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE reservations SET expires_at = DATE_SUB(NOW(), INTERVAL 1 MINUTE) WHERE id = %s",
            (reservation_id,),
        )
    expired_availability = api_client.get(
        "/api/availability",
        params={
            "check_in": "2050-07-10",
            "check_out": "2050-07-17",
            "guests_count": 2,
        },
    )
    assert cottage_id in expired_availability.json()["cottages"]
    with db_connection.cursor() as cursor:
        cursor.execute("SELECT status FROM reservations WHERE id = %s", (reservation_id,))
        assert cursor.fetchone()["status"] == "EXPIRED"


def test_honeypot_submission_is_acknowledged_without_being_saved(
    api_client,
    db_connection,
):
    with db_connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS count FROM web_inquiries")
        inquiry_count_before = cursor.fetchone()["count"]

    response = api_client.post(
        "/api/inquiries",
        json={
            "full_name": "Bot Example",
            "phone": "+48600100200",
            "email": "bot@example.com",
            "check_in": "2027-07-10",
            "check_out": "2027-07-17",
            "guests_count": 4,
            "consent": True,
            "website": "filled by bot",
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] is None

    with db_connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS count FROM web_inquiries")
        assert cursor.fetchone()["count"] == inquiry_count_before


def test_availability_can_filter_by_guest_capacity(api_client):
    response = api_client.get(
        "/api/availability",
        params={
            "check_in": "2027-07-10",
            "check_out": "2027-07-17",
            "guests_count": 20,
        },
    )

    assert response.status_code == 200
    assert response.json()["cottages"] == []
    assert response.json()["available"] is False


def test_inquiry_is_kept_when_no_cottage_can_fit_party(
    api_client,
    created_web_inquiry_cleanup,
):
    response = api_client.post(
        "/api/inquiries",
        json={
            "full_name": "Anna Nowak",
            "phone": "+48600100201",
            "email": "anna@example.com",
            "check_in": "2027-07-10",
            "check_out": "2027-07-17",
            "guests_count": 20,
            "consent": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["availability"] == "UNAVAILABLE"
    created_web_inquiry_cleanup.append(response.json()["id"])


def test_inquiry_distinguishes_property_and_preferred_cottage_availability(
    api_client,
    db_connection,
    created_reservation_cleanup,
    created_web_inquiry_cleanup,
):
    reservation_id = ReservationRepository(db_connection).create(
        cottage_id=2,
        source_id=1,
        check_in=date(2050, 7, 10),
        check_out=date(2050, 7, 17),
        guests_count=2,
        status="CONFIRMED",
        is_test_data=False,
    )
    created_reservation_cleanup["reservation_ids"].append(reservation_id)

    response = api_client.post(
        "/api/inquiries",
        json={
            "full_name": "Jan Kowalski",
            "phone": "+48600100200",
            "email": "jan@example.com",
            "check_in": "2050-07-10",
            "check_out": "2050-07-17",
            "guests_count": 2,
            "preferred_cottage_id": 2,
            "consent": True,
        },
    )
    created_web_inquiry_cleanup.append(response.json()["id"])

    assert response.status_code == 201
    assert response.json()["availability"] == "AVAILABLE"
    assert response.json()["preferred_cottage_available"] is False

    with db_connection.cursor() as cursor:
        cursor.execute(
            "SELECT available_cottage_ids FROM web_inquiries WHERE id = %s",
            (response.json()["id"],),
        )
        assert "2" not in cursor.fetchone()["available_cottage_ids"].split(",")

    status_response = api_client.post(
        f"/ui/inquiries/{response.json()['id']}/status",
        data={"status": "IN_PROGRESS"},
        follow_redirects=False,
    )
    panel_response = api_client.get(status_response.headers["location"])
    template_response = api_client.get(
        f"/ui/inquiries/{response.json()['id']}/template",
        params={
            "total_amount": "1000.00",
            "deposit_amount": "300.00",
            "cottage": "Domek 6",
        },
    )
    email_template = unquote(unescape(template_response.text))
    assert "Domek 2 jest niedostępny." in email_template
    assert "Domek 6" in email_template


def test_template_suggests_nearby_dates_when_all_cottages_are_booked(
    api_client,
    db_connection,
    created_reservation_cleanup,
    created_web_inquiry_cleanup,
):
    cottage_ids = CottageRepository(db_connection).get_active_cottage_ids(
        guests_count=2
    )
    for cottage_id in cottage_ids:
        reservation_id = ReservationRepository(db_connection).create(
            cottage_id=cottage_id,
            source_id=1,
            check_in=date(2050, 7, 10),
            check_out=date(2050, 7, 17),
            guests_count=2,
            status="CONFIRMED",
            is_test_data=False,
        )
        created_reservation_cleanup["reservation_ids"].append(reservation_id)

    response = api_client.post(
        "/api/inquiries",
        json={
            "full_name": "Jan Kowalski",
            "phone": "+48600100200",
            "email": "jan@example.com",
            "check_in": "2050-07-10",
            "check_out": "2050-07-17",
            "guests_count": 2,
            "consent": True,
        },
    )
    created_web_inquiry_cleanup.append(response.json()["id"])

    template_response = api_client.get(
        f"/ui/inquiries/{response.json()['id']}/template"
    )

    assert template_response.status_code == 200
    assert "W podanym terminie żaden domek nie jest obecnie dostępny" in template_response.text
    assert "Możliwe alternatywy o tej samej długości pobytu" in template_response.text
    assert "2050-07-03 – 2050-07-10" in template_response.text
    assert "Przygotuj szablon na ten termin" in template_response.text
    assert "62 1050 1520 1000 0091 3978 0382" not in template_response.text


def test_availability_rate_limit_returns_429_after_thirty_requests(api_client):
    responses = [
        api_client.get(
            "/api/availability",
            params={
                "check_in": "2027-07-10",
                "check_out": "2027-07-17",
            },
        )
        for _ in range(31)
    ]

    assert all(response.status_code == 200 for response in responses[:30])
    assert responses[30].status_code == 429


def test_local_website_origin_can_call_inquiry_api(api_client):
    response = api_client.options(
        "/api/inquiries",
        headers={
            "Origin": "http://127.0.0.1:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5500"
