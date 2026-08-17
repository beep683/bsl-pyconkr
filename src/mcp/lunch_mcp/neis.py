import asyncio
from typing import Any

import httpx

from .errors import AppError, NeisNoData
from .settings import Settings

NO_DATA_CODES = {"INFO-200"}
SUCCESS_CODES = {"INFO-000"}


class NeisClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client

    async def _request(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        request_params = {"Key": self.settings.neis_api_key, "Type": "json", **params}
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            base_url=str(self.settings.neis_base_url).rstrip("/"),
            timeout=self.settings.neis_timeout_seconds,
        )
        try:
            for attempt in range(2):
                try:
                    response = await client.get(path, params=request_params)
                    if response.status_code >= 500 and attempt == 0:
                        await asyncio.sleep(0.05)
                        continue
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict):
                        raise ValueError("response root is not an object")
                    return data
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempt == 0:
                        await asyncio.sleep(0.05)
                        continue
                    if isinstance(exc, httpx.TimeoutException):
                        raise AppError(
                            "NEIS_TIMEOUT", "NEIS 서비스 응답이 지연되고 있습니다."
                        ) from exc
                    raise AppError(
                        "NEIS_UNAVAILABLE", "NEIS 서비스에 연결할 수 없습니다."
                    ) from exc
                except httpx.HTTPStatusError as exc:
                    raise AppError(
                        "NEIS_UNAVAILABLE", "NEIS 서비스 요청에 실패했습니다."
                    ) from exc
                except ValueError as exc:
                    raise AppError(
                        "NEIS_INVALID_RESPONSE", "NEIS 응답을 해석할 수 없습니다."
                    ) from exc
        finally:
            if owns_client:
                await client.aclose()
        raise AppError("NEIS_UNAVAILABLE", "NEIS 서비스 요청에 실패했습니다.")

    @staticmethod
    def _result_code(data: dict[str, Any], key: str) -> str | None:
        result = data.get("RESULT")
        if isinstance(result, dict):
            return str(result.get("CODE", ""))
        sections = data.get(key)
        if isinstance(sections, list):
            for section in sections:
                if not isinstance(section, dict):
                    continue
                head = section.get("head")
                if not isinstance(head, list):
                    continue
                for value in head:
                    nested_result = value.get("RESULT") if isinstance(value, dict) else None
                    if isinstance(nested_result, dict):
                        return str(nested_result.get("CODE", ""))
        return None

    @classmethod
    def _rows(cls, data: dict[str, Any], key: str) -> tuple[list[dict[str, Any]], int]:
        code = cls._result_code(data, key)
        if code in NO_DATA_CODES:
            raise NeisNoData
        if code not in SUCCESS_CODES:
            raise AppError("NEIS_ERROR", "NEIS 서비스가 요청을 처리하지 못했습니다.")

        sections = data.get(key)
        if not isinstance(sections, list):
            raise AppError("NEIS_INVALID_RESPONSE", "NEIS 응답 형식이 올바르지 않습니다.")
        rows: list[dict[str, Any]] = []
        total = 0
        for section in sections:
            if not isinstance(section, dict):
                continue
            if isinstance(section.get("row"), list):
                rows.extend(row for row in section["row"] if isinstance(row, dict))
            head = section.get("head")
            if isinstance(head, list):
                for value in head:
                    count = value.get("list_total_count") if isinstance(value, dict) else None
                    if isinstance(count, int):
                        total = count
        return rows, total or len(rows)

    async def search_schools(
        self, query: str, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        try:
            data = await self._request(
                "/schoolInfo",
                {"SCHUL_NM": query, "pIndex": 1, "pSize": page_size},
            )
            return self._rows(data, "schoolInfo")
        except NeisNoData:
            return [], 0

    async def get_school(self, office_code: str, school_code: str) -> dict[str, Any]:
        try:
            data = await self._request(
                "/schoolInfo",
                {
                    "ATPT_OFCDC_SC_CODE": office_code,
                    "SD_SCHUL_CODE": school_code,
                    "pIndex": 1,
                    "pSize": 1,
                },
            )
            rows, _ = self._rows(data, "schoolInfo")
        except NeisNoData as exc:
            raise AppError("SCHOOL_NOT_FOUND", "학교를 찾을 수 없습니다.") from exc
        if not rows:
            raise AppError("SCHOOL_NOT_FOUND", "학교를 찾을 수 없습니다.")
        return rows[0]

    async def get_meals(
        self, office_code: str, school_code: str, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        try:
            data = await self._request(
                "/mealServiceDietInfo",
                {
                    "ATPT_OFCDC_SC_CODE": office_code,
                    "SD_SCHUL_CODE": school_code,
                    "MMEAL_SC_CODE": "2",
                    "MLSV_FROM_YMD": start_date,
                    "MLSV_TO_YMD": end_date,
                    "pIndex": 1,
                    "pSize": 100,
                },
            )
            rows, _ = self._rows(data, "mealServiceDietInfo")
            return rows
        except NeisNoData:
            return []
