import { Badge, Button, Card, Spinner } from "@fluentui/react-components";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  allowedAnalysisDates,
  createAnalysisAgentClient,
  type AnalysisAgentClient,
} from "./client";
import {
  INITIAL_ANALYSIS_STATE,
  type AnalysisResult,
  type AnalysisState,
  type EvaluationArea,
} from "./types";

const AREA_LABELS: Record<EvaluationArea, string> = {
  nutrition: "영양 균형",
  health: "건강성",
  menu_quality: "식재료 및 메뉴 품질",
};

const PHASE_LABELS: Partial<Record<AnalysisState["phase"], string>> = {
  loading_candidates: "학교 후보를 준비하고 있습니다.",
  loading_meals: "MCP에서 두 학교의 중식을 확인하고 있습니다.",
  evaluating: "세 전문 평가자가 동시에 분석하고 있습니다.",
  judging: "최종 평가자가 근거와 데이터 한계를 검증하고 있습니다.",
};

function defaultPrompt(state: AnalysisState): string {
  const selected = state.selectedSchoolCodes.map(
    (code) => state.candidates.find((school) => school.schoolCode === code)?.name,
  );
  if (selected.some((name) => !name) || !state.selectedDate) {
    return "선택한 두 학교의 같은 날짜 중식을 평가 루브릭에 따라 비교해 주세요.";
  }
  return `${state.selectedDate}의 ${selected[0]}와 ${selected[1]} 중식을 평가 루브릭에 따라 비교하고, 근거와 개선안을 한국어로 설명해 주세요.`;
}

