import asyncio
import json
from datetime import date
from typing import Any

from agent_framework import Agent, ChatResponse, Message

from app.schemas import (
    AnalysisResult,
    EvaluationArea,
    MealData,
    MenuItem,
    SchoolCandidate,
)
from app.workflow import build_evaluation_workflow, evaluation_prompt


class FakeChatClient:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def get_response(
        self,
        messages: list[Message],
        *,
        stream: bool = False,
        options: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> ChatResponse[Any]:
        assert messages
        assert not stream
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        instructions = str((options or {}).get("instructions", ""))
        if "Final Judge" in instructions:
            payload = {
                "winner": "school_a",
                "headline": "가학교 우세",
                "rationale": ["총점이 더 높습니다."],
                "schoolAImprovements": ["과일을 추가합니다."],
                "schoolBImprovements": ["채소를 추가합니다."],
            }
        else:
            area = (
                "nutrition"
                if "Nutrition Agent" in instructions
                else "health"
                if "Health Agent" in instructions
                else "menu_quality"
            )
            assessment_a = {
                "score": 5,
                "evidence": ["현미밥"],
                "improvements": ["과일을 추가합니다."],
            }
            assessment_b = {
                "score": 3,
                "evidence": ["기본 구성"],
                "improvements": ["채소를 추가합니다."],
            }
            payload = {
                "area": area,
                "schoolA": assessment_a,
                "schoolB": assessment_b,
                "comparison": "가학교가 우수합니다.",
            }
        return ChatResponse(
            messages=[
                Message(
                    role="assistant",
                    contents=[json.dumps(payload, ensure_ascii=False)],
                )
            ]
        )


def meal(code: str, name: str) -> MealData:
    return MealData(
        school=SchoolCandidate(
            education_office_code="B10",
            school_code=code,
            name=name,
            school_type="고등학교",
            region="서울특별시",
        ),
        date=date(2026, 8, 17),
        menu_items=[MenuItem(name="현미밥")],
        calories_kcal=700,
    )


async def test_specialists_run_concurrently_before_final_judge() -> None:
    client = FakeChatClient()
    instructions = {
        EvaluationArea.NUTRITION: "# Nutrition Agent",
        EvaluationArea.HEALTH: "# Health Agent",
        EvaluationArea.MENU_QUALITY: "# Menu Quality Agent",
    }

    def factory(name: str, agent_instructions: str) -> Agent:
        return Agent(client, name=name, instructions=agent_instructions)

    meal_a = meal("1", "가학교")
    meal_b = meal("2", "나학교")
    workflow = build_evaluation_workflow(
        factory,
        instructions,
        "# Final Judge",
        meal_a,
        meal_b,
    )

    events = await workflow.run(evaluation_prompt(meal_a, meal_b))
    result = events.get_outputs()[0]

    assert isinstance(result, AnalysisResult)
    assert client.max_active == 3
    assert result.school_a_score.total == 100
    assert result.school_b_score.total == 60
    assert result.judge.winner == "school_a"
