from datetime import date, datetime
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.reservation_service import create_reservation, update_reservation
from app.payment_service import create_payment, mark_payment_as_paid, generate_payment_report
from app.reservation_service import cancel_reservation
from app.customer_service import create_customer, get_customer, update_customer
from app.availability_service import AvailabilityService

from app.repositories.block_repository import BlockRepository
from app.repositories.cottage_repository import CottageRepository
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.customer_repository import CustomerRepository

from app.database import get_connection



app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

templates = Jinja2Templates(directory="app/templates")

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
    

def get_db_connection():
    connection = get_connection()

    try:
        yield connection
    finally:
        connection.close()


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


@app.get("/")
def read_root():
    return {"message": "QA Booking API"}


@app.get("/api/availability")
def check_availability(
    check_in: date,
    check_out: date,
    availability_service=Depends(get_availability_service),
):
    if check_out <= check_in:
        raise HTTPException(
            status_code=400,
            detail="check_out must be after check_in",
        )

    available_cottages = availability_service.get_available_cottages(
        check_in=check_in,
        check_out=check_out,
    )

    return {
        "check_in": check_in,
        "check_out": check_out,
        "cottages": available_cottages,
    }

@app.post("/api/reservations", status_code=201)
def create_reservation_endpoint(
    reservation: ReservationCreate,
    db_connection=Depends(get_db_connection),
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
    db_connection=Depends(get_db_connection),
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
    db_connection=Depends(get_db_connection),
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
    db_connection=Depends(get_db_connection),
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
    db_connection=Depends(get_db_connection),
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
    db_connection=Depends(get_db_connection),
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
    db_connection=Depends(get_db_connection),
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
