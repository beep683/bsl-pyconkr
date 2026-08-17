from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pytest
import respx
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from lunch_mcp.neis import NeisClient
from lunch_mcp.server import create_server
from lunch_mcp.service import LunchService
from lunch_mcp.settings import Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def neis_response(key: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        key: [
            {
                "head": [
                    {"list_total_count": len(rows)},
                    {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다."}},
                ]
            },
            {"row": rows},
        ]
    }


@pytest.fixture
async def client_session() -> AsyncGenerator[ClientSession]:
    settings = Settings(
        neis_api_key="test-key",
        neis_base_url="https://neis.test/hub",
        neis_timeout_seconds=1,
    )
    service = LunchService(NeisClient(settings))
    async with create_connected_server_and_client_session(
        create_server(service), raise_exceptions=True
    ) as session:
        yield session


@pytest.mark.anyio
@respx.mock
async def test_lists_and_calls_tools_with_neis(client_session: ClientSession) -> None:
    school = {
        "SCHUL_NM": "예시고등학교",
        "ATPT_OFCDC_SC_NM": "서울특별시교육청",
        "ATPT_OFCDC_SC_CODE": "B10",
        "SD_SCHUL_CODE": "7010536",
        "SCHUL_KND_SC_NM": "고등학교",
        "LCTN_SC_NM": "서울특별시",
    }
    search_route = respx.get("https://neis.test/hub/schoolInfo").mock(
        return_value=httpx.Response(200, json=neis_response("schoolInfo", [school]))
    )
    meals_route = respx.get("https://neis.test/hub/mealServiceDietInfo").mock(
        return_value=httpx.Response(
            200,
            json=neis_response(
                "mealServiceDietInfo",
                [
                    {
                        "MLSV_YMD": "20260817",
                        "DDISH_NM": "현미밥<br/>된장국 (5.6)",
                        "CAL_INFO": "742.6 Kcal",
                        "MLSV_FGR": "520",
                        "NTR_INFO": "",
                        "ORPLC_INFO": "",
                    }
                ],
            ),
        )
    )

    tools = await client_session.list_tools()
    search_result = await client_session.call_tool(
        "search_schools", {"query": " 예시 ", "page_size": 10}
    )
    meal_result = await client_session.call_tool(
        "get_lunch_meals",
        {
            "education_office_code": "B10",
            "school_code": "7010536",
            "start_date": "2026-08-17",
            "end_date": "2026-08-17",
        },
    )

    assert {tool.name for tool in tools.tools} == {
        "search_schools",
        "get_random_schools",
        "get_lunch_meals",
    }
    assert search_result.isError is False
    assert search_result.structuredContent["schools"][0]["name"] == "예시고등학교"
    assert meal_result.isError is False
    assert meal_result.structuredContent["meals"][0]["menu_items"][1]["name"] == "된장국"
    assert search_route.call_count == 2
    assert meals_route.called
    assert meals_route.calls[0].request.url.params["MMEAL_SC_CODE"] == "2"
    assert meals_route.calls[0].request.url.params["MLSV_FROM_YMD"] == "20260817"


@pytest.mark.anyio
async def test_input_error_is_an_mcp_tool_error(client_session: ClientSession) -> None:
    result = await client_session.call_tool("search_schools", {"query": "가"})

    assert result.isError is True
    assert "INVALID_QUERY" in result.content[0].text


@pytest.mark.anyio
@respx.mock
async def test_neis_no_data_and_timeout_are_safe_errors(
    client_session: ClientSession,
) -> None:
    no_data = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
    respx.get("https://neis.test/hub/schoolInfo").mock(
        return_value=httpx.Response(200, json=no_data)
    )
    no_data_result = await client_session.call_tool("search_schools", {"query": "없는학교"})

    respx.get("https://neis.test/hub/schoolInfo").mock(
        side_effect=httpx.ReadTimeout("slow")
    )
    timeout_result = await client_session.call_tool("search_schools", {"query": "예시학교"})

    assert no_data_result.isError is True
    assert "SCHOOL_NOT_FOUND" in no_data_result.content[0].text
    assert timeout_result.isError is True
    assert "NEIS_TIMEOUT" in timeout_result.content[0].text
    assert "test-key" not in timeout_result.content[0].text


@pytest.mark.anyio
@respx.mock
async def test_meal_no_data_and_neis_error_are_tool_errors(
    client_session: ClientSession,
) -> None:
    school = {
        "SCHUL_NM": "예시고등학교",
        "ATPT_OFCDC_SC_NM": "서울특별시교육청",
        "ATPT_OFCDC_SC_CODE": "B10",
        "SD_SCHUL_CODE": "7010536",
        "SCHUL_KND_SC_NM": "고등학교",
        "LCTN_SC_NM": "서울특별시",
    }
    respx.get("https://neis.test/hub/schoolInfo").mock(
        return_value=httpx.Response(200, json=neis_response("schoolInfo", [school]))
    )
    respx.get("https://neis.test/hub/mealServiceDietInfo").mock(
        return_value=httpx.Response(
            200,
            json={"RESULT": {"CODE": "INFO-200", "MESSAGE": "데이터 없음"}},
        )
    )

    no_meals_result = await client_session.call_tool(
        "get_lunch_meals",
        {
            "education_office_code": "B10",
            "school_code": "7010536",
            "start_date": "2026-08-17",
            "end_date": "2026-08-17",
        },
    )

    respx.get("https://neis.test/hub/schoolInfo").mock(
        return_value=httpx.Response(
            200,
            json={"RESULT": {"CODE": "ERROR-300", "MESSAGE": "invalid key details"}},
        )
    )
    api_error_result = await client_session.call_tool(
        "search_schools", {"query": "예시학교"}
    )

    assert no_meals_result.isError is True
    assert "MEALS_NOT_FOUND" in no_meals_result.content[0].text
    assert api_error_result.isError is True
    assert "NEIS_ERROR" in api_error_result.content[0].text
    assert "invalid key details" not in api_error_result.content[0].text
