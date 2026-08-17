import random
from typing import Any

import pytest

from lunch_mcp.service import LunchService


def school(index: int) -> dict[str, str]:
    return {
        "SCHUL_NM": f"{index}학교",
        "ATPT_OFCDC_SC_NM": "서울특별시교육청",
        "ATPT_OFCDC_SC_CODE": "B10",
        "SD_SCHUL_CODE": str(index),
        "SCHUL_KND_SC_NM": "고등학교",
        "LCTN_SC_NM": "서울특별시",
    }


class SchoolListClient:
    async def list_schools(
        self, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        start = (page - 1) * page_size
        return [school(index) for index in range(start, min(start + page_size, 250))], 250


@pytest.mark.anyio
async def test_random_school_candidates_are_exact_and_unique() -> None:
    service = LunchService(SchoolListClient(), random.Random(7))

    result = await service.get_random_schools(10)

    assert len(result.schools) == 10
    assert len({item.school_code for item in result.schools}) == 10
    assert result.total_count == 250
