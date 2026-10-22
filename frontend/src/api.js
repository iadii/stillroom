export async function request(path, options = {}) {
  const headers =
    options.body instanceof FormData
      ? {}
      : { "Content-Type": "application/json" };
  const response = await fetch(`/api${path}`, { headers, ...options });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`,
    );
  }
  return response.status === 204 ? null : response.json();
}

export function displayDate(
  value,
  options = { month: "short", day: "numeric", year: "numeric" },
) {
  if (!value) return "Undated";
  const parsed = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  return parsed.toLocaleString(undefined, options);
}

export function size(bytes) {
  return bytes < 1024
    ? `${bytes} B`
    : bytes < 1024 * 1024
      ? `${(bytes / 1024).toFixed(1)} KB`
      : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
