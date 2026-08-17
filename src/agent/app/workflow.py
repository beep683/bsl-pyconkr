from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from agent_framework import (
    AgentExecutorRequest,
    AgentExecutorResponse,
    Executor,
    Workflow,
    WorkflowContext,
    handler,
)
from agent_framework_orchestrations import ConcurrentBuilder
from typing_extensions import Never

from .schemas import (
    AnalysisResult,
    EvaluationArea,
    JudgeReport,
    MealData,
    SpecialistEvaluation,
)
from .scoring import calculate_school_scores

AgentFactory = Callable[[str, str], Any]


class EvaluationWorkflowError(RuntimeError):
    """Raised when a Copilot agent returns an invalid evaluation."""


class CopilotSpecialistExecutor(Executor):
    def __init__(
        self,
        name: str,
        instructions: str,
        agent_factory: AgentFactory,
    ) -> None:
        super().__init__(name)
        self._instructions = instructions
        self._agent_factory = agent_factory

    @handler
    async def evaluate(
        self,
        request: AgentExecutorRequest,
        ctx: WorkflowContext[AgentExecutorResponse],
    ) -> None:
        agent = self._agent_factory(self.id, self._instructions)
        async with _started_agent(agent) as running:
            response = await running.run(request.messages)
        await ctx.send_message(
            AgentExecutorResponse(
                self.id,
                response,
                full_conversation=list(request.messages) + list(response.messages),
            )
        )


class JudgeAggregator(Executor):
    def __init__(
        self,
        instructions: str,
        agent_factory: AgentFactory,
        school_a: MealData,
        school_b: MealData,
    ) -> None:
        super().__init__("final-judge")
        self._instructions = instructions
        self._agent_factory = agent_factory
        self._school_a = school_a
        self._school_b = school_b

    @handler
    async def aggregate(
        self,
        results: list[AgentExecutorResponse],
        ctx: WorkflowContext[Never, AnalysisResult],
    ) -> None:
        evaluations = self._validated_evaluations(results)
        score_a, score_b = calculate_school_scores(
            self._school_a.school,
            self._school_b.school,
            evaluations,
        )
        payload = {
            "schoolA": self._school_a.model_dump(mode="json", by_alias=True),
            "schoolB": self._school_b.model_dump(mode="json", by_alias=True),
            "evaluations": [
                item.model_dump(mode="json", by_alias=True) for item in evaluations
            ],
            "schoolAScore": score_a.model_dump(mode="json", by_alias=True),
            "schoolBScore": score_b.model_dump(mode="json", by_alias=True),
            "requiredWinner": _winner(score_a.total, score_b.total),
        }
        judge = self._agent_factory(self.id, self._instructions)
        async with _started_agent(judge) as running:
            response = await running.run(
                "다음 결과를 품질 검증하고 JSON 최종 보고서를 작성하세요.\n"
                + json.dumps(payload, ensure_ascii=False)
            )
        judge = _parse_model(response.text, JudgeReport)
        if judge.winner != payload["requiredWinner"]:
            raise EvaluationWorkflowError(
                "Final judge changed the deterministically calculated winner."
            )
        await ctx.yield_output(
            AnalysisResult(
                analysis_date=self._school_a.date,
                school_a_meal=self._school_a,
                school_b_meal=self._school_b,
                evaluations=evaluations,
                school_a_score=score_a,
                school_b_score=score_b,
                judge=judge,
            )
        )

    @staticmethod
    def _validated_evaluations(
        results: list[AgentExecutorResponse],
    ) -> list[SpecialistEvaluation]:
        expected = {
            f"{area.value}-agent": area
            for area in EvaluationArea
        }
        evaluations: dict[EvaluationArea, SpecialistEvaluation] = {}
        for result in results:
            area = expected.get(result.executor_id)
            if area is None:
                raise EvaluationWorkflowError(
                    f"Unexpected specialist result from {result.executor_id}."
                )
            evaluation = _parse_model(
                result.agent_response.text,
                SpecialistEvaluation,
            )
            if evaluation.area != area:
                raise EvaluationWorkflowError(
                    f"{result.executor_id} returned the wrong evaluation area."
                )
            evaluations[area] = evaluation
        if set(evaluations) != set(EvaluationArea):
            raise EvaluationWorkflowError(
                "Specialist results do not cover each rubric area exactly once."
            )
        return [evaluations[area] for area in EvaluationArea]


def build_evaluation_workflow(
    agent_factory: AgentFactory,
    specialist_instructions: dict[EvaluationArea, str],
    judge_instructions: str,
    school_a: MealData,
    school_b: MealData,
) -> Workflow:
    if set(specialist_instructions) != set(EvaluationArea):
        raise ValueError("One specialist per rubric area is required.")
    specialists = [
        CopilotSpecialistExecutor(
            f"{area.value}-agent",
            specialist_instructions[area],
            agent_factory,
        )
        for area in EvaluationArea
    ]
    aggregator = JudgeAggregator(
        judge_instructions,
        agent_factory,
        school_a,
        school_b,
    )
    return (
        ConcurrentBuilder(participants=specialists)
        .with_aggregator(aggregator)
        .build()
    )


def evaluation_prompt(
    school_a: MealData,
    school_b: MealData,
    user_prompt: str | None = None,
) -> str:
    payload = {
        "schoolA": school_a.model_dump(mode="json", by_alias=True),
        "schoolB": school_b.model_dump(mode="json", by_alias=True),
    }
    prefix = (
        f"사용자 요청: {user_prompt}\n\n"
        if user_prompt
        else ""
    )
    return (
        prefix
        + "같은 날짜 두 학교 중식을 담당 영역의 루브릭으로 각각 평가하세요. "
        "입력에 없는 사실이나 수치를 만들지 마세요.\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def _parse_model(text: str, model: type[Any]) -> Any:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        candidate = "\n".join(lines[1:-1]).strip()
    try:
        return model.model_validate_json(candidate)
    except ValueError as exc:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            try:
                return model.model_validate_json(candidate[start : end + 1])
            except ValueError:
                pass
        raise EvaluationWorkflowError(
            f"{model.__name__} JSON response is invalid."
        ) from exc


def _winner(score_a: float, score_b: float) -> str:
    if score_a == score_b:
        return "tie"
    return "school_a" if score_a > score_b else "school_b"


@asynccontextmanager
async def _started_agent(agent: Any) -> AsyncIterator[Any]:
    if hasattr(agent, "__aenter__") and hasattr(agent, "__aexit__"):
        async with agent as running:
            yield running
    else:
        yield agent
