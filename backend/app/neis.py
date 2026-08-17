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
                    status = 504 if isinstance(exc, httpx.TimeoutException) else 502
                    code = "NEIS_TIMEOUT" if status == 504 else "NEIS_UNAVAILABLE"
                    raise AppError(status, code, "NEIS 서비스에 연결할 수 없습니다.") from exc
                except httpx.HTTPStatusError as exc:
                    raise AppError(502, "NEIS_UNAVAILABLE", "NEIS 서비스 요청에 실패했습니다.") from exc
                except ValueError as exc:
                    raise AppError(502, "NEIS_INVALID_RESPONSE", "NEIS 응답을 해석할 수 없습니다.") from exc
        finally:
            if owns_client:
                await client.aclose()
        raise AppError(502, "NEIS_UNAVAILABLE", "NEIS 서비스 요청에 실패했습니다.")

    @staticmethod
    def _rows(data: dict[str, Any], key: str) -> tuple[list[dict[str, Any]], int]:
        top_result = data.get("RESULT")
        if isinstance(top_result, dict):
            code = top_result.get("CODE")
            if code in NO_DATA_CODES:
                raise NeisNoData
            if code not in SUCCESS_CODES:
                raise AppError(502, "NEIS_ERROR", "NEIS 서비스가 요청을 처리하지 못했습니다.")

        sections = data.get(key)
        if not isinstance(sections, list):
            raise AppError(502, "NEIS_INVALID_RESPONSE", "NEIS 응답 형식이 올바르지 않습니다.")
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
                    if isinstance(value, dict) and isinstance(value.get("list_total_count"), int):
                        total = value["list_total_count"]
        return rows, total or len(rows)

    async def search_schools(
        self, query: str, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        try:
            data = await self._request(
                "/schoolInfo",
                {"SCHUL_NM": query, "pIndex": page, "pSize": page_size},
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
            raise AppError(404, "SCHOOL_NOT_FOUND", "학교를 찾을 수 없습니다.") from exc
        if not rows:
            raise AppError(404, "SCHOOL_NOT_FOUND", "학교를 찾을 수 없습니다.")
        return rows[0]

    async def get_meals(
        self, office_code: str, school_code: str, from_date: str, to_date: str
    ) -> list[dict[str, Any]]:
        try:
            data = await self._request(
                "/mealServiceDietInfo",
                {
                    "ATPT_OFCDC_SC_CODE": office_code,
                    "SD_SCHUL_CODE": school_code,
                    "MMEAL_SC_CODE": "2",
                    "MLSV_FROM_YMD": from_date,
                    "MLSV_TO_YMD": to_date,
                    "pIndex": 1,
                    "pSize": 100,
                },
            )
            rows, _ = self._rows(data, "mealServiceDietInfo")
            return rows
        except NeisNoData:
            return []
