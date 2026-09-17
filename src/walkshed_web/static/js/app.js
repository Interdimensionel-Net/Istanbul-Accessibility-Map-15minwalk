/* Boot: load data, wire modules, first render. Loads last and coordinates everything. */
import { getAll, getGeo, getJson } from "./api.js";
import { createEscStack, retrofit } from "./a11y.js";
import { createDetail } from "./detail.js";
import { renderLines, renderOperators, syncControls } from "./filters.js";
import { $, $$, fmt, isPhone, phoneMq } from "./format.js";
import { BASEMAPS, createMap } from "./map.js";
import { createRoute } from "./route.js";
import { createSearch } from "./search.js";
import { ROUTE_SNAPS, STATION_SNAPS, makeSheet } from "./sheet.js";
import { createStore, initialState } from "./state.js";
import { THEMES, applyColors, currentTheme, setTheme } from "./theme.js";
import { showError, showToast } from "./toast.js";

const OPERATOR_ORDER = ["Metro İstanbul", "TCDD Taşımacılık", "İETT"];
const CHECK = '<svg class="ck" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m3 8.5 3.2 3.2L13 4.5"/></svg>';

let theme = currentTheme();
applyColors(theme);
const esc = createEscStack();
const view = createMap("map", theme);
const model = { meta: null, lines: [], stations: [], operators: [], km2ById: new Map() };
let store = null;

/* Popovers in the top bar: one open at a time. */
const POPS = [
  { box: $("#basemap"), btn: $("#base-btn") },
  { box: $("#themes"), btn: $("#theme-btn") },
];
let popRelease = null;
function setPop(open) {
  if (isPhone()) return; // the popover contents sit in the drawer, always shown
  POPS.forEach((p) => {
    const on = p === open;
    p.box.hidden = !on;
    p.btn.setAttribute("aria-expanded", String(on));
  });
  if (popRelease) popRelease();
  popRelease = open ? esc.push(() => setPop(null)) : null;
}
POPS.forEach((p) => p.btn.addEventListener("click", () => setPop(p.box.hidden ? p : null)));
document.addEventListener("mousedown", (e) => {
  if (isPhone()) return;
  const open = POPS.find((p) => !p.box.hidden);
  if (open && !open.box.contains(e.target) && !open.btn.contains(e.target)) setPop(null);
});

/* Basemap list */
function renderBasemaps() {
  const host = $("#base-list");
  host.innerHTML = [{ id: "", name: "Auto", sub: "OpenStreetMap, darkened on dark themes" }, ...BASEMAPS]
    .map((b) => `<button type="button" class="radio-row" role="radio" data-base="${b.id}" aria-checked="${String(b.id === (view.basePick() || ""))}"><span class="sw sw-${b.id || "auto"}" aria-hidden="true"></span><span>${b.name}${b.sub ? `<small>${b.sub}</small>` : ""}</span>${CHECK}</button>`)
    .join("");
}
$("#base-list").addEventListener("click", (e) => {
  const b = e.target.closest("[data-base]");
  if (!b) return;
  view.setBase(b.dataset.base || null);
  renderBasemaps();
});

/* Theme grid: the 16 presets */
function renderThemes() {
  const host = $("#theme-grid");
  host.innerHTML = Object.entries(THEMES)
    .map(([name, c]) => `<button type="button" class="radio-row" role="radio" data-theme="${name}" aria-checked="${String(name === theme.name)}"><span class="sw sw-theme" aria-hidden="true"><i style="background:${c.bg}"></i><i style="background:${c.red}"></i><i style="background:${c.panel}"></i><i style="background:${c.fg}"></i></span><span>${name}</span>${CHECK}</button>`)
    .join("");
}
$("#theme-grid").addEventListener("click", (e) => {
  const b = e.target.closest("[data-theme]");
  if (!b) return;
  theme = setTheme(b.dataset.theme);
  view.setTheme(theme, store && store.get());
  renderThemes();
  renderBasemaps();
});

/* About modal */
const about = $("#about-modal");
let aboutRelease = null;
function openAbout() {
  about.classList.remove("hidden");
  $("#about-btn").setAttribute("aria-expanded", "true");
  aboutRelease = esc.push(closeAbout);
  about.querySelector(".close-btn").focus();
}
function closeAbout() {
  about.classList.add("hidden");
  $("#about-btn").setAttribute("aria-expanded", "false");
  if (aboutRelease) aboutRelease();
  aboutRelease = null;
}
$("#about-btn").addEventListener("click", () => (about.classList.contains("hidden") ? openAbout() : closeAbout()));
about.querySelector(".close-btn").addEventListener("click", closeAbout);
about.addEventListener("mousedown", (e) => {
  if (e.target === about) closeAbout();
});

