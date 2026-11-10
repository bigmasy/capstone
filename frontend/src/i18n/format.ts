const numberFormat = new Intl.NumberFormat("uk-UA", { maximumFractionDigits: 1 });
const dateFormat = new Intl.DateTimeFormat("uk-UA", { dateStyle: "long", timeStyle: "short" });

/** Formats points with at most one decimal and the Ukrainian decimal comma, such as `11,2`. */
export function formatPoints(value: number): string {
  return numberFormat.format(value);
}

/** Formats an ISO timestamp from the API as a long local date with the time. */
export function formatDateTime(iso: string): string {
  return dateFormat.format(new Date(iso));
}

const dayFormat = new Intl.DateTimeFormat("uk-UA", { day: "numeric", month: "long", year: "numeric" });

/** Formats a timestamp as a date only, such as "10 листопада 2026 р.". */
export function formatDate(iso: string): string {
  return dayFormat.format(new Date(iso));
}
