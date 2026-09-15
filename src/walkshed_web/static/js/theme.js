/* Theme contract: five core colours on :root. Presets from the Odysseus guide, §2.2. */
import { KEYS, getJSON, setJSON } from "./storage.js";

export const DEFAULT_THEME = "midnight";

const preset = (bg, fg, panel, border, red) => Object.freeze({ bg, fg, panel, border, red });

export const THEMES = Object.freeze({
  dark: preset("#282c34", "#9cdef2", "#111111", "#355a66", "#e06c75"),
  light: preset("#f0ebe3", "#5a5248", "#faf6f0", "#d4cdc2", "#c47d5a"),
  midnight: preset("#0d1117", "#c9d1d9", "#161b22", "#30363d", "#f85149"),
  paper: preset("#faf8f5", "#3b3836", "#ffffff", "#d5d0c8", "#c5ac4a"),
  cyberpunk: preset("#0a0a0f", "#0ff0fc", "#12101a", "#9b30ff", "#e040fb"),
  retrowave: preset("#1a1a2e", "#e94560", "#16213e", "#533483", "#e94560"),
  forest: preset("#1b2a1b", "#a8d5a2", "#142414", "#3d6b3d", "#7cb871"),
  ocean: preset("#0b1a2c", "#64d2ff", "#091422", "#1e5074", "#4facfe"),
  ume: preset("#2b1b2e", "#f5c2e7", "#1e1420", "#6c4675", "#f5a0c0"),
  copper: preset("#1c1410", "#e8c39e", "#140f0a", "#7a5533", "#d4764e"),
  terminal: preset("#000000", "#00ff41", "#0a0a0a", "#003b00", "#00ff41"),
  organs: preset("#0a0406", "#efe1c8", "#15080a", "#3a1519", "#c83240"),
  lavender: preset("#f3eef8", "#3d3551", "#faf7ff", "#cec3de", "#9b6dcc"),
  gpt: preset("#212121", "#ececec", "#171717", "#424242", "#949494"),
  claude: preset("#262624", "#f5f4f0", "#30302e", "#4a4a47", "#c6613f"),
  cute: preset("#fff0f5", "#d4608a", "#fff8fa", "#f0c0d0", "#ff6b9d"),
});

const CORE = ["bg", "fg", "panel", "border", "red"];
const HEX = /^#[0-9a-f]{6}$/i;

const hexToRgb = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
const rgbToHex = (rgb) => "#" + rgb.map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0")).join("");

/* mix(a, b, t): t = 0 gives a, t = 1 gives b. Canvas layers need real hex, not color-mix(). */
export function mix(a, b, t) {
  const [r1, g1, b1] = hexToRgb(a);
  const [r2, g2, b2] = hexToRgb(b);
  return rgbToHex([r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t]);
}

export function isDark(colors) {
  const [r, g, b] = hexToRgb(colors.bg);
  return 0.299 * r + 0.587 * g + 0.114 * b < 128;
}

/* Colours that Leaflet draws on canvas, derived from the five core values. */
export function mapTokens(colors) {
  const dark = isDark(colors);
  return Object.freeze({
    dark,
    land: mix(colors.bg, colors.fg, 0.08),
    landEdge: mix(colors.bg, colors.fg, 0.2),
    band: dark ? mix(colors.red, colors.bg, 0.35) : mix(colors.red, colors.bg, 0.3),
    bandEdge: dark ? colors.red : mix(colors.red, colors.fg, 0.35),
    focus: colors.red,
    marker: colors.fg,
    markerStroke: colors.bg,
  });
}

export function currentTheme() {
  const saved = getJSON(KEYS.THEME);
  if (saved && saved.colors && CORE.every((k) => HEX.test(saved.colors[k] || ""))) return saved;
  return { name: DEFAULT_THEME, colors: THEMES[DEFAULT_THEME] };
}

export function applyColors(theme) {
  const root = document.documentElement;
  CORE.forEach((k) => root.style.setProperty(`--${k}`, theme.colors[k]));
  root.dataset.theme = theme.name;
  root.dataset.dark = String(isDark(theme.colors));
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = theme.colors.bg;
}

export function setTheme(name) {
  if (!THEMES[name]) return currentTheme();
  const theme = { name, colors: THEMES[name] };
  applyColors(theme);
  setJSON(KEYS.THEME, theme);
  return theme;
}
