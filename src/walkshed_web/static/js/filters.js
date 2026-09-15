/* Operator segmented control and the line list. Renders from state; dispatches actions. */
import { $, $$, chip, esc, fmt } from "./format.js";
import { lineColor } from "./lineColors.js";
import { isSelected } from "./state.js";

const SHORT_OPS = { "Metro İstanbul": "Metro İstanbul", "TCDD Taşımacılık": "TCDD", İETT: "İETT" };

export function renderOperators(operators, store) {
  const host = $("#ops");
  host.innerHTML = "";
  operators.forEach((op) => {
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.op = op;
    b.setAttribute("aria-pressed", "true");
    b.textContent = SHORT_OPS[op] || op;
    b.addEventListener("click", () => store.dispatch({ type: "toggleOp", op }));
    host.appendChild(b);
  });
}

export function renderLines({ lines, stations, operators }, store, { onFocusStation, onZoomLine }) {
  const counts = stations.reduce((acc, s) => {
    s.lines.forEach((c) => {
      acc[c] = (acc[c] || 0) + 1;
    });
    return acc;
  }, {});
  const groups = operators.map((op) => [op, lines.filter((l) => l.operator === op)]);
  const rest = lines.filter((l) => !operators.includes(l.operator));
  if (rest.length && groups.length) groups[0][1].push(...rest);
  const host = $("#lines");
  host.innerHTML = "";
  groups.forEach(([op, ls]) => {
    if (!ls.length) return;
    const h = document.createElement("div");
    h.className = "group";
    h.textContent = op;
    host.appendChild(h);
    ls.forEach((l) => host.append(...lineRow(l, counts, store, onFocusStation, onZoomLine)));
  });
}

function lineRow(l, counts, store, onFocusStation, onZoomLine) {
  const row = document.createElement("div");
  row.className = "linerow";
  const b = document.createElement("button");
  b.className = "line";
  b.type = "button";
  b.dataset.line = l.code;
  b.setAttribute("aria-pressed", "true");
  const stops = Array.isArray(l.stops) ? l.stops : [];
  const n = stops.length || counts[l.code] || 0;
  b.innerHTML = `${chip(l.code)}<span class="name">${esc(l.name)}</span><span class="n">${n}<small>stops</small></span>`;
  b.title = `${l.code} ${l.name} · click toggles, Ctrl-click isolates, double-click zooms`;
  b.addEventListener("click", (ev) => {
    if (ev.altKey || ev.metaKey || ev.ctrlKey) store.dispatch({ type: "isolateLine", code: l.code });
    else store.dispatch({ type: "toggleLine", code: l.code });
  });
  b.addEventListener("dblclick", () => {
    store.dispatch({ type: "isolateLine", code: l.code });
    onZoomLine(l);
  });
  row.appendChild(b);
  if (!stops.length) return [row];
  const exp = document.createElement("button");
  exp.className = "exp";
  exp.type = "button";
  exp.setAttribute("aria-expanded", "false");
  exp.setAttribute("aria-label", `Show the ${stops.length} stops of ${l.code}`);
  exp.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6l5 5 5-5"/></svg>';
  const ul = document.createElement("ul");
  ul.className = "stops";
  ul.hidden = true;
  ul.style.setProperty("--stop-color", lineColor(l.code));
  stops.forEach((st) => {
    const li = document.createElement("li");
    const sb = document.createElement("button");
    sb.className = "stop";
    sb.type = "button";
    sb.textContent = st.name;
    if (st.sid == null) {
      sb.disabled = true;
      sb.title = "No OpenStreetMap node for this stop";
    } else sb.addEventListener("click", () => onFocusStation(st.sid));
    li.appendChild(sb);
    ul.appendChild(li);
  });
  exp.addEventListener("click", () => {
    const open = ul.hidden;
    ul.hidden = !open;
    exp.setAttribute("aria-expanded", String(open));
  });
  row.appendChild(exp);
  return [row, ul];
}

export function syncControls(state, { stations, km2ById }) {
  $$("[data-op]").forEach((b) => b.setAttribute("aria-pressed", String(state.ops.includes(b.dataset.op))));
  $$(".line").forEach((b) => b.setAttribute("aria-pressed", String(state.lines.includes(b.dataset.line))));
  const picked = stations.filter((s) => isSelected(state, s));
  const km2 = picked.reduce((sum, s) => sum + (km2ById.get(String(s.sid)) || 0), 0);
  $("#sel-n").textContent = fmt(picked.length);
  $("#sel-km2").textContent = fmt(km2);
}
