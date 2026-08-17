import os

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from .errors import AppError
from .models import MealRangeResult, SchoolSearchResult
from .neis import NeisClient
from .service import LunchService
from .settings import get_settings


def create_server(service: LunchService | None = None) -> FastMCP:
    server = FastMCP(
        "school-lunch",
        instructions=(
            "NEIS 공개 데이터를 사용해 학교를 검색하고 학교별 중식 정보를 조회합니다. "
            "search_schools 또는 get_random_schools로 학교 식별 코드를 확인한 뒤 "
            "get_lunch_meals를 호출하세요."
        ),
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "8000")),
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )

    def get_service() -> LunchService:
        return service or LunchService(NeisClient(get_settings()))

    @server.tool()
    async def search_schools(query: str, page_size: int = 20) -> SchoolSearchResult:
        """학교 이름 일부로 후보 학교와 교육청·학교 식별 정보를 조회합니다."""
        try:
            return await get_service().search_schools(query, page_size)
        except AppError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from exc

    @server.tool()
    async def get_random_schools(count: int = 10) -> SchoolSearchResult:
        """전국 학교 중 서로 다른 후보를 무작위로 반환합니다."""
        try:
            return await get_service().get_random_schools(count)
        except AppError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from exc

    @server.tool()
    async def get_lunch_meals(
        education_office_code: str,
        school_code: str,
        start_date: str,
        end_date: str,
    ) -> MealRangeResult:
        """선택한 학교의 기간별 중식 메뉴, 열량, 영양정보와 원산지를 조회합니다.

        start_date와 end_date는 YYYY-MM-DD 형식이며 조회 기간은 최대 31일입니다.
        """
        try:
            return await get_service().get_lunch_meals(
                education_office_code,
                school_code,
                start_date,
                end_date,
            )
        except AppError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from exc

    return server


mcp = create_server()


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