/* Station detail */
let detailRelease = null;
const detail = createDetail({
  onClose: () => {
    store.dispatch({ type: "focus", sid: null });
    if (detailRelease) detailRelease();
    detailRelease = null;
  },
});
async function focusStation(sid) {
  const s = await detail.open(sid);
  if (!s) return;
  if (route.isOpen()) closeRoute();
  store.dispatch({ type: "focus", sid: s.sid });
  if (!detailRelease) detailRelease = esc.push(closeStation);
  closeDrawer();
  stationSheet.set("peek");
  view.fitStation(s, isPhone() ? STATION_SNAPS.peek : 0);
}
function closeStation() {
  detail.close();
  store.dispatch({ type: "focus", sid: null });
  if (detailRelease) detailRelease();
  detailRelease = null;
}
view.on("onStation", focusStation);
view.on("onTileError", () => showToast("Map tiles are blocked here. The built-in sheet is shown instead.", 4000));

/* Route panel */
let routeRelease = null;
const route = createRoute({
  view,
  model,
  onClose: () => {
    if (routeRelease) routeRelease();
    routeRelease = null;
    if (store) view.applyFilters(store.get());
  },
});
function openRoute(line) {
  if (detail.isOpen()) closeStation();
  store.dispatch({ type: "isolateLine", code: line.code });
  view.fitLine(line, isPhone() ? ROUTE_SNAPS.peek : 0);
  setPop(null);
  closeDrawer();
  routeSheet.set("peek");
  route.open(line);
  if (!routeRelease) routeRelease = esc.push(closeRoute);
}
function closeRoute() {
  route.close();
  if (routeRelease) routeRelease();
  routeRelease = null;
  if (store) view.applyFilters(store.get());
}

/* Search */
const search = createSearch({ onPick: focusStation, onFocus: () => setPop(null) });

/* Bottom sheets on phones */
const stationSheet = makeSheet($("#station"), $("#st-grip"), STATION_SNAPS);
const routeSheet = makeSheet($("#route"), $("#rt-grip"), ROUTE_SNAPS);

/* Drawer (phone): the sidebar slides in from the left over a scrim */
const drawer = $("#panel");
const scrim = $("#scrim");
const menuBtn = $("#menu-btn");
const pill = $("#pill");
let drawerRelease = null;
const isDrawerOpen = () => drawer.dataset.open === "true";
const behindDrawer = () => [$("#map"), $("#bar"), $("#stats"), pill, $("#station"), $("#route")];
function openDrawer() {
  if (!isPhone() || isDrawerOpen()) return;
  drawer.dataset.open = "true";
  drawer.setAttribute("role", "dialog");
  drawer.setAttribute("aria-modal", "true");
  scrim.hidden = false;
  behindDrawer().forEach((el) => { el.inert = true; });
  [menuBtn, pill].forEach((el) => el.setAttribute("aria-expanded", "true"));
  drawerRelease = esc.push(closeDrawer);
  $("#drawer-close").focus();
}
function closeDrawer() {
  if (!isDrawerOpen()) return;
  delete drawer.dataset.open;
  drawer.removeAttribute("role");
  drawer.removeAttribute("aria-modal");
  scrim.hidden = true;
  behindDrawer().forEach((el) => { el.inert = false; });
  [menuBtn, pill].forEach((el) => el.setAttribute("aria-expanded", "false"));
  if (drawerRelease) drawerRelease();
  drawerRelease = null;
  if (drawer.contains(document.activeElement)) menuBtn.focus();
}
menuBtn.addEventListener("click", openDrawer);
pill.addEventListener("click", openDrawer);
scrim.addEventListener("click", closeDrawer);
$("#drawer-close").addEventListener("click", closeDrawer);
$("#drawer-about").addEventListener("click", openAbout);
$("#st-back").addEventListener("click", () => { closeStation(); openDrawer(); });
$("#rt-back").addEventListener("click", () => { closeRoute(); openDrawer(); });

