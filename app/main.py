from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from calendar import monthrange
import os
import re

from fastapi import Depends, FastAPI, HTTPException, Request, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from httpx2 import request
from pydantic import BaseModel, Field, field_validator
import calendar


from app.reservation_service import create_reservation, generate_bank_statement_report, update_reservation

from app.payment_service import create_payment, mark_payment_as_paid, generate_payment_report
from app.reservation_service import cancel_reservation, generate_overall_report, create_historical_reservation
from app.customer_service import create_customer, get_customer, update_customer
from app.availability_service import AvailabilityService
from app.bank_statement_service import BankStatementReportService
from app.bank_transaction_service import (
    create_bank_transaction,
    get_direct_pending_deposit,
    list_bank_transactions,
    sum_bank_transactions,
)
from app.overall_report_service import (
    generate_cash_flow_report,
    generate_overall_report,
)
from app.accounting_report_service import generate_accounting_report, generate_accounting_reports
from app.sales_report_service import generate_sales_report
from app.repositories.bank_transaction_repository import BankTransactionRepository
from app.repositories.block_repository import BlockRepository
from app.repositories.cottage_repository import CottageRepository
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.web_inquiry_repository import WebInquiryRepository
from app.rate_limiter import SlidingWindowRateLimiter

from app.database import get_connection



app = FastAPI()

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "PUBLIC_SITE_ORIGINS",
        "http://127.0.0.1:5500,http://localhost:5500",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

rate_limiter = SlidingWindowRateLimiter()

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

templates = Jinja2Templates(directory="app/templates")