function ResultPanel({ result }: { result: AnalysisResult }) {
  const winnerName =
    result.judge.winner === "school_a"
      ? result.schoolAScore.school.name
      : result.judge.winner === "school_b"
        ? result.schoolBScore.school.name
        : "동점";
  return (
    <section className="analysis-results" aria-labelledby="analysis-result-heading">
      <p className="eyebrow">분석 완료</p>
      <h2 id="analysis-result-heading">{result.judge.headline}</h2>
      <Badge appearance="filled" color="success">
        결과: {winnerName}
      </Badge>
      <div className="score-grid">
        {[result.schoolAScore, result.schoolBScore].map((score) => (
          <Card className="score-card" key={score.school.schoolCode}>
            <h3>{score.school.name}</h3>
            <strong className="total-score">{score.total.toFixed(1)}점</strong>
            <dl>
              {score.areas.map((area) => (
                <div key={area.area}>
                  <dt>
                    {AREA_LABELS[area.area]} ({area.weight}%)
                  </dt>
                  <dd>
                    {area.rating}/5 · {area.weightedScore.toFixed(1)}점
                  </dd>
                </div>
              ))}
            </dl>
          </Card>
        ))}
      </div>
      <div className="evaluation-grid">
        {result.evaluations.map((evaluation) => (
          <Card className="evaluation-card" key={evaluation.area}>
            <h3>{AREA_LABELS[evaluation.area]}</h3>
            <p>{evaluation.comparison}</p>
            <strong>{result.schoolAScore.school.name}</strong>
            <ul>{evaluation.schoolA.evidence.map((item) => <li key={item}>{item}</li>)}</ul>
            <strong>{result.schoolBScore.school.name}</strong>
            <ul>{evaluation.schoolB.evidence.map((item) => <li key={item}>{item}</li>)}</ul>
          </Card>
        ))}
      </div>
      <Card className="judge-card">
        <h3>최종 품질 게이트</h3>
        <ul>{result.judge.rationale.map((item) => <li key={item}>{item}</li>)}</ul>
        <h3>{result.schoolAScore.school.name} 개선안</h3>
        <ul>{result.judge.schoolAImprovements.map((item) => <li key={item}>{item}</li>)}</ul>
        <h3>{result.schoolBScore.school.name} 개선안</h3>
        <ul>{result.judge.schoolBImprovements.map((item) => <li key={item}>{item}</li>)}</ul>
        {[...result.judge.qualityNotes, ...result.judge.limitations].length > 0 && (
          <>
            <h3>검증 메모 및 데이터 한계</h3>
            <ul>
              {[...result.judge.qualityNotes, ...result.judge.limitations].map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </>
        )}
      </Card>
    </section>
  );
}

export default function AnalysisPage() {
  const client = useRef<AnalysisAgentClient | null>(null);
  if (client.current === null) {
    client.current = createAnalysisAgentClient();
  }
  const [state, setState] = useState(INITIAL_ANALYSIS_STATE);
  const [prompt, setPrompt] = useState(defaultPrompt(INITIAL_ANALYSIS_STATE));
  const [promptEdited, setPromptEdited] = useState(false);
  const [requestError, setRequestError] = useState("");
  const bounds = useMemo(() => allowedAnalysisDates(), []);
  const busy = [
    "loading_candidates",
    "loading_meals",
    "evaluating",
    "judging",
  ].includes(state.phase);

  useEffect(() => {
    const activeClient = client.current ?? createAnalysisAgentClient();
    client.current = activeClient;
    activeClient.loadCandidates(setState).catch((error: unknown) => {
      setRequestError(
        error instanceof Error ? error.message : "학교 후보를 불러오지 못했습니다.",
      );
    });
    return () => {
      activeClient.abort();
      if (client.current === activeClient) {
        client.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!promptEdited) {
      setPrompt(defaultPrompt(state));
    }
  }, [promptEdited, state]);

  const toggleSchool = (schoolCode: string) => {
    setState((current) => {
      const selected = current.selectedSchoolCodes.includes(schoolCode)
        ? current.selectedSchoolCodes.filter((code) => code !== schoolCode)
        : current.selectedSchoolCodes.length < 2
          ? [...current.selectedSchoolCodes, schoolCode]
          : current.selectedSchoolCodes;
      return { ...current, selectedSchoolCodes: selected, result: null, error: null };
    });
  };

  const analyze = async () => {
    setRequestError("");
    if (state.selectedSchoolCodes.length !== 2) {
      setRequestError("서로 다른 학교를 정확히 두 곳 선택해 주세요.");
      return;
    }
    if (!state.selectedDate) {
      setRequestError("분석할 날짜를 선택해 주세요.");
      return;
    }
    if (!prompt.trim()) {
      setRequestError("분석 프롬프트를 입력해 주세요.");
      return;
    }
    try {
      await client.current?.analyze(state, prompt.trim(), setState);
    } catch (error) {
      setRequestError(
        error instanceof Error ? error.message : "분석 요청을 완료하지 못했습니다.",
      );
    }
  };

  return (
    <main>
      <section className="analysis-hero">
        <p className="eyebrow">MULTI-AGENT LUNCH REVIEW</p>
        <h1>급식 분석</h1>
        <p className="hero-copy">
          세 전문 에이전트가 동시에 평가하고 최종 평가자가 근거와 데이터 한계를
          검증합니다.
        </p>
      </section>

      <section className="setup-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">STEP 1</p>
            <h2>학교 두 곳을 선택하세요</h2>
          </div>
          <Button
            disabled={busy}
            onClick={() => client.current?.loadCandidates(setState)}
          >
            후보 새로고침
          </Button>
        </div>
        {state.phase === "loading_candidates" ? (
          <Spinner label="무작위 학교 10곳을 불러오는 중입니다." />
        ) : (
          <div className="candidate-grid" role="group" aria-label="학교 후보 10곳">
            {state.candidates.map((school) => {
              const selected = state.selectedSchoolCodes.includes(school.schoolCode);
              return (
                <button
                  aria-pressed={selected}
                  className={`candidate-card${selected ? " selected" : ""}`}
                  key={school.schoolCode}
                  onClick={() => toggleSchool(school.schoolCode)}
                  type="button"
                >
                  <strong>{school.name}</strong>
                  <span>{school.schoolType} · {school.region}</span>
                </button>
              );
            })}
          </div>
        )}
        <p className="hint">{state.selectedSchoolCodes.length}/2개 학교 선택</p>
      </section>

      <section className="setup-card">
        <p className="eyebrow">STEP 2</p>
        <h2>날짜와 프롬프트를 확인하세요</h2>
        <label htmlFor="analysis-date">분석 날짜</label>
        <input
          id="analysis-date"
          max={bounds.max}
          min={bounds.min}
          onChange={(event) =>
            setState((current) => ({
              ...current,
              selectedDate: event.target.value || null,
              result: null,
            }))
          }
          type="date"
          value={state.selectedDate ?? ""}
        />
        <label htmlFor="analysis-prompt">분석 프롬프트</label>
        <textarea
          id="analysis-prompt"
          onChange={(event) => {
            setPromptEdited(true);
            setPrompt(event.target.value);
          }}
          rows={5}
          value={prompt}
        />
        <Button
          appearance="primary"
          className="submit-button"
          disabled={busy}
          onClick={analyze}
          size="large"
        >
          분석 시작
        </Button>
      </section>

      {PHASE_LABELS[state.phase] && (
        <div className="status-panel" role="status">
          <Spinner size="small" label={PHASE_LABELS[state.phase]} />
        </div>
      )}
      {(requestError || state.error) && (
        <div className="status-panel error" role="alert">
          {requestError || state.error?.message}
        </div>
      )}
      {state.result && <ResultPanel result={state.result} />}
    </main>
  );
}
