import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@fluentui/react-components", () => ({
  Badge: ({
    children,
    ...props
  }: React.HTMLAttributes<HTMLSpanElement> & {
    appearance?: string;
    color?: string;
  }) => {
    const { appearance: _appearance, color: _color, ...htmlProps } = props;
    return <span {...htmlProps}>{children}</span>;
  },
  Button: ({
    children,
    appearance: _appearance,
    size: _size,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    appearance?: string;
    size?: string;
  }) => <button {...props}>{children}</button>,
  Card: ({
    children,
    ...props
  }: React.HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div>,
  FluentProvider: ({
    children,
  }: {
    children: React.ReactNode;
    theme?: unknown;
  }) => <>{children}</>,
  Input: ({
    onChange,
    size: _size,
    ...props
  }: Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "size"> & {
    onChange?: (
      event: React.ChangeEvent<HTMLInputElement>,
      data: { value: string },
    ) => void;
    size?: string;
  }) => (
    <input
      {...props}
      onChange={(event) => onChange?.(event, { value: event.target.value })}
    />
  ),
  Spinner: ({ label }: { label?: string; size?: string }) => (
    <div role="status">{label}</div>
  ),
  webLightTheme: {},
}));

import App from "./App";

const school = {
  educationOfficeCode: "B10",
  schoolCode: "7010536",
  name: "예시고등학교",
  schoolType: "고등학교",
  region: "서울특별시",
};

const fetchMock = vi.fn<typeof fetch>(async (input) => {
  const url = new URL(String(input), "http://localhost");
  if (url.pathname === "/api/v1/schools") {
    return Response.json({
      items: [school],
      page: 1,
      pageSize: 20,
      totalCount: 1,
    });
  }
  if (url.pathname === "/api/v1/meals") {
    const from = url.searchParams.get("from")!;
    const to = url.searchParams.get("to")!;
    return Response.json({
      school,
      from,
      to,
      days: [
        {
          date: from,
          status: "available",
          meal: {
            date: from,
            mealType: "lunch",
            menuItems: [{ name: "현미밥", allergenCodes: [] }],
            caloriesKcal: 742.6,
            servings: null,
            nutrition: [],
            origins: [],
          },
        },
      ],
    });
  }
  return new Response(null, { status: 404 });
});

beforeEach(() => {
  fetchMock.mockClear();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderApp() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

describe("급식 조회", () => {
  it("두 글자 검색부터 학교 선택과 결과 표시까지 진행한다", async () => {
    const user = userEvent.setup();
    renderApp();

    const input = screen.getByLabelText("학교 이름");
    await user.type(input, "예");
    expect(
      screen.getByText("학교 이름을 두 글자 이상 입력해 주세요."),
    ).toBeInTheDocument();

    await user.type(input, "시");
    const option = await screen.findByRole("option", {
      name: /예시고등학교/,
    });
    await user.click(option);
    expect(screen.queryByLabelText("학교 이름")).not.toBeInTheDocument();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "학교 변경" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "중식 조회하기" }));
    expect(await screen.findByText("현미밥")).toBeInTheDocument();
    expect(await screen.findByText("현미밥")).toBeInTheDocument();
    expect(screen.getByText(/742\.6 kcal/)).toBeInTheDocument();
  });

  it("초기 날짜 범위가 오늘을 포함한 최근 7일이다", () => {
    renderApp();
    const range = screen.getByText(/선택 기간:/).textContent ?? "";
    const today = new Date();
    const sixDaysAgo = new Date(today);
    sixDaysAgo.setDate(today.getDate() - 6);
    const format = (value: Date) =>
      `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;

    expect(range).toContain(format(sixDaysAgo));
    expect(range).toContain(format(today));
  });
});