def calculate_deposit(total_amount: Decimal) -> Decimal:
    return (total_amount * Decimal("0.30")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def estimate_inquiry_stay_price(check_in: date, check_out: date) -> Decimal | None:
    nightly_rates = {
        5: Decimal("280.00"),
        6: Decimal("280.00"),
        7: Decimal("300.00"),
        8: Decimal("300.00"),
        9: Decimal("280.00"),
    }
    long_weekend_nights = set()
    for year in range(check_in.year, check_out.year + 1):
        corpus_christi = _easter_sunday(year) + timedelta(days=60)
        long_weekend_nights.update(
            date(year, 5, day) for day in (1, 2, 3)
        )
        long_weekend_nights.update(
            corpus_christi + timedelta(days=offset) for offset in range(3)
        )
    amount = Decimal("0.00")
    night = check_in
    while night < check_out:
        rate = (
            Decimal("450.00")
            if night.weekday() in (4, 5) or night in long_weekend_nights
            else nightly_rates.get(night.month, Decimal("300.00"))
        )
        amount += rate
        night += timedelta(days=1)
    return amount


def inquiry_price_uses_default_rate(check_in: date, check_out: date) -> bool:
    nightly_rates = {5, 6, 7, 8, 9}
    premium_nights = set()
    for year in range(check_in.year, check_out.year + 1):
        corpus_christi = _easter_sunday(year) + timedelta(days=60)
        premium_nights.update(date(year, 5, day) for day in (1, 2, 3))
        premium_nights.update(
            corpus_christi + timedelta(days=offset) for offset in range(3)
        )

    night = check_in
    while night < check_out:
        if (
            night.month not in nightly_rates
            and night.weekday() not in (4, 5)
            and night not in premium_nights
        ):
            return True
        night += timedelta(days=1)
    return False


def _easter_sunday(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)

class CustomerCreate(BaseModel):
    phone: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None

class ReservationCreate(BaseModel):
    customer_id: int | None = None
    cottage_id: int
    source_id: int
    check_in: date
    check_out: date
    guests_count: int = Field(gt=0)
    total_amount: Decimal | None = None

class ReservationUpdate(BaseModel):
    cottage_id: int
    source_id: int
    check_in: date
    check_out: date
    guests_count: int = Field(gt=0)

class PaymentCreate(BaseModel):
    reservation_id: int
    payment_type: str
    amount: Decimal
    due_at: datetime | None = None

class PaymentPaid(BaseModel):
    paid_at: datetime


class WebInquiryCreate(BaseModel):
    full_name: str = Field(min_length=3, max_length=200)
    phone: str = Field(min_length=7, max_length=30)
    email: str = Field(min_length=5, max_length=255)
    check_in: date
    check_out: date
    guests_count: int = Field(gt=0, le=20)
    preferred_cottage_id: int | None = None
    message: str | None = Field(default=None, max_length=2000)
    consent: bool
    website: str | None = None

    @field_validator("full_name", "phone", "email")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field is required")
        return value

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Invalid email address")
        return value
    

def get_db_connection():
    connection = get_connection()

    try:
        yield connection
    finally:
        connection.close()


def get_api_write_connection():
    connection = get_connection()

    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def expire_payment_holds(db_connection) -> int:
    expired_count = ReservationRepository(db_connection).expire_pending_reservations(
        datetime.now()
    )
    if expired_count:
        db_connection.commit()
    return expired_count


def get_availability_service(
    db_connection=Depends(get_db_connection),
):
    return AvailabilityService(
        reservation_repository=ReservationRepository(db_connection),
        block_repository=BlockRepository(db_connection),
        cottage_repository=CottageRepository(db_connection),
    )

def get_reservation_repository(
    db_connection=Depends(get_db_connection),
):
    return ReservationRepository(db_connection)

MONTH_NAMES_PL = {
    1: "Styczeń",
    2: "Luty",
    3: "Marzec",
    4: "Kwiecień",
    5: "Maj",
    6: "Czerwiec",
    7: "Lipiec",
    8: "Sierpień",
    9: "Wrzesień",
    10: "Październik",
    11: "Listopad",
    12: "Grudzień",
}

MONTH_NAMES_PL_GENITIVE = {
    1: "stycznia",
    2: "lutego",
    3: "marca",
    4: "kwietnia",
    5: "maja",
    6: "czerwca",
    7: "lipca",
    8: "sierpnia",
    9: "września",
    10: "października",
    11: "listopada",
    12: "grudnia",
}

@app.get("/")
def read_root():
    return {"message": "QA Booking API"}


@app.get("/api/availability")
def check_availability(
    request: Request,
    check_in: date,
    check_out: date,
    guests_count: int | None = Query(default=None, gt=0, le=20),
    db_connection=Depends(get_db_connection),
    availability_service=Depends(get_availability_service),
):
    enforce_rate_limit(
        request=request,
        action="availability",
        limit=30,
        window_seconds=600,
    )

    if check_out <= check_in:
        raise HTTPException(
            status_code=400,
            detail="check_out must be after check_in",
        )

    expire_payment_holds(db_connection)

    available_cottages = availability_service.get_available_cottages(
        check_in=check_in,
        check_out=check_out,
        guests_count=guests_count,
    )

    return {
        "check_in": check_in,
        "check_out": check_out,
        "cottages": available_cottages,
        "available": bool(available_cottages),
    }


def enforce_rate_limit(
    request: Request,
    action: str,
    limit: int,
    window_seconds: int,
) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(
        key=f"{action}:{client_ip}",
        limit=limit,
        window_seconds=window_seconds,
    ):
        raise HTTPException(
            status_code=429,
            detail="Zbyt wiele prób. Spróbuj ponownie za kilka minut.",
        )


@app.post("/api/inquiries", status_code=201)
def create_web_inquiry_endpoint(
    inquiry: WebInquiryCreate,
    request: Request,
    db_connection=Depends(get_db_connection),
):
    if inquiry.check_out <= inquiry.check_in:
        raise HTTPException(
            status_code=400,
            detail="check_out must be after check_in",
        )

    enforce_rate_limit(
        request=request,
        action="inquiry",
        limit=5,
        window_seconds=900,
    )

    if inquiry.website:
        return {
            "id": None,
            "status": "NEW",
            "availability": "UNAVAILABLE",
        }

    if not inquiry.consent:
        raise HTTPException(
            status_code=422,
            detail="Consent is required",
        )

    expire_payment_holds(db_connection)
    availability_service = AvailabilityService(
        reservation_repository=ReservationRepository(db_connection),
        block_repository=BlockRepository(db_connection),
        cottage_repository=CottageRepository(db_connection),
    )
    available_cottages = availability_service.get_available_cottages(
        check_in=inquiry.check_in,
        check_out=inquiry.check_out,
        guests_count=inquiry.guests_count,
    )

    if inquiry.preferred_cottage_id is not None:
        preferred_cottage = CottageRepository(db_connection).get_by_id(
            inquiry.preferred_cottage_id
        )
        if preferred_cottage is None or not preferred_cottage["active"]:
            raise HTTPException(
                status_code=422,
                detail="Invalid preferred cottage",
            )

    repository = WebInquiryRepository(db_connection)
    try:
        inquiry_id = repository.create(
            full_name=inquiry.full_name,
            phone=inquiry.phone,
            email=inquiry.email,
            check_in=inquiry.check_in,
            check_out=inquiry.check_out,
            guests_count=inquiry.guests_count,
            preferred_cottage_id=inquiry.preferred_cottage_id,
            message=inquiry.message,
            availability_found=bool(available_cottages),
            available_cottage_ids=available_cottages,
        )
        db_connection.commit()
    except Exception:
        db_connection.rollback()
        raise

    return {
        "id": inquiry_id,
        "status": "NEW",
        "availability": "AVAILABLE" if available_cottages else "UNAVAILABLE",
        "preferred_cottage_available": (
            inquiry.preferred_cottage_id in available_cottages
            if inquiry.preferred_cottage_id is not None
            else None
        ),
    }

@app.get("/ui/reports/overall")
def overall_report_ui(
    request: Request,
    year: int = 2026,
    month: int = 7,
    db_connection=Depends(get_db_connection),
):
    if month < 0 or month > 12:
        raise HTTPException(
            status_code=400,
            detail="Invalid month",
        )

    if month == 0:
        start_date = date(year, 1, 1)
        end_date = date(year + 1, 1, 1)
    elif month == 12:
        start_date = date(year, 12, 1)
        end_date = date(year + 1, 1, 1)
    else:
        start_date = date(year, month, 1)
        end_date = date(year, month + 1, 1)

    report = generate_cash_flow_report(
        connection=db_connection,
        start_date=start_date,
        end_date=end_date,
    )

    return templates.TemplateResponse(
        request=request,
        name="overall_report.html",
        context={
            "year": year,
            "month": month,
            "reservations": report["reservations"],
            "transactions": report["transactions"],
            "total_amount": report["total_amount"],
        },
    )

@app.post("/api/reservations", status_code=201)
def create_reservation_endpoint(
    reservation: ReservationCreate,
    db_connection=Depends(get_api_write_connection, scope="function"),
):
    try:
        return create_reservation(
            connection=db_connection,
            customer_id=reservation.customer_id,
            cottage_id=reservation.cottage_id,
            source_id=reservation.source_id,
            check_in=reservation.check_in,
            check_out=reservation.check_out,
            guests_count=reservation.guests_count,
            total_amount=reservation.total_amount,
        )
    except ValueError as exc:
        if str(exc) == "Reservation not found":
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            )

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

