import json
from datetime import date
from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas import MealData, SchoolCandidate


def candidate(index: int) -> SchoolCandidate:
    return SchoolCandidate(
        education_office_code="B10",
        school_code=str(index),
        name=f"{index}학교",
        school_type="고등학교",
        region="서울특별시",
    )


class CandidateDataSource:
    async def random_schools(self, count: int = 10) -> list[SchoolCandidate]:
        return [candidate(index) for index in range(count)]

    async def meals_for(
        self,
        school_a: SchoolCandidate,
        school_b: SchoolCandidate,
        analysis_date: date,
    ) -> tuple[MealData, MealData]:
        raise AssertionError("meals_for should not run")


def decode_sse(response_text: str) -> list[dict[str, Any]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in response_text.splitlines()
        if line.startswith("data: ")
    ]


def test_candidate_request_streams_exactly_ten_schools() -> None:
    app = create_app(
        data_source=CandidateDataSource(),
        agent_factory=lambda _name, _instructions: None,
    )

    with TestClient(app) as client:
        response = client.post(
            "/agent",
            json={
                "threadId": "thread-1",
                "runId": "run-1",
                "messages": [],
                "state": {"action": "load_candidates"},
            },
        )

    assert response.status_code == 200
    events = decode_sse(response.text)
    snapshots = [
        event["snapshot"]
        for event in events
        if event["type"] == "STATE_SNAPSHOT"
    ]
    assert snapshots[-1]["phase"] == "selecting"
    assert len(snapshots[-1]["candidates"]) == 10
    assert events[0]["type"] == "RUN_STARTED"
    assert events[-1]["type"] == "RUN_FINISHED"
