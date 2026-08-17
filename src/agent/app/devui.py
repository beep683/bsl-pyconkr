from datetime import date

from agent_framework.devui import serve
from agent_framework_github_copilot import GitHubCopilotAgent

from .config import get_settings
from .instructions import InstructionLoader
from .schemas import EvaluationArea, MealData, MenuItem, SchoolCandidate
from .workflow import build_evaluation_workflow


def main() -> None:
    settings = get_settings()
    loader = InstructionLoader()

    def factory(name: str, instructions: str) -> GitHubCopilotAgent:
        return GitHubCopilotAgent(
            name=name,
            instructions=instructions,
            default_options={
                "model": settings.github_copilot_model,
                "timeout": settings.github_copilot_timeout,
            },
        )

    def sample_meal(code: str, name: str) -> MealData:
        return MealData(
            school=SchoolCandidate(
                education_office_code="B10",
                school_code=code,
                name=name,
                school_type="고등학교",
                region="서울특별시",
            ),
            date=date.today(),
            menu_items=[MenuItem(name="현미밥"), MenuItem(name="된장국")],
            calories_kcal=700,
        )

    workflow = build_evaluation_workflow(
        factory,
        {area: loader.specialist(area) for area in EvaluationArea},
        loader.judge(),
        sample_meal("sample-a", "샘플 A학교"),
        sample_meal("sample-b", "샘플 B학교"),
    )
    serve(entities=[workflow], port=8080, auto_open=True)


if __name__ == "__main__":
    main()