@app.put("/api/reservations/{reservation_id}")
def update_reservation_endpoint(
    reservation_id: int,
    reservation: ReservationUpdate,
    db_connection=Depends(get_api_write_connection, scope="function"),
):
    if reservation.check_out <= reservation.check_in:
        raise HTTPException(
            status_code=400,
            detail="check_out must be after check_in",
        )

    try:
        update_reservation(
            connection=db_connection,
            reservation_id=reservation_id,
            cottage_id=reservation.cottage_id,
            source_id=reservation.source_id,
            check_in=reservation.check_in,
            check_out=reservation.check_out,
            guests_count=reservation.guests_count,
        )
    except ValueError as exc:
        if str(exc) == "Reservation not found":
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            )

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    return {"message": "Reservation updated"}

@app.get("/api/reservations/{reservation_id}")
def get_reservation_endpoint(
    reservation_id: int,
    db_connection=Depends(get_db_connection),
):
    repository = ReservationRepository(db_connection)

    reservation = repository.get_by_id(reservation_id)

    if reservation is None:
        raise HTTPException(
            status_code=404,
            detail="Reservation not found",
        )

    return reservation


@app.delete("/api/reservations/{reservation_id}", status_code=204)
def cancel_reservation_endpoint(
    reservation_id: int,
    db_connection=Depends(get_api_write_connection, scope="function"),
):
    try:
        cancel_reservation(
            connection=db_connection,
            reservation_id=reservation_id,
        )
    except ValueError as exc:
        if str(exc) == "Reservation not found":
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            )

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

@app.post("/api/payments", status_code=201)
def create_payment_endpoint(
    payment: PaymentCreate,
    db_connection=Depends(get_api_write_connection, scope="function"),
):
    try:
        return create_payment(
            connection=db_connection,
            reservation_id=payment.reservation_id,
            payment_type=payment.payment_type,
            amount=payment.amount,
            due_at=payment.due_at,
        )
    except ValueError as exc:
        if str(exc) == "Reservation not found":
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            )

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

@app.get("/api/payments/report")
def get_payment_report_endpoint(
    start_date: date,
    end_date: date,
    vat_rate: Decimal = Decimal("8"),
    source_code: str | None = None,
    db_connection=Depends(get_db_connection),
):
    if end_date <= start_date:
        raise HTTPException(
            status_code=400,
            detail="end_date must be after start_date",
        )

    return generate_payment_report(
        connection=db_connection,
        start_date=start_date,
        end_date=end_date,
        vat_rate=vat_rate,
        source_code=source_code,
    )

@app.get("/api/payments/{payment_id}")
def get_payment_endpoint(
    payment_id: int,
    db_connection=Depends(get_db_connection),
):
    repository = PaymentRepository(db_connection)

    payment = repository.get_payment_by_id(payment_id)

    if payment is None:
        raise HTTPException(
            status_code=404,
            detail="Payment not found",
        )

    return payment

@app.put("/api/payments/{payment_id}/paid")
def mark_payment_as_paid_endpoint(
    payment_id: int,
    payment: PaymentPaid,
    db_connection=Depends(get_api_write_connection, scope="function"),
):
    try:
        mark_payment_as_paid(
            connection=db_connection,
            payment_id=payment_id,
            paid_at=payment.paid_at,
        )
    except ValueError as exc:
        if str(exc) == "Payment not found":
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            )

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    return {"message": "Payment marked as paid"}

