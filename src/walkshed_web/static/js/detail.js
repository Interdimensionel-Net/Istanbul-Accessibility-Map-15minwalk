/* Station panel, filled from /api/stations/{sid}. */
import { getJson } from "./api.js";
import { $, chip, esc, fmt } from "./format.js";
import { showError } from "./toast.js";

const GOOGLE_MAPS = "https://www.google.com/maps/search/?api=1&query=";

export function createDetail({ onClose }) {
  const panel = $("#station");
  let current = null;

  function render(s) {
    current = s;
    $("#st-name").textContent = s.name;
    $("#st-codes").innerHTML = s.lines.map(chip).join("");
    $("#st-meta").innerHTML =
      s.line_names.map((l) => `<div>${esc(l.code)} ${esc(l.name)}</div>`).join("") + `<div class="op">${esc(s.operator)}</div>`;
    const bands = s.bands || [];
    $("#st-hero").hidden = !bands.length;
    $("#st-none").hidden = Boolean(bands.length);
    if (bands.length) {
      const widest = s.widest || bands[bands.length - 1];
      const max = widest.km2 || 1;
      $("#st-big").textContent = fmt(widest.km2, 1);
      $("#st-big-min").textContent = widest.minutes;
      $("#st-bars").innerHTML = bands
        .map((b) => `<span class="lbl">${b.minutes} min</span><span class="bar"><i style="width:${((100 * b.km2) / max).toFixed(1)}%"></i></span><span class="v">${fmt(b.km2, 2)} km²</span>`)
        .join("");
    }
    $("#st-gmaps").href = GOOGLE_MAPS + encodeURIComponent(`${s.lat},${s.lon}`);
    panel.hidden = false;
  }

  async function open(sid) {
    try {
      const { data } = await getJson(`/api/stations/${encodeURIComponent(sid)}`);
      render(data);
      return data;
    } catch (e) {
      showError(e.message || "Station did not load.");
      return null;
    }
  }

  function close() {
    current = null;
    panel.hidden = true;
  }

  panel.querySelector(".close-btn:not(.back)").addEventListener("click", () => {
    close();
    onClose();
  });

  return Object.freeze({ open, close, current: () => current, isOpen: () => !panel.hidden });
}