/* On phones the basemap and theme lists live in the drawer footer, always shown */
function placeChrome() {
  const boxes = POPS.map((p) => p.box);
  if (isPhone()) {
    POPS.forEach((p) => p.btn.setAttribute("aria-expanded", "false"));
    $("#drawer-foot").prepend(...boxes);
    boxes.forEach((box) => { box.hidden = false; });
  } else {
    closeDrawer();
    $("#bar").append(...boxes);
    boxes.forEach((box) => { box.hidden = true; });
  }
}
placeChrome();

/* Keyboard */
document.addEventListener("keydown", (e) => {
  const typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement?.tagName ?? "");
  if (e.key === "/" && !typing) {
    e.preventDefault();
    search.focus();
  } else if (e.key === "Escape" && !typing) {
    esc.pop();
  }
});

const placeAttribution = () => view.setAttributionPosition(isPhone() ? "topright" : "bottomright");
placeAttribution();
phoneMq.addEventListener?.("change", () => { placeAttribution(); placeChrome(); });

/* Boot */
async function boot() {
  const { data: meta } = await getJson("/api/meta");
  const v = meta.reference_hash ? `?v=${encodeURIComponent(meta.reference_hash)}` : "";
  const [linesRes, stations, bandsGeo, land, routes] = await Promise.all([
    getJson("/api/lines?include_stops=true&include_coords=true"),
    getAll("/api/stations"),
    getGeo(`/data/bands.geojson${v}`),
    getGeo(`/data/provinces.geojson${v}`, { optional: true }),
    getGeo(`/data/routes.geojson${v}`, { optional: true }),
  ]);
  model.meta = meta;
  model.lines = linesRes.data;
  model.stations = stations;
  model.operators = [...OPERATOR_ORDER.filter((o) => meta.operators.includes(o)), ...meta.operators.filter((o) => !OPERATOR_ORDER.includes(o))];
  model.km2ById = bandsGeo.features.reduce((m, f) => {
    const sid = String(f.properties.sid);
    return m.set(sid, Math.max(m.get(sid) || 0, f.properties.km2 || 0));
  }, new Map());
  store = createStore(initialState(model.operators, model.lines.map((l) => l.code)));

  view.build({ land, basemap: meta.basemap, bandsGeo, routes, lines: model.lines, stations });
  renderOperators(model.operators, store);
  renderLines(model, store, { onFocusStation: focusStation, onZoomLine: openRoute });
  renderBasemaps();
  renderThemes();
  $$("#lines .linerow").forEach(retrofit);

  store.subscribe((state) => {
    route.cancel();
    view.applyFilters(state);
    syncControls(state, model);
  });
  view.applyFilters(store.get());
  syncControls(store.get(), model);
  $("#all").addEventListener("click", () => store.dispatch({ type: "setLines", codes: model.lines.map((l) => l.code) }));
  $("#none").addEventListener("click", () => store.dispatch({ type: "setLines", codes: [] }));

  const widest = Math.max(...meta.bands) / 60;
  $("#k-stations").textContent = fmt(meta.counts.covered);
  $("#p-stations").textContent = fmt(meta.counts.covered);
  $("#k-km2").textContent = fmt(meta.total_km2);
  $("#p-km2").textContent = fmt(meta.total_km2);
  $("#about-speed").textContent = meta.walk_speed_kmh;
  $("#about-min").textContent = widest;
  $("#about-when").textContent = meta.generated_at ? new Date(meta.generated_at).toLocaleDateString("en-GB", { year: "numeric", month: "long", day: "numeric" }) : "unknown";
  $("#loading").hidden = true;
  document.body.classList.add("ready");
  openFromHash();
}

/* Deep links: #menu opens the drawer, #station/<sid> focuses a station, #route/<code> plays a line */
function openFromHash() {
  const [key, value] = decodeURIComponent(location.hash.slice(1)).split("/");
  if (key === "menu") openDrawer();
  else if (key === "station" && model.stations.some((s) => String(s.sid) === value)) focusStation(value);
  else if (key === "route" && value) {
    const line = model.lines.find((l) => l.code === value);
    if (line) openRoute(line);
  }
}
window.addEventListener("hashchange", () => { if (model.meta) openFromHash(); });

boot().catch((e) => {
  $("#loading .s").textContent = "The map data did not load. Reload the page.";
  $("#loading .p").hidden = true;
  showError(e.message || "Load failed.");
});