@app.post("/api/customers", status_code=201)
def create_customer_endpoint(
    customer: CustomerCreate,
    db_connection=Depends(get_api_write_connection, scope="function"),
):
    try:
        customer_id = create_customer(
            connection=db_connection,
            first_name=customer.first_name,
            last_name=customer.last_name,
            phone=customer.phone,
            email=customer.email,
        )

        repository = CustomerRepository(db_connection)

        return repository.get_by_id(customer_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
@app.get("/api/customers/{customer_id}")
def get_customer_endpoint(
    customer_id: int,
    db_connection=Depends(get_db_connection),
):
    try:
        return get_customer(
            connection=db_connection,
            customer_id=customer_id,
        )
    except ValueError as exc:
        if str(exc) == "Customer not found":
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
@app.put("/api/customers/{customer_id}")
def update_customer_endpoint(
    customer_id: int,
    customer: CustomerCreate,
    db_connection=Depends(get_api_write_connection, scope="function"),
):
    try:
        return update_customer(
            connection=db_connection,
            customer_id=customer_id,
            first_name=customer.first_name,
            last_name=customer.last_name,
            phone=customer.phone,
            email=customer.email,
        )
    except ValueError as exc:
        if str(exc) == "Customer not found":
            raise HTTPException(
                status_code=404,
                detail=str(exc),
            )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
    
@app.get("/ui")
def operator_ui(
    request: Request,
    check_in: date | None = None,
    check_out: date | None = None,
    cottage_id: int | None = None,
    reservation_created: int | None = None,
    reservation_error: str | None = None,
):
    connection = get_connection()

    try:
        cottage_repository = CottageRepository(connection)

        cottage_ids = cottage_repository.get_active_cottage_ids()

        available_cottages = None

        if check_in is not None and check_out is not None:
            if check_out <= check_in:
                raise HTTPException(
                    status_code=400,
                    detail="check_out must be after check_in",
                )

            availability_service = AvailabilityService(
                reservation_repository=ReservationRepository(connection),
                block_repository=BlockRepository(connection),
                cottage_repository=cottage_repository,
            )

            available_cottages = availability_service.get_available_cottages(
                check_in=check_in,
                check_out=check_out,
            )

    finally:
        connection.close()

    return templates.TemplateResponse(
    request=request,
    name="availability.html",
    context={
        "request": request,
        "check_in": check_in.isoformat() if check_in else "",
        "check_out": check_out.isoformat() if check_out else "",
        "cottage_ids": cottage_ids,
        "available_cottages": available_cottages,
        "selected_cottage_id": cottage_id,
        "reservation_created": reservation_created,
        "reservation_error": reservation_error,
        
    },
)

@app.post("/ui/reservations")
def create_ui_reservation(
    cottage_id: int = Form(...),
    check_in: date = Form(...),
    check_out: date = Form(...),
    phone: str = Form(...),
    guests_count: int = Form(...),
    db_connection=Depends(get_db_connection),
):
    try:
        customer_repository = CustomerRepository(db_connection)

        # Na tym etapie szukamy klienta po numerze telefonu.
        customer = customer_repository.get_by_phone(phone)

        if customer is None:
            customer_id = create_customer(
                connection=db_connection,
                phone=phone,
            )
        else:
            customer_id = customer["id"]

        reservation_id = create_reservation(
            connection=db_connection,
            customer_id=customer_id,
            cottage_id=cottage_id,
            source_id=1, #direct booking
            check_in=check_in,
            check_out=check_out,
            guests_count=guests_count,
        )
        db_connection.commit()

    except ValueError as exc:
        
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    return RedirectResponse(
    url=(
        f"/ui?"
        f"check_in={check_in}"
        f"&check_out={check_out}"
        f"&reservation_created={reservation_id}"
    ),
    status_code=303,
)

@app.get("/ui/reservations/search")
def search_reservation_ui(
    reservation_id: int,
):
    return RedirectResponse(
        url=f"/ui/reservations/{reservation_id}",
        status_code=303,
    )

@app.get("/ui/reservations/historical")
def historical_reservation_ui(
    request: Request,
):
    return templates.TemplateResponse(
        request=request,
        name="historical_reservation.html",
        context={
            "request": request,
        },
    )

@app.get("/ui/reservations/{reservation_id}")
def reservation_ui(
    request: Request,
    reservation_id: int,
):
    connection = get_connection()

    try:
        repository = ReservationRepository(connection)
        reservation = repository.get_by_id(reservation_id)

    finally:
        connection.close()

    if reservation is None:
        raise HTTPException(
            status_code=404,
            detail="Reservation not found",
        )

    return templates.TemplateResponse(
        request=request,
        name="reservation.html",
        context={
            "reservation": reservation,
        },
    )

@app.post("/ui/reservations/{reservation_id}/cancel")
def cancel_reservation_ui(
    reservation_id: int,
    db_connection=Depends(get_db_connection),
):
    try:
        cancel_reservation(
            connection=db_connection,
            reservation_id=reservation_id,
        )

        db_connection.commit()

    except ValueError as exc:
        db_connection.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    return RedirectResponse(
        url=f"/ui/reservations/{reservation_id}",
        status_code=303,
    )

@app.get("/api/bank-statement-report")
def get_bank_statement_report(
    start_date: date,
    end_date: date,
    db_connection=Depends(get_db_connection),
):
    return generate_bank_statement_report(
        connection=db_connection,
        start_date=start_date,
        end_date=end_date,
    )

@app.get("/ui/reports/bank-statement")
def bank_statement_report_ui(
    request: Request,
    year: int,
    db_connection=Depends(get_db_connection),
):
    bank_transaction_repository = BankTransactionRepository(
        db_connection
    )

    bank_statement_report_service = BankStatementReportService(
        payment_repository=None,
    )

    report = bank_statement_report_service.generate_bank_statement_report(
        bank_transaction_repository=bank_transaction_repository,
        year=year,
    )

    return templates.TemplateResponse(
        request=request,
        name="bank_statement_report.html",
        context={
            "request": request,
            "year": year,
            "months": report["months"],
            "total_gross": report["total_gross"],
            "total_net": report["total_net"],
            "total_vat": report["total_vat"],
        },
    )

@app.get("/api/overall-report")
def get_overall_report(
    start_date: date,
    end_date: date,
    db_connection=Depends(get_db_connection),
):
    return generate_cash_flow_report(
        connection=db_connection,
        start_date=start_date,
        end_date=end_date,
    )

@app.get("/ui/reports/overall")
def overall_report_ui(
    request: Request,
    month: int,
    year: int,
    db_connection=Depends(get_db_connection),
):
    if month == 0:
        start_date = date(year, 1, 1)
        end_date = date(year + 1, 1, 1)
    elif month == 12:
        start_date = date(year, 12, 1)
        end_date = date(year + 1, 1, 1)
    else:
        start_date = date(year, month, 1)
        end_date = date(year, month + 1, 1)

    report = generate_cash_flow_report(
        connection=db_connection,
        start_date=start_date,
        end_date=end_date,
    )

    return templates.TemplateResponse(
        "overall_report.html",
        {
            "request": request,
            "month": month,
            "year": year,
            "reservations": report["reservations"],
            "transactions": report["transactions"],
            "total_amount": report["total_amount"],
        },
    )


@app.post("/ui/reservations/historical")
def create_historical_ui_reservation(
    cottage_id: int = Form(...),
    source_id: int = Form(...),
    check_in: date = Form(...),
    check_out: date = Form(...),
    guests_count: int = Form(...),
    total_amount: Decimal = Form(...),
    phone: str | None = Form(None),
    notes: str | None = Form(None),
    commission_amount: Decimal | None = Form(None),
    db_connection=Depends(get_db_connection),
):
    customer_id = None

    if phone:
        customer_repository = CustomerRepository(db_connection)

        customer = customer_repository.get_by_phone(phone)

        if customer is None:
            customer_id = create_customer(
                connection=db_connection,
                phone=phone,
            )
        else:
            customer_id = customer["id"]

    try:
        reservation_id = create_historical_reservation(
            connection=db_connection,
            customer_id=customer_id,
            cottage_id=cottage_id,
            source_id=source_id,
            check_in=check_in,
            check_out=check_out,
            guests_count=guests_count,
            total_amount=total_amount,
            notes=notes,
            commission_amount=commission_amount,
        )

        db_connection.commit()

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    return RedirectResponse(
        url=f"/ui/reservations/{reservation_id}",
        status_code=303,
    )

@app.get("/ui/bank-transactions")
def bank_transactions_ui(
    request: Request,
    month: int | None = None,
    year: int | None = None,
    notes: str | None = None,
    reservation_number: str | None = None,
    db_connection=Depends(get_db_connection),
):
    transactions = None
    total_amount = None
    reservation_lookup = None
    reservation_lookup_error = None

    if reservation_number:
        try:
            _, reservation, deposit = get_direct_pending_deposit(
                db_connection,
                reservation_number,
            )
            reservation_lookup = {
                "id": reservation["id"],
                "cottage_id": reservation["cottage_id"],
                "check_in": reservation["check_in"],
                "check_out": reservation["check_out"],
                "total_amount": reservation["total_amount"],
                "deposit_amount": deposit["amount"],
                "due_at": deposit["due_at"],
            }
        except ValueError as exc:
            reservation_lookup_error = str(exc)

    if month is not None and year is not None:
        if month == 12:
            start_date = date(year, 12, 1)
            end_date = date(year + 1, 1, 1)
        else:
            start_date = date(year, month, 1)
            end_date = date(year, month + 1, 1)

        transactions = list_bank_transactions(
            connection=db_connection,
            start_date=start_date,
            end_date=end_date,
            notes=notes,
        )

        total_amount = sum_bank_transactions(
            connection=db_connection,
            start_date=start_date,
            end_date=end_date,
            notes=notes,
        )

    return templates.TemplateResponse(
        request=request,
        name="bank_transactions.html",
        context={
            "request": request,
            "month": month,
            "year": year,
            "transactions": transactions,
            "total_amount": total_amount,
            "reservation_number": reservation_number,
            "reservation_lookup": reservation_lookup,
            "reservation_lookup_error": reservation_lookup_error,
        },
    )

@app.post("/ui/bank-transactions")
def create_bank_transaction_ui(
    transaction_date: date = Form(...),
    source_id: int = Form(...),
    cottage_id: int | None = Form(None),
    amount: Decimal = Form(...),
    description: str | None = Form(None),
    notes: str | None = Form(None),
    reservation_number: str | None = Form(None),
    db_connection=Depends(get_db_connection),
):
    try:
        transaction_id = create_bank_transaction(
            connection=db_connection,
            transaction_date=transaction_date,
            source_id=source_id,
            cottage_id=cottage_id,
            amount=amount,
            description=description,
            notes=notes,
            reservation_number=reservation_number,
        )

        db_connection.commit()

    except ValueError as exc:
        db_connection.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    return RedirectResponse(
        url=(
            f"/ui/bank-transactions"
            f"?month={transaction_date.month}"
            f"&year={transaction_date.year}"
        ),
        status_code=303,
    )


@app.get("/ui/inquiries")
def web_inquiries_ui(
    request: Request,
    db_connection=Depends(get_db_connection),
):
    expire_payment_holds(db_connection)
    inquiries = WebInquiryRepository(db_connection).list_all()
    for inquiry in inquiries:
        inquiry["offer_expires_at"] = (
            inquiry["message_sent_at"] + timedelta(hours=48)
            if inquiry["message_sent_at"] is not None
            else None
        )
        inquiry["offer_expired"] = (
            inquiry["offer_expires_at"] is not None
            and inquiry["offer_expires_at"] <= datetime.now()
        )
    active_inquiries = [
        inquiry
        for inquiry in inquiries
        if inquiry["status"] in {"NEW", "IN_PROGRESS"}
    ]
    resolved_inquiries = [
        inquiry
        for inquiry in inquiries
        if inquiry["status"] not in {"NEW", "IN_PROGRESS"}
    ]
    return templates.TemplateResponse(
        request=request,
        name="web_inquiries.html",
        context={
            "inquiries": inquiries,
            "active_inquiries": active_inquiries,
            "resolved_inquiries": resolved_inquiries,
        },
    )


@app.get("/ui/inquiries/{inquiry_id}/template")
def web_inquiry_template_ui(
    request: Request,
    inquiry_id: int,
    total_amount: Decimal | None = Query(None, gt=0),
    deposit_amount: Decimal | None = Query(None, gt=0),
    cottage: str = Query(""),
    check_in: date | None = Query(None),
    check_out: date | None = Query(None),
    db_connection=Depends(get_db_connection),
):
    inquiry = next(
        (
            item
            for item in WebInquiryRepository(db_connection).list_all()
            if item["id"] == inquiry_id
        ),
        None,
    )
    if inquiry is None:
        raise HTTPException(status_code=404, detail="Inquiry not found")

    quote_check_in = check_in or inquiry["offered_check_in"] or inquiry["check_in"]
    quote_check_out = check_out or inquiry["offered_check_out"] or inquiry["check_out"]
    if quote_check_out <= quote_check_in:
        raise HTTPException(status_code=422, detail="Invalid quote dates")
    same_as_saved_offer = (
        quote_check_in == inquiry["offered_check_in"]
        and quote_check_out == inquiry["offered_check_out"]
    )

    availability_service = AvailabilityService(
        reservation_repository=ReservationRepository(db_connection),
        block_repository=BlockRepository(db_connection),
        cottage_repository=CottageRepository(db_connection),
    )
    current_cottage_ids = availability_service.get_available_cottages(
        check_in=quote_check_in,
        check_out=quote_check_out,
        guests_count=inquiry["guests_count"],
    )
    preferred_cottage_id = inquiry["preferred_cottage_id"]
    preferred_cottage_available = (
        preferred_cottage_id in current_cottage_ids
        if preferred_cottage_id is not None
        else None
    )
    alternative_cottage_ids = [
        cottage_id
        for cottage_id in current_cottage_ids
        if cottage_id != preferred_cottage_id
    ]

    stay_length = (quote_check_out - quote_check_in).days
    alternative_dates = []
    if not current_cottage_ids:
        for offset in (*range(-7, 0), *range(1, 8)):
            alternate_check_in = quote_check_in + timedelta(days=offset)
            alternate_check_out = alternate_check_in + timedelta(days=stay_length)
            if alternate_check_in < date.today():
                continue
            available_ids = availability_service.get_available_cottages(
                check_in=alternate_check_in,
                check_out=alternate_check_out,
                guests_count=inquiry["guests_count"],
            )
            if available_ids:
                alternate_price = estimate_inquiry_stay_price(
                    alternate_check_in, alternate_check_out
                )
                alternative_dates.append(
                    {
                        "check_in": alternate_check_in,
                        "check_out": alternate_check_out,
                        "cottage_ids": available_ids,
                        "estimated_amount": alternate_price,
                        "deposit_amount": (
                            calculate_deposit(alternate_price)
                            if alternate_price is not None
                            else None
                        ),
                    }
                )

    if total_amount is not None and deposit_amount is not None and deposit_amount > total_amount:
        raise HTTPException(status_code=422, detail="Deposit cannot exceed total amount")

    estimated_amount = estimate_inquiry_stay_price(
        quote_check_in, quote_check_out
    )
    if total_amount is None:
        total_amount = (
            inquiry["offered_total_amount"]
            if same_as_saved_offer
            else estimated_amount
        )
    if deposit_amount is None and same_as_saved_offer:
        deposit_amount = inquiry["offered_deposit_amount"]
    if deposit_amount is None and total_amount is not None:
        deposit_amount = calculate_deposit(total_amount)
    if (
        not cottage
        and same_as_saved_offer
        and inquiry["offered_cottage_id"] in current_cottage_ids
    ):
        cottage = f"Domek {inquiry['offered_cottage_id']}"

    available_cottage_names = {
        f"Domek {cottage_id}" for cottage_id in current_cottage_ids
    }
    if cottage and cottage not in available_cottage_names:
        raise HTTPException(status_code=422, detail="Selected cottage is unavailable")

    message = None
    if not current_cottage_ids:
        availability_text = "Niestety w wybranym terminie nie ma obecnie dostępnego domku."
        if alternative_dates:
            suggestions = "; ".join(
                f"{item['check_in'].strftime('%d.%m.%Y')}–"
                f"{item['check_out'].strftime('%d.%m.%Y')} "
                f"(wolne domki: {', '.join(map(str, item['cottage_ids']))})"
                for item in alternative_dates
            )
            availability_text += f" Możliwe terminy w pobliżu: {suggestions}."
        message = (
            f"Dzień dobry {inquiry['full_name']},\n\n"
            f"Niestety w terminie od {quote_check_in.strftime('%d.%m.%Y')} do "
            f"{quote_check_out.strftime('%d.%m.%Y')} nie mamy wolnego domku.\n\n"
            f"{availability_text}\n\n"
            "Prosimy o informację, czy któryś z alternatywnych terminów jest dla Państwa odpowiedni. "
            "Po wyborze terminu ponownie potwierdzimy dostępność i przygotujemy warunki płatności.\n\n"
            "Pozdrawiamy\nWrzosowo 159"
        )
    elif total_amount is not None and deposit_amount is not None and cottage:
        balance = total_amount - deposit_amount
        format_amount = lambda amount: f"{amount:,.2f}".replace(",", " ").replace(".", ",")
        quote_dates_text = (
            f"od {quote_check_in.strftime('%d.%m.%Y')} do "
            f"{quote_check_out.strftime('%d.%m.%Y')}"
        )
        message = (
            f"Dzień dobry {inquiry['full_name']},\n\n"
            f"potwierdzamy wstępną dostępność pobytu w {cottage} "
            f"{quote_dates_text} dla {inquiry['guests_count']} osób.\n\n"
            f"Wskazany domek jest obecnie dostępny; dostępność wymaga końcowego potwierdzenia.\n\n"
            f"Szacunkowa wartość pobytu: {format_amount(total_amount)} zł.\n"
            f"Zadatek (30%): {format_amount(deposit_amount)} zł.\n"
            f"Pozostała kwota: {format_amount(balance)} zł.\n\n"
            "Prosimy o wpłatę zadatku w ciągu 48 godzin od wysłania tej wiadomości. "
            "Po wykonaniu przelewu prosimy o przesłanie potwierdzenia wpłaty. "
            "Rezerwacja zostanie potwierdzona po otrzymaniu wpłaty i końcowym "
            "potwierdzeniu dostępności.\n\n"
            "Dane do przelewu:\n"
            "Wrzosowo 159\n"
            "ING: 62 1050 1520 1000 0091 3978 0382\n"
            f"Tytuł przelewu: zadatek, {inquiry['full_name']}, "
            f"{quote_check_in.strftime('%d.%m.%Y')}–"
            f"{quote_check_out.strftime('%d.%m.%Y')}\n\n"
            "Opłata miejscowa: 3 zł za osobę za noc, płatna na miejscu.\n"
            "Cena nie uwzględnia ewentualnej opłaty za psa (25 zł/doba).\n\n"
            "Pozdrawiamy\nWrzosowo 159"
        )

    return templates.TemplateResponse(
        request=request,
        name="web_inquiry_template.html",
        context={
            "inquiry": inquiry,
            "total_amount": total_amount,
            "deposit_amount": deposit_amount,
            "cottage": cottage,
            "message": message,
            "current_cottage_ids": current_cottage_ids,
            "preferred_cottage_available": preferred_cottage_available,
            "alternative_cottage_ids": alternative_cottage_ids,
            "alternative_dates": alternative_dates,
            "estimated_amount": estimated_amount,
            "uses_default_rate": inquiry_price_uses_default_rate(
                quote_check_in, quote_check_out
            ),
            "quote_check_in": quote_check_in,
            "quote_check_out": quote_check_out,
            "offer_expires_at": (
                inquiry["message_sent_at"] + timedelta(hours=48)
                if inquiry["message_sent_at"] is not None
                else None
            ),
            "offer_expired": (
                inquiry["message_sent_at"] is not None
                and inquiry["message_sent_at"] + timedelta(hours=48) <= datetime.now()
            ),
        },
    )


@app.post("/ui/inquiries/{inquiry_id}/mark-offer-sent")
def mark_inquiry_offer_sent_ui(
    inquiry_id: int,
    cottage_id: int = Form(...),
    total_amount: Decimal = Form(..., gt=0),
    deposit_amount: Decimal = Form(..., gt=0),
    check_in: date = Form(...),
    check_out: date = Form(...),
    confirm_sent: bool = Form(False),
    db_connection=Depends(get_db_connection),
):
    if not confirm_sent:
        raise HTTPException(status_code=400, detail="Confirm that the message was sent")
    if check_out <= check_in:
        raise HTTPException(status_code=400, detail="Invalid reservation dates")
    if deposit_amount > total_amount:
        raise HTTPException(status_code=400, detail="Deposit cannot exceed total amount")
    if deposit_amount != calculate_deposit(total_amount):
        raise HTTPException(status_code=400, detail="Deposit must equal 30% of the total amount")

    inquiry_repository = WebInquiryRepository(db_connection)
    reservation_repository = ReservationRepository(db_connection)
    cottage_repository = CottageRepository(db_connection)
    now = datetime.now().replace(microsecond=0)
    try:
        inquiry = inquiry_repository.get_by_id_for_update(inquiry_id)
        if inquiry is None:
            raise HTTPException(status_code=404, detail="Inquiry not found")
        if inquiry["status"] != "IN_PROGRESS" or inquiry["reservation_id"] is not None:
            raise HTTPException(status_code=409, detail="Inquiry is not awaiting a payment request")
        inquiry_length = (inquiry["check_out"] - inquiry["check_in"]).days
        if (
            (check_out - check_in).days != inquiry_length
            or abs((check_in - inquiry["check_in"]).days) > 7
        ):
            raise HTTPException(status_code=400, detail="Reservation dates must be the inquiry dates or a suggested nearby date")

        cottage = cottage_repository.get_by_id_for_update(cottage_id)
        if cottage is None or not cottage["active"]:
            raise HTTPException(status_code=409, detail="Cottage is unavailable")
        if inquiry["guests_count"] > cottage["capacity"]:
            raise HTTPException(status_code=409, detail="Cottage capacity is too small")

        reservation_repository.expire_pending_reservations(now)
        availability_service = AvailabilityService(
            reservation_repository=reservation_repository,
            block_repository=BlockRepository(db_connection),
            cottage_repository=cottage_repository,
        )
        available_cottage_ids = availability_service.get_available_cottages(
            check_in=check_in,
            check_out=check_out,
            guests_count=inquiry["guests_count"],
        )
        if cottage_id not in available_cottage_ids:
            raise HTTPException(status_code=409, detail="Cottage is no longer available")

        sent_at = datetime.now().replace(microsecond=0)
        inquiry_repository.save_sent_offer(
            inquiry_id=inquiry_id,
            cottage_id=cottage_id,
            check_in=check_in,
            check_out=check_out,
            total_amount=total_amount,
            deposit_amount=deposit_amount,
            message_sent_at=sent_at,
        )
        db_connection.commit()
    except HTTPException:
        db_connection.rollback()
        raise
    except Exception:
        db_connection.rollback()
        raise

    return RedirectResponse(
        url=f"/ui/inquiries#inquiry-{inquiry_id}",
        status_code=303,
    )


@app.post("/ui/inquiries/{inquiry_id}/accept")
def accept_web_inquiry_ui(
    inquiry_id: int,
    db_connection=Depends(get_db_connection),
):
    inquiry_repository = WebInquiryRepository(db_connection)
    reservation_repository = ReservationRepository(db_connection)
    cottage_repository = CottageRepository(db_connection)
    now = datetime.now().replace(microsecond=0)

    try:
        inquiry = inquiry_repository.get_by_id_for_update(inquiry_id)
        if inquiry is None:
            raise HTTPException(status_code=404, detail="Inquiry not found")
        if inquiry["status"] != "IN_PROGRESS" or inquiry["reservation_id"] is not None:
            raise HTTPException(status_code=409, detail="Inquiry cannot be accepted")
        if inquiry["message_sent_at"] is None or inquiry["offered_cottage_id"] is None:
            raise HTTPException(status_code=409, detail="Send and confirm the offer first")

        expires_at = inquiry["message_sent_at"] + timedelta(hours=48)
        if expires_at <= now:
            raise HTTPException(status_code=409, detail="Offer expired; send it again before accepting")

        cottage_id = inquiry["offered_cottage_id"]
        cottage = cottage_repository.get_by_id_for_update(cottage_id)
        if cottage is None or not cottage["active"]:
            raise HTTPException(status_code=409, detail="Cottage is unavailable")
        if inquiry["guests_count"] > cottage["capacity"]:
            raise HTTPException(status_code=409, detail="Cottage capacity is too small")

        reservation_repository.expire_pending_reservations(now)
        availability_service = AvailabilityService(
            reservation_repository=reservation_repository,
            block_repository=BlockRepository(db_connection),
            cottage_repository=cottage_repository,
        )
        available_cottage_ids = availability_service.get_available_cottages(
            check_in=inquiry["offered_check_in"],
            check_out=inquiry["offered_check_out"],
            guests_count=inquiry["guests_count"],
        )
        if cottage_id not in available_cottage_ids:
            raise HTTPException(status_code=409, detail="Cottage is no longer available")

        first_name, _, last_name = inquiry["full_name"].strip().partition(" ")
        customer_id = CustomerRepository(db_connection).create(
            first_name=first_name,
            last_name=last_name,
            phone=inquiry["phone"],
            email=inquiry["email"],
        )
        with db_connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM reservation_sources WHERE code = 'DIRECT'"
            )
            direct_source = cursor.fetchone()
        if direct_source is None:
            raise HTTPException(status_code=500, detail="Direct reservation source is missing")

        reservation_id = reservation_repository.create(
            cottage_id=cottage_id,
            customer_id=customer_id,
            source_id=direct_source["id"],
            check_in=inquiry["offered_check_in"],
            check_out=inquiry["offered_check_out"],
            guests_count=inquiry["guests_count"],
            status="PENDING",
            expires_at=expires_at,
            total_amount=inquiry["offered_total_amount"],
            deposit_amount=inquiry["offered_deposit_amount"],
            notes=f"Rezerwacja z zapytania WWW #{inquiry_id}",
        )
        PaymentRepository(db_connection).create_payment(
            reservation_id=reservation_id,
            payment_type="DEPOSIT",
            amount=inquiry["offered_deposit_amount"],
            status="UNPAID",
            due_at=expires_at,
        )
        inquiry_repository.convert_to_reservation(inquiry_id, reservation_id)
        db_connection.commit()
    except HTTPException:
        db_connection.rollback()
        raise
    except Exception:
        db_connection.rollback()
        raise

    return RedirectResponse(
        url=f"/ui/inquiries?reservation_id={reservation_id}#inquiry-{inquiry_id}",
        status_code=303,
    )


