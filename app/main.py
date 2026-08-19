from datetime import date, datetime
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.reservation_service import create_reservation, update_reservation
from app.payment_service import create_payment
from app.reservation_service import cancel_reservation
from app.availability_service import AvailabilityService

from app.repositories.block_repository import BlockRepository
from app.repositories.cottage_repository import CottageRepository
from app.repositories.reservation_repository import ReservationRepository

from app.database import get_connection



app = FastAPI()
class ReservationCreate(BaseModel):
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