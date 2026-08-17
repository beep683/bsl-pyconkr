import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@fluentui/react-components", () => ({
  Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
  Button: ({
    children,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    appearance?: string;
    size?: string;
  }) => {
    const { appearance: _appearance, size: _size, ...htmlProps } = props;
    return <button {...htmlProps}>{children}</button>;
  },
  Card: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  FluentProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
  Spinner: ({ label }: { label?: string }) => <div role="status">{label}</div>,
  webLightTheme: {},
}));

const analyze = vi.fn();
const schools = Array.from({ length: 10 }, (_, index) => ({
  educationOfficeCode: "B10",
  schoolCode: String(index),
  name: `${index}학교`,
  schoolType: "고등학교",
  region: "서울특별시",
}));

vi.mock("./client", () => ({
  allowedAnalysisDates: () => ({ min: "2026-07-01", max: "2026-08-17" }),
  createAnalysisAgentClient: () => ({
    loadCandidates: async (onState: (state: unknown) => void) => {
      onState({
        action: null,
        phase: "selecting",
        candidates: schools,
        selectedSchoolCodes: [],
        selectedDate: null,
        result: null,
        error: null,
      });
    },
    analyze,
    abort: vi.fn(),
  }),
}));

import App from "../App";

function renderApp() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  window.history.pushState({}, "", "/analysis");
  analyze.mockReset();
  analyze.mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
  window.history.pushState({}, "", "/");
});

describe("급식 분석", () => {
  it("후보 10곳에서 두 학교와 날짜를 선택하고 수정한 프롬프트를 전송한다", async () => {
    const user = userEvent.setup();
    renderApp();

    const group = await screen.findByRole("group", { name: "학교 후보 10곳" });
    expect(within(group).getAllByRole("button")).toHaveLength(10);
    await user.click(within(group).getByRole("button", { name: /0학교/ }));
    await user.click(within(group).getByRole("button", { name: /1학교/ }));
    expect(screen.getByText("2/2개 학교 선택")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("분석 날짜"), {
      target: { value: "2026-08-17" },
    });
    const prompt = screen.getByLabelText("분석 프롬프트");
    await user.clear(prompt);
    await user.type(prompt, "근거 중심으로 비교해 주세요.");
    await user.click(screen.getByRole("button", { name: "분석 시작" }));

    expect(analyze).toHaveBeenCalledOnce();
    expect(analyze.mock.calls[0][0].selectedSchoolCodes).toEqual(["0", "1"]);
    expect(analyze.mock.calls[0][0].selectedDate).toBe("2026-08-17");
    expect(analyze.mock.calls[0][1]).toBe("근거 중심으로 비교해 주세요.");
  });
});