@app.post("/ui/inquiries/{inquiry_id}/status")
def update_web_inquiry_status_ui(
    inquiry_id: int,
    status: str = Form(...),
    db_connection=Depends(get_db_connection),
):
    allowed_statuses = {"IN_PROGRESS", "REJECTED", "CLOSED"}
    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Invalid inquiry status")

    WebInquiryRepository(db_connection).update_status(
        inquiry_id=inquiry_id,
        status=status,
    )
    db_connection.commit()
    redirect_url = "/ui/inquiries"
    if status == "IN_PROGRESS":
        redirect_url += f"#inquiry-{inquiry_id}"
    return RedirectResponse(url=redirect_url, status_code=303)

@app.get("/api/sales-report")
def get_sales_report(
    start_date: date,
    end_date: date,
    db_connection=Depends(get_db_connection),
):
    if end_date <= start_date:
        raise HTTPException(
            status_code=400,
            detail="end_date must be after start_date",
        )

    return generate_sales_report(
        connection=db_connection,
        start_date=start_date,
        end_date=end_date,
    )
@app.get("/ui/reports/sales")
def sales_report_ui(
    request: Request,
    month: int = 7,
    year: int = 2026,
    db_connection=Depends(get_db_connection),
):
    if month < 0 or month > 12:
        raise HTTPException(
            status_code=400,
            detail="Invalid month",
        )

    if month == 0:
        start_date = date(year, 1, 1)
        end_date = date(year + 1, 1, 1)
    else:
        start_date = date(year, month, 1)

        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

    report = generate_sales_report(
        connection=db_connection,
        start_date=start_date,
        end_date=end_date,
    )

    return templates.TemplateResponse(
        request=request,
        name="sales_report.html",
        context={
            "month": month,
            "year": year,
            "years": sorted({2026, 2027, year}),
            "reservations": report["reservations"],
            "total_amount": report["total_amount"],
            "by_source": report["by_source"],
        },
    )

