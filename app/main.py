from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.orders import router as orders_router
from app.api.errors import ErrorResponse
import uuid

app = FastAPI(title="B2B Order Management API", version="1.0.0")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    payload = ErrorResponse(
        status_code=422,
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[
            {
                "field": ".".join(str(loc) for loc in err["loc"] if loc != "body"),
                "message": err["msg"],
            }
            for err in exc.errors()
        ],
        request_id=str(uuid.uuid4()),
    )
    return JSONResponse(status_code=422, content=payload.model_dump())

app.include_router(orders_router)

@app.get("/")
async def root():
    return {"message": "Welcome to B2B Order Management API"}