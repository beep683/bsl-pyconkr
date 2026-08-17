# 급식 비교 멀티에이전트 서비스

기존 FastAPI 백엔드와 분리된 Microsoft Agent Framework 서비스입니다. 학교와 급식
데이터는 MCP 서버에서만 가져오고, GitHub Copilot SDK를 모델 공급자로 사용합니다.

## 워크플로우

1. MCP에서 무작위 학교 후보 10곳을 가져옵니다.
2. 선택된 두 학교의 같은 날짜 중식을 병렬 조회하며, 한 곳이라도 없으면 중단합니다.
3. 영양 균형(45%), 건강성(30%), 식재료 및 메뉴 품질(25%) 전문 에이전트를
   `ConcurrentBuilder`로 동시에 실행합니다.
4. 애플리케이션 코드가 `(평점 / 5) × 가중치`로 100점 총점을 계산합니다.
5. 최종 평가자는 점수를 바꾸지 않고 근거, 모순, 데이터 한계를 검증합니다.

`EVALUATION_RUBRIC.md`의 세 평가 영역과 별도 품질 게이트를 각각 세 전문 에이전트와
최종 평가자에게 대응시킵니다.

## 실행

GitHub Copilot CLI에 로그인하고 MCP 서버를 `localhost:8001`에서 실행한 다음:

```powershell
uv sync --project src/agent --extra dev --extra devui
uv run --project src/agent uvicorn app.main:app --reload --port 8002
```

- AG-UI: `POST http://localhost:8002/agent`
- 상태 확인: `GET http://localhost:8002/health`
- DevUI: `uv run --project src/agent python -m app.devui`

`GITHUB_COPILOT_MODEL`로 모델을 선택할 수 있으며 기본값은 `gpt-5-mini`입니다.
Copilot 인증 정보는 환경 변수나 저장소 파일에 저장하지 않고 로그인된 CLI 런타임을
사용합니다.
