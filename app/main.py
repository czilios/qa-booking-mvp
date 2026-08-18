from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from app.availability_service import AvailabilityService
from app.database import get_connection
from app.repositories.block_repository import BlockRepository
from app.repositories.cottage_repository import CottageRepository
from app.repositories.reservation_repository import ReservationRepository
from app.reservation_service import create_reservation


app = FastAPI()

class ReservationCreate(BaseModel):
    cottage_id: int
    source_id: int
    check_in: date
    check_out: date
    guests_count: int = Field(gt=0)


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
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )