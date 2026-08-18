from datetime import date
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "QA Booking API"}

@app.get("/api/availability")
def check_availability(check_in: date, check_out: date):
    return {
        "check_in": check_in,
        "check_out": check_out,
    }