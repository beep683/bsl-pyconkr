export function toDateString(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function getSeoulToday(now = new Date()): Date {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).formatToParts(now);
  const values = Object.fromEntries(
    parts
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, Number(part.value)]),
  );
  return new Date(values.year, values.month - 1, values.day);
}

export function getAllowedDates(today = getSeoulToday()): {
  minimum: Date;
  maximum: Date;
} {
  return {
    minimum: new Date(today.getFullYear(), today.getMonth() - 1, 1),
    maximum: new Date(today.getFullYear(), today.getMonth() + 1, 0),
  };
}

export function getInitialRange(today = getSeoulToday()): {
  from: Date;
  to: Date;
} {
  const from = new Date(today);
  from.setDate(from.getDate() - 6);
  return { from, to: today };
}
