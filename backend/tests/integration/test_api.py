from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from app.main import app, get_client
from app.neis import NeisClient
from app.services import allowed_date_bounds


class StubNeisClient:
    async def search_schools(
        self, query: str, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        assert query == "예시"
        return [
            {
                "ATPT_OFCDC_SC_CODE": "B10",
                "SD_SCHUL_CODE": "7010536",
                "SCHUL_NM": "예시고등학교",
                "SCHUL_KND_SC_NM": "고등학교",
                "LCTN_SC_NM": "서울특별시",
            }
        ], 1

    async def get_school(self, office_code: str, school_code: str) -> dict[str, Any]:
        return {
            "ATPT_OFCDC_SC_CODE": office_code,
            "SD_SCHUL_CODE": school_code,
            "SCHUL_NM": "예시고등학교",
            "SCHUL_KND_SC_NM": "고등학교",
            "LCTN_SC_NM": "서울특별시",
        }

    async def get_meals(
        self, office_code: str, school_code: str, from_date: str, to_date: str
    ) -> list[dict[str, Any]]:
        assert len(from_date) == 8
        return [
            {
                "MLSV_YMD": from_date,
                "DDISH_NM": "현미밥<br/>된장국 (5.6)",
                "CAL_INFO": "742.6 Kcal",
                "MLSV_FGR": "520",
                "NTR_INFO": "",
                "ORPLC_INFO": "",
            }
        ]


@pytest.fixture
def client() -> httpx.AsyncClient:
    app.dependency_overrides[get_client] = lambda: StubNeisClient()
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


@pytest.mark.asyncio
async def test_school_search_and_meal_range(client: httpx.AsyncClient) -> None:
    minimum, _ = allowed_date_bounds()
    end = minimum + timedelta(days=1)
    school_response = await client.get("/api/v1/schools", params={"query": " 예시 "})
    meal_response = await client.get(
        "/api/v1/meals",
        params={
            "educationOfficeCode": "B10",
            "schoolCode": "7010536",
            "from": minimum.isoformat(),
            "to": end.isoformat(),
        },
    )
    await client.aclose()
    app.dependency_overrides.clear()

    assert school_response.status_code == 200
    assert school_response.json()["items"][0]["name"] == "예시고등학교"
    assert meal_response.status_code == 200
    assert [day["status"] for day in meal_response.json()["days"]] == [
        "available",
        "noData",
    ]


@pytest.mark.asyncio
async def test_short_query_uses_error_contract(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/schools", params={"query": "가"})
    await client.aclose()
    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "QUERY_TOO_SHORT"
    assert response.json()["error"]["requestId"]
