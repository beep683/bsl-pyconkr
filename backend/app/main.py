from datetime import date
from uuid import uuid4

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .errors import AppError
from .models import ErrorBody, ErrorDetail, ErrorResponse, MealRangeResponse, SchoolSearchResponse
from .neis import NeisClient
from .services import LunchService
from .settings import Settings, get_settings

app = FastAPI(title="급식 배틀 API", version="0.1.0")


def get_client(settings: Settings = Depends(get_settings)) -> NeisClient:
    return NeisClient(settings)


def get_service(client: NeisClient = Depends(get_client)) -> LunchService:
    return LunchService(client)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = request.headers.get("x-request-id", str(uuid4()))
    details = (
        [ErrorDetail(field=exc.field, reason=exc.reason or exc.message)]
        if exc.field or exc.reason
        else []
    )
    response = ErrorResponse(
        error=ErrorBody(
            code=exc.code,
            message=exc.message,
            details=details,
            request_id=request_id,
        )
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(by_alias=True, mode="json"),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = request.headers.get("x-request-id", str(uuid4()))
    details = [
        ErrorDetail(
            field=str(error["loc"][-1]) if error["loc"] else None,
            reason=str(error["msg"]),
        )
        for error in exc.errors()
    ]
    response = ErrorResponse(
        error=ErrorBody(
            code="VALIDATION_ERROR",
            message="요청 값을 확인해 주세요.",
            details=details,
            request_id=request_id,
        )
    )
    return JSONResponse(
        status_code=422,
        content=response.model_dump(by_alias=True, mode="json"),
    )


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/schools", response_model=SchoolSearchResponse)
async def search_schools(
    query: str = Query(min_length=1, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    service: LunchService = Depends(get_service),
) -> SchoolSearchResponse:
    return await service.search_schools(query, page, page_size)


@app.get("/api/v1/meals", response_model=MealRangeResponse)
async def get_meals(
    education_office_code: str = Query(alias="educationOfficeCode", min_length=1),
    school_code: str = Query(alias="schoolCode", min_length=1),
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    service: LunchService = Depends(get_service),
) -> MealRangeResponse:
    return await service.get_meals(
        education_office_code,
        school_code,
        from_date,
        to_date,
    )
