/* Fetch helpers. Every call is same-origin and every /api answer is unwrapped from the envelope. */

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function getJson(path, { signal } = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
    signal,
  });
  if (res.status === 429) throw new ApiError("Too many requests. Wait a moment.", 429);
  const body = await res.json().catch(() => null);
  if (!res.ok || !body || body.success !== true) {
    throw new ApiError((body && body.error) || "Request failed.", res.status);
  }
  return Object.freeze({ data: body.data, meta: body.meta });
}

export async function getGeo(path, { optional = false, signal } = {}) {
  const res = await fetch(path, { credentials: "same-origin", signal });
  if (!res.ok) {
    if (optional) return null;
    throw new ApiError("Map data did not load.", res.status);
  }
  return res.json();
}

/* Follow pagination until every row is collected. */
export async function getAll(path, limit = 500) {
  const rows = [];
  let offset = 0;
  for (;;) {
    const sep = path.includes("?") ? "&" : "?";
    const { data, meta } = await getJson(`${path}${sep}limit=${limit}&offset=${offset}`);
    rows.push(...data);
    offset += data.length;
    if (!meta || !data.length || offset >= meta.total) break;
  }
  return rows;
}
