from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.errors import AppError
from app.mappers import map_meal, map_school
from app.services import allowed_date_bounds, validate_date_range


def test_maps_school_and_meal_fields() -> None:
    school = map_school(
        {
            "ATPT_OFCDC_SC_CODE": "B10",
            "SD_SCHUL_CODE": "7010536",
            "SCHUL_NM": "예시고등학교",
            "SCHUL_KND_SC_NM": "고등학교",
            "LCTN_SC_NM": "서울특별시",
        }
    )
    meal = map_meal(
        {
            "MLSV_YMD": "20260817",
            "DDISH_NM": "현미밥<br/>된장국 (5.6)",
            "CAL_INFO": "742.6 Kcal",
            "MLSV_FGR": 520.0,
            "NTR_INFO": "단백질(g) : 24.3",
            "ORPLC_INFO": "쌀 : 국내산",
        }
    )

    assert school.name == "예시고등학교"
    assert meal.date == date(2026, 8, 17)
    assert meal.menu_items[1].allergen_codes == ["5", "6"]
    assert meal.calories_kcal == 742.6
    assert meal.servings == 520
    assert meal.nutrition[0].unit == "g"
    assert meal.origins[0].origin == "국내산"


def test_allowed_period_handles_january_boundary() -> None:
    now = datetime(2026, 1, 15, tzinfo=ZoneInfo("Asia/Seoul"))
    assert allowed_date_bounds(now) == (date(2025, 12, 1), date(2026, 1, 31))


def test_invalid_range_is_rejected() -> None:
    with pytest.raises(AppError, match="종료일"):
        validate_date_range(date(2026, 8, 18), date(2026, 8, 17))
