/* localStorage with parse safety. Per-viewer conveniences only; nothing here is authoritative. */

export const KEYS = Object.freeze({
  THEME: "walkshed-theme",
  BASEMAP: "walkshed-basemap",
});

export function getJSON(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch (e) {
    return fallback;
  }
}

export function setJSON(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    /* storage unavailable */
  }
}

export function remove(key) {
  try {
    localStorage.removeItem(key);
  } catch (e) {
    /* storage unavailable */
  }
}
