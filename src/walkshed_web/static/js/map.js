/* Leaflet layers and their styling from theme tokens. Filtering only changes styles; layers are built once. */
import { chip, esc } from "./format.js";
import { lineColor } from "./lineColors.js";
import { KEYS, getJSON, remove, setJSON } from "./storage.js";
import { isSelected, isVisible } from "./state.js";
import { mapTokens } from "./theme.js";

const OSM_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>';
const ESRI_ATTR = 'Tiles &copy; <a href="https://www.esri.com/" target="_blank" rel="noopener">Esri</a> &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community';

export const BASEMAPS = Object.freeze([
  { id: "osm", name: "OpenStreetMap", sub: "Darkened on dark themes", url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", maxZoom: 19, attr: OSM_ATTR, filter: true },
  { id: "satellite", name: "Satellite", sub: "Esri World Imagery", url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", maxZoom: 18, attr: ESRI_ATTR },
  { id: "topo", name: "OpenTopoMap", sub: "Terrain and contours", url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", subdomains: "abc", maxZoom: 17, attr: OSM_ATTR + ", SRTM; style &copy; OpenTopoMap (CC-BY-SA)", filter: true },
]);

const DARK_FILTER = "invert(1) hue-rotate(180deg) grayscale(0.7) brightness(0.75) contrast(0.95) opacity(0.8)";

export function createMap(container, theme) {
  const map = L.map(container, { preferCanvas: true, zoomControl: false, minZoom: 9, maxZoom: 17 });
  map.attributionControl.setPrefix(false);
  map.createPane("land").style.zIndex = 150;
  map.createPane("basemap").style.zIndex = 180;
  map.createPane("bands").style.zIndex = 390;
  L.control.zoom({ position: "bottomright" }).addTo(map);

  let tokens = mapTokens(theme.colors);
  let basePick = BASEMAPS.some((b) => b.id === getJSON(KEYS.BASEMAP)) ? getJSON(KEYS.BASEMAP) : null;
  let tiles = null;
  let tilesId = null;
  let tileErrorShown = false;
  const layers = { land: null, edge: null, band: null, lines: null, stations: null };
  let stationsById = new Map();
  let bands = null;
  const handlers = { onStation: () => {}, onTileError: () => {} };

  const activeBase = () => basePick || "osm";

  function applyBase() {
    const def = BASEMAPS.find((b) => b.id === activeBase());
    if (tiles && tilesId !== def.id) {
      map.removeLayer(tiles);
      tiles = null;
    }
    if (!tiles) {
      tiles = L.tileLayer(def.url, { subdomains: def.subdomains || "abc", maxZoom: def.maxZoom, attribution: def.attr });
      tiles.on("tileerror", () => {
        if (tileErrorShown) return;
        tileErrorShown = true;
        handlers.onTileError();
      });
      tiles.addTo(map);
      tilesId = def.id;
    }
    document.documentElement.style.setProperty("--tile-filter", def.filter && tokens.dark ? DARK_FILTER : "none");
    document.documentElement.dataset.tiles = def.filter && tokens.dark ? "filter" : "none";
  }

  const landStyle = () => ({ color: tokens.landEdge, weight: 1, fillColor: tokens.land, fillOpacity: 1 });
  const bandStyle = () => ({ fillColor: tokens.band, fillOpacity: 1, stroke: false });
  // Borders are drawn first and opaque fills on top in the same faded pane, so interior seams
  // between neighbouring stations disappear and only the outer edge of the merged surface remains.
  const edgeStyle = () => ({ fill: false, color: tokens.bandEdge, weight: 7, opacity: 1, lineJoin: "round" });
  const lineStyle = (code) => ({ color: lineColor(code), weight: 3, opacity: 0.9, interactive: false, lineJoin: "round", lineCap: "round", smoothFactor: 0.8 });

  function build({ land, basemap, bandsGeo, routes, lines, stations }) {
    bands = bandsGeo;
    stationsById = new Map(stations.map((s) => [String(s.sid), s]));
    if (land) layers.land = L.geoJSON(land, { pane: "land", interactive: false, style: landStyle }).addTo(map);
    if (basemap && basemap.layers) {
      basemap.layers.forEach((l) => L.imageOverlay(l.file, l.bounds, { pane: "basemap", interactive: false }).addTo(map));
    }
    layers.edge = L.geoJSON(bands, { pane: "bands", style: edgeStyle, interactive: false }).addTo(map);
    layers.band = L.geoJSON(bands, { pane: "bands", style: bandStyle, interactive: false }).addTo(map);
    if (routes && routes.features && routes.features.length) {
      layers.lines = L.layerGroup(
        routes.features.map((f) => {
          const layer = L.geoJSON(f, { style: () => lineStyle(f.properties.line), interactive: false });
          layer.lineMeta = lines.find((l) => l.code === f.properties.line) || { code: f.properties.line, operator: f.properties.operator };
          return layer;
        })
      ).addTo(map);
    } else {
      layers.lines = L.layerGroup(
        lines.map((l) => {
          const layer = L.polyline((l.coords || []).map(([x, y]) => [y, x]), lineStyle(l.code));
          layer.lineMeta = l;
          return layer;
        })
      ).addTo(map);
    }
    layers.stations = L.layerGroup(
      stations.map((s) => {
        const mk = L.circleMarker([s.lat, s.lon], { radius: 3.5, color: tokens.markerStroke, weight: 1, fillColor: tokens.marker, fillOpacity: 1 });
        mk.bindTooltip(`${s.lines.map(chip).join("")}${esc(s.name)}`, { className: "st", direction: "top", offset: [0, -6] });
        mk.on("click", () => handlers.onStation(s.sid));
        mk.sid = String(s.sid);
        return mk;
      })
    ).addTo(map);
    const bounds = layers.band.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [20, 20] });
    else map.setView([41.01, 28.97], 10);
  }

  function applyFilters(state) {
    if (!layers.band) return;
    const shown = (f) => isVisible(state, stationsById.get(String(f.properties.sid)));
    layers.edge.eachLayer((layer) => layer.setStyle({ ...edgeStyle(), opacity: shown(layer.feature) ? 1 : 0 }));
    layers.band.eachLayer((layer) => layer.setStyle({ ...bandStyle(), fillOpacity: shown(layer.feature) ? 1 : 0 }));
    layers.lines.eachLayer((pl) => {
      const l = pl.lineMeta;
      const on = state.lines.includes(l.code) && state.ops.includes(l.operator);
      pl.setStyle({ opacity: on ? (state.focus ? 0.35 : 0.9) : 0.12 });
    });
    layers.stations.eachLayer((mk) => {
      const s = stationsById.get(mk.sid);
      const on = !state.focus && isSelected(state, s);
      const isFocus = state.focus === mk.sid;
      mk.setStyle({
        radius: isFocus ? 6 : 3.5,
        color: tokens.markerStroke,
        fillColor: isFocus ? tokens.focus : tokens.marker,
        opacity: on || isFocus ? 1 : 0.15,
        fillOpacity: on || isFocus ? 1 : 0.15,
      });
    });
  }

  const fitOpts = (max, phone) =>
    phone ? { paddingTopLeft: [20, 120], paddingBottomRight: [20, 130], maxZoom: max } : { paddingTopLeft: [404, 40], paddingBottomRight: [368, 90], maxZoom: max };

  function fitStation(station, phone) {
    const fs = bands ? bands.features.filter((f) => String(f.properties.sid) === String(station.sid)) : [];
    if (fs.length) map.fitBounds(L.geoJSON({ type: "FeatureCollection", features: fs }).getBounds(), fitOpts(15, phone));
    else map.setView([station.lat, station.lon], 14);
  }

  function fitLine(line, phone) {
    if (!line.coords || !line.coords.length) return;
    map.fitBounds(L.latLngBounds(line.coords.map(([x, y]) => [y, x])), fitOpts(17, phone));
  }

  function setTheme(nextTheme, state) {
    tokens = mapTokens(nextTheme.colors);
    applyBase();
    if (layers.land) layers.land.setStyle(landStyle());
    if (state) applyFilters(state);
    else if (layers.band) {
      layers.edge.setStyle(edgeStyle());
      layers.band.setStyle(bandStyle());
      layers.stations.eachLayer((mk) => mk.setStyle({ color: tokens.markerStroke, fillColor: tokens.marker }));
    }
  }

  function setBase(id) {
    basePick = BASEMAPS.some((b) => b.id === id) ? id : null;
    if (basePick) setJSON(KEYS.BASEMAP, basePick);
    else remove(KEYS.BASEMAP);
    applyBase();
  }

  applyBase();
  return Object.freeze({
    map,
    build,
    applyFilters,
    fitStation,
    fitLine,
    setTheme,
    setBase,
    basePick: () => basePick,
    on: (name, fn) => {
      handlers[name] = fn;
    },
    setAttributionPosition: (pos) => map.attributionControl.setPosition(pos),
  });
}