@app.get("/ui/reports/accounting")
def accounting_report_ui(
    request: Request,
    month: int = 7,
    year: int = 2026,
    start_month: int | None = None,
    start_year: int | None = None,
    end_month: int | None = None,
    end_year: int | None = None,
    db_connection=Depends(get_db_connection),
):
    if month < 0 or month > 12:
        raise HTTPException(
            status_code=400,
            detail="Invalid month",
        )

    has_custom_range = any(
        value is not None
        for value in (start_month, start_year, end_month, end_year)
    )

    if has_custom_range:
        if any(
            value is None
            for value in (start_month, start_year, end_month, end_year)
        ):
            raise HTTPException(
                status_code=400,
                detail="Complete date range is required",
            )

        if not 1 <= start_month <= 12 or not 1 <= end_month <= 12:
            raise HTTPException(
                status_code=400,
                detail="Invalid month in date range",
            )

        report_start_date = date(start_year, start_month, 1)
        if end_month == 12:
            report_end_date = date(end_year + 1, 1, 1)
        else:
            report_end_date = date(
                end_year,
                end_month + 1,
                1,
            )

    elif month == 0:
        report_start_date = date(year, 1, 1)
        report_end_date = date(year + 1, 1, 1)
    else:
        report_start_date = date(year, month, 1)

        if month == 12:
            report_end_date = date(year + 1, 1, 1)
        else:
            report_end_date = date(year, month + 1, 1)

    reports = generate_accounting_reports(
    connection=db_connection,
    start_date=report_start_date,
    end_date=report_end_date,
  )

    return templates.TemplateResponse(
        request=request,
        name="accounting_report.html",
        context={
            "reports": reports,
            "month": month,
            "year": year,
            "start_month": start_month if start_month is not None else month,
            "start_year": start_year if start_year is not None else year,
            "end_month": end_month if end_month is not None else month,
            "end_year": end_year if end_year is not None else year,
            "years": sorted({2026, 2027, year, start_year, end_year} - {None}),
        },
    )
