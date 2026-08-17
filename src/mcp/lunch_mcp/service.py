import asyncio
import random
import unicodedata
from collections import defaultdict
from datetime import date

from .errors import AppError
from .mappers import map_meal, map_school
from .models import MealRangeResult, SchoolSearchResult
from .neis import NeisClient

MAX_DATE_RANGE_DAYS = 31


def parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AppError(
            "INVALID_DATE", f"{field_name}은 YYYY-MM-DD 형식이어야 합니다."
        ) from exc


class LunchService:
    def __init__(
        self,
        client: NeisClient,
        random_source: random.Random | random.SystemRandom | None = None,
    ) -> None:
        self.client = client
        self.random = random_source or random.SystemRandom()

    async def search_schools(self, query: str, page_size: int) -> SchoolSearchResult:
        normalized = unicodedata.normalize("NFKC", query).strip()
        if not 2 <= len(normalized) <= 100:
            raise AppError(
                "INVALID_QUERY", "학교 이름은 공백을 제외하고 2~100자로 입력해 주세요."
            )
        if not 1 <= page_size <= 100:
            raise AppError("INVALID_PAGE_SIZE", "page_size는 1~100이어야 합니다.")
        rows, total = await self.client.search_schools(normalized, page_size)
        if not rows:
            raise AppError(
                "SCHOOL_NOT_FOUND", "검색 결과가 없습니다. 다른 학교 이름을 입력해 주세요."
            )
        return SchoolSearchResult(
            schools=[map_school(row) for row in rows],
            total_count=total,
        )

    async def get_random_schools(self, count: int) -> SchoolSearchResult:
        if not 2 <= count <= 20:
            raise AppError("INVALID_COUNT", "학교 후보 수는 2~20이어야 합니다.")
        first_rows, total = await self.client.list_schools(1, 100)
        if total < count:
            raise AppError(
                "INSUFFICIENT_SCHOOLS",
                f"학교 후보 {count}곳을 준비할 수 없습니다.",
            )

        selected_indexes = sorted(self.random.sample(range(total), count))
        rows_by_index = {index: row for index, row in enumerate(first_rows)}
        pages: dict[int, list[int]] = defaultdict(list)
        for index in selected_indexes:
            if index not in rows_by_index:
                pages[index // 100 + 1].append(index)

        if pages:
            page_numbers = sorted(pages)
            page_results = await asyncio.gather(
                *(self.client.list_schools(page, 100) for page in page_numbers)
            )
            for page, (rows, _) in zip(page_numbers, page_results, strict=True):
                offset = (page - 1) * 100
                rows_by_index.update(
                    (offset + row_index, row)
                    for row_index, row in enumerate(rows)
                )

        try:
            schools = [map_school(rows_by_index[index]) for index in selected_indexes]
        except KeyError as exc:
            raise AppError(
                "NEIS_INVALID_RESPONSE",
                "NEIS 학교 목록이 요청한 후보를 포함하지 않습니다.",
            ) from exc
        unique = {school.school_code: school for school in schools}
        if len(unique) != count:
            raise AppError(
                "NEIS_INVALID_RESPONSE",
                "서로 다른 학교 후보를 준비하지 못했습니다.",
            )
        return SchoolSearchResult(schools=list(unique.values()), total_count=total)

    async def get_lunch_meals(
        self,
        education_office_code: str,
        school_code: str,
        start_date: str,
        end_date: str,
    ) -> MealRangeResult:
        office_code = education_office_code.strip()
        normalized_school_code = school_code.strip()
        if not office_code or not normalized_school_code:
            raise AppError(
                "INVALID_SCHOOL_ID",
                "교육청 코드와 학교 코드를 모두 입력해 주세요.",
            )
        start = parse_date(start_date, "start_date")
        end = parse_date(end_date, "end_date")
        if end < start:
            raise AppError(
                "INVALID_DATE_RANGE", "end_date는 start_date보다 빠를 수 없습니다."
            )
        if (end - start).days + 1 > MAX_DATE_RANGE_DAYS:
            raise AppError(
                "DATE_RANGE_TOO_LARGE",
                f"조회 기간은 최대 {MAX_DATE_RANGE_DAYS}일입니다.",
            )

        school_row = await self.client.get_school(office_code, normalized_school_code)
        meal_rows = await self.client.get_meals(
            office_code,
            normalized_school_code,
            start.strftime("%Y%m%d"),
            end.strftime("%Y%m%d"),
        )
        if not meal_rows:
            raise AppError(
                "MEALS_NOT_FOUND",
                "선택한 기간에 중식 정보가 없습니다. 다른 날짜를 입력해 주세요.",
            )
        meals = sorted((map_meal(row) for row in meal_rows), key=lambda meal: meal.date)
        return MealRangeResult(
            school=map_school(school_row),
            start_date=start,
            end_date=end,
            meals=meals,
        )
