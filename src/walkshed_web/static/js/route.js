/* Route panel: isolate a line, reveal each stop's walkshed in order, count the numbers up. */
import { $, $$, chip, esc, fmt, isPhone } from "./format.js";
import { lineColor } from "./lineColors.js";
import { ROUTE_SNAPS } from "./sheet.js";

const FADE_MS = 380;

export function createRoute({ view, model, onClose, onPickStop = () => {} }) {
  const box = $("#route");
  let play = null;
  let current = null;

  function cancel() {
    if (play) {
      play.cancelled = true;
      play = null;
    }
  }

  function fill(line, sids, perStop, total) {
    const stops = line.stops || [];
    const matched = sids.filter(Boolean).length;
    const len = line.length_km || 0;
    const widest = Math.max(...(model.meta.bands || [900]));
    $("#rt-name").textContent = line.name;
    $("#rt-codes").innerHTML = chip(line.code);
    $("#rt-meta").innerHTML = `<div>${esc(line.operator)}</div><div class="op">${esc(line.mode.replace(/_/g, " "))} · ${stops.length} official stops, ${matched} on the map</div>`;
    $("#rt-min").textContent = widest / 60;
    $("#rt-stops").textContent = fmt(stops.length);
    $("#rt-len").textContent = len ? fmt(len, 1) : "–";
    $("#rt-avg").textContent = matched ? fmt(total / matched, 2) : "–";
    $("#rt-density").textContent = len ? fmt(stops.length / len, 2) : "–";
    const bars = $("#rt-bars");
    bars.style.setProperty("--rt-color", lineColor(line.code));
    bars.innerHTML = stops
      .map((s, i) => `<button type="button" class="nm${sids[i] ? "" : " none"}" title="${esc(s.name)}" aria-pressed="false"${sids[i] ? ` data-sid="${esc(sids[i])}"` : " disabled"}>${esc(s.name)}</button><span class="bar"><i data-i="${i}"></i></span><span class="v">${sids[i] ? fmt(perStop[i], 2) : "–"}</span>`)
      .join("");
  }

  function animate(sids, perStop, total) {
    cancel();
    const token = { cancelled: false };
    play = token;
    const setters = view.routeLayers(sids.filter(Boolean));
    const max = Math.max(1, ...perStop);
    const sum = perStop.reduce((a, b) => a + b, 0) || 1;
    const stepMs = Math.max(60, Math.min(160, 2400 / Math.max(1, sids.length)));
    const totalMs = stepMs * sids.length + FADE_MS;
    const big = $("#rt-big");
    const bars = Array.from($("#rt-bars").querySelectorAll("i[data-i]"));
    const start = performance.now();
    function frame(now) {
      if (token.cancelled) return;
      const elapsed = now - start;
      let done = 0;
      sids.forEach((sid, i) => {
        const k = Math.max(0, Math.min(1, (elapsed - i * stepMs) / FADE_MS));
        done += perStop[i] * k;
        if (bars[i]) bars[i].style.width = `${((100 * perStop[i] * k) / max).toFixed(1)}%`;
        const set = sid && setters.get(sid);
        if (set) set(k);
      });
      big.textContent = fmt(total * Math.min(1, done / sum), 1);
      if (elapsed < totalMs) requestAnimationFrame(frame);
      else {
        big.textContent = fmt(total, 1);
        play = null;
      }
    }
    requestAnimationFrame(frame);
  }

  function open(line) {
    view.clearStop();
    current = line;
    const stops = line.stops || [];
    const sids = stops.map((s) => (s.sid == null ? null : String(s.sid)));
    const perStop = sids.map((sid) => (sid ? model.km2ById.get(sid) || 0 : 0));
    const total = line.km2 != null ? line.km2 : perStop.reduce((a, b) => a + b, 0);
    fill(line, sids, perStop, total);
    box.hidden = false;
    animate(sids, perStop, total);
  }

  function close() {
    cancel();
    view.clearStop();
    current = null;
    box.hidden = true;
  }

  box.querySelector(".close-btn:not(.back)").addEventListener("click", () => {
    close();
    onClose();
  });
  $("#rt-replay").addEventListener("click", () => current && open(current));

  /* Stop names: a click keeps the line shown, outlines this walkshed and zooms to it; a second click zooms back. */
  const sheetFrac = () => (isPhone() ? ROUTE_SNAPS.peek : 0);
  const syncPressed = () => $$("#rt-bars .nm[data-sid]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.sid === view.routeStop())));
  $("#rt-bars").addEventListener("click", (e) => {
    const b = e.target.closest(".nm[data-sid]");
    if (!b || !current) return;
    if (view.routeStop() === b.dataset.sid) {
      view.clearStop();
      view.fitLine(current, sheetFrac());
    } else {
      view.highlightStop(b.dataset.sid, sheetFrac());
      onPickStop();
    }
    syncPressed();
  });

  return Object.freeze({ open, close, cancel, isOpen: () => !box.hidden, current: () => current });
}
