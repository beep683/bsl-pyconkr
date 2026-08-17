import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .errors import AppError
from .mappers import map_meal, map_school
from .models import MealDay, MealRangeResponse, SchoolSearchResponse
from .neis import NeisClient

SEOUL = ZoneInfo("Asia/Seoul")


def allowed_date_bounds(now: datetime | None = None) -> tuple[date, date]:
    current = (now or datetime.now(SEOUL)).astimezone(SEOUL).date()
    first_this_month = current.replace(day=1)
    last_previous_month = first_this_month - timedelta(days=1)
    first_previous_month = last_previous_month.replace(day=1)
    if first_this_month.month == 12:
        first_next_month = date(first_this_month.year + 1, 1, 1)
    else:
        first_next_month = date(first_this_month.year, first_this_month.month + 1, 1)
    return first_previous_month, first_next_month - timedelta(days=1)


def validate_date_range(from_date: date, to_date: date) -> None:
    if to_date < from_date:
        raise AppError(
            400,
            "INVALID_DATE_RANGE",
            "종료일은 시작일보다 빠를 수 없습니다.",
            field="to",
            reason="must be on or after from",
        )
    minimum, maximum = allowed_date_bounds()
    if from_date < minimum or to_date > maximum:
        raise AppError(
            400,
            "DATE_OUT_OF_ALLOWED_PERIOD",
            "이번 달과 직전 달의 날짜만 조회할 수 있습니다.",
            field="from",
            reason=f"must be between {minimum.isoformat()} and {maximum.isoformat()}",
        )


class LunchService:
    def __init__(self, client: NeisClient) -> None:
        self.client = client

    async def search_schools(
        self, query: str, page: int, page_size: int
    ) -> SchoolSearchResponse:
        normalized = unicodedata.normalize("NFKC", query).strip()
        if len(normalized) < 2:
            raise AppError(
                422,
                "QUERY_TOO_SHORT",
                "학교 이름을 두 글자 이상 입력해 주세요.",
                field="query",
                reason="must contain at least 2 characters",
            )
        rows, total = await self.client.search_schools(normalized, page, page_size)
        return SchoolSearchResponse(
            items=[map_school(row) for row in rows],
            page=page,
            page_size=page_size,
            total_count=total,
        )

    async def get_meals(
        self,
        education_office_code: str,
        school_code: str,
        from_date: date,
        to_date: date,
    ) -> MealRangeResponse:
        validate_date_range(from_date, to_date)
        school_row = await self.client.get_school(education_office_code, school_code)
        meal_rows = await self.client.get_meals(
            education_office_code,
            school_code,
            from_date.strftime("%Y%m%d"),
            to_date.strftime("%Y%m%d"),
        )
        meals = {meal.date: meal for meal in (map_meal(row) for row in meal_rows)}
        days: list[MealDay] = []
        current = from_date
        while current <= to_date:
            meal = meals.get(current)
            days.append(
                MealDay(
                    date=current,
                    status="available" if meal else "noData",
                    meal=meal,
                )
            )
            current += timedelta(days=1)
        return MealRangeResponse(
            school=map_school(school_row),
            **{"from": from_date},
            to=to_date,
            days=days,
        )
