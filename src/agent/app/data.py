from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from agent_framework import MCPStreamableHTTPTool

from .schemas import MealData, SchoolCandidate


class LunchDataError(RuntimeError):
    """Raised when MCP data cannot satisfy an analysis request."""


class McpCaller(Protocol):
    async def call_tool(self, tool_name: str, **kwargs: Any) -> str | list[Any]: ...


class LunchDataSource(Protocol):
    async def random_schools(self, count: int = 10) -> list[SchoolCandidate]: ...

    async def meals_for(
        self,
        school_a: SchoolCandidate,
        school_b: SchoolCandidate,
        analysis_date: date,
    ) -> tuple[MealData, MealData]: ...


def _normalize_mcp_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.path not in ("", "/"):
        return value
    return urlunsplit((parts.scheme, parts.netloc, "/mcp", parts.query, parts.fragment))


class McpLunchDataSource:
    def __init__(self, tool: McpCaller) -> None:
        self._tool = tool

    @classmethod
    def create(cls, mcp_url: str) -> tuple[MCPStreamableHTTPTool, McpLunchDataSource]:
        tool = MCPStreamableHTTPTool(
            "school-lunch-mcp",
            _normalize_mcp_url(mcp_url),
            allowed_tools=["get_random_schools", "get_lunch_meals"],
            approval_mode="never_require",
            load_prompts=False,
        )
        return tool, cls(tool)

    async def random_schools(self, count: int = 10) -> list[SchoolCandidate]:
        payload = await self._call("get_random_schools", count=count)
        try:
            schools = payload["schools"]
            candidates = [SchoolCandidate.model_validate(item) for item in schools]
        except (KeyError, TypeError, ValueError) as exc:
            raise LunchDataError("MCP 학교 후보 응답 형식이 올바르지 않습니다.") from exc
        unique = {school.school_code: school for school in candidates}
        if len(unique) != count:
            raise LunchDataError(f"MCP에서 서로 다른 학교 {count}곳을 받지 못했습니다.")
        return list(unique.values())

    async def meals_for(
        self,
        school_a: SchoolCandidate,
        school_b: SchoolCandidate,
        analysis_date: date,
    ) -> tuple[MealData, MealData]:
        day = analysis_date.isoformat()
        payload_a, payload_b = await asyncio.gather(
            self._call(
                "get_lunch_meals",
                education_office_code=school_a.education_office_code,
                school_code=school_a.school_code,
                start_date=day,
                end_date=day,
            ),
            self._call(
                "get_lunch_meals",
                education_office_code=school_b.education_office_code,
                school_code=school_b.school_code,
                start_date=day,
                end_date=day,
            ),
        )
        return (
            self._meal_from_payload(payload_a, school_a, analysis_date),
            self._meal_from_payload(payload_b, school_b, analysis_date),
        )

    async def _call(self, name: str, **arguments: Any) -> dict[str, Any]:
        try:
            result = await self._tool.call_tool(name, **arguments)
        except Exception as exc:
            message = str(exc)
            if "MEALS_NOT_FOUND" in message:
                raise LunchDataError(
                    "한 학교 이상에서 선택 날짜의 중식 데이터가 없습니다."
                ) from exc
            raise LunchDataError(f"MCP 도구 {name} 호출에 실패했습니다.") from exc
        return _decode_tool_result(result)

    @staticmethod
    def _meal_from_payload(
        payload: dict[str, Any],
        school: SchoolCandidate,
        analysis_date: date,
    ) -> MealData:
        meals = payload.get("meals")
        if not isinstance(meals, list) or len(meals) != 1:
            raise LunchDataError(
                f"{school.name}의 선택 날짜 중식 데이터가 없습니다."
            )
        data = dict(meals[0])
        data["school"] = school.model_dump(mode="json")
        data["date"] = analysis_date.isoformat()
        try:
            return MealData.model_validate(data)
        except ValueError as exc:
            raise LunchDataError("MCP 급식 응답 형식이 올바르지 않습니다.") from exc


def _decode_tool_result(result: str | list[Any]) -> dict[str, Any]:
    texts = (
        [result]
        if isinstance(result, str)
        else [
            item.text
            for item in result
            if isinstance(getattr(item, "text", None), str)
        ]
    )
    for text in texts:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise LunchDataError("MCP가 유효한 JSON 객체를 반환하지 않았습니다.")
