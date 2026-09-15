/* Official line colours from the "Lines In Operation" legend of the Metro İstanbul network map.
   Brand data, not theme colours: they stay fixed across every theme. */

export const LINE_COLORS = Object.freeze({
  M1A: "#e3202b", M1B: "#e3202b", M2: "#009a4e", M3: "#00a7e1", M4: "#e5007e", M5: "#5a2a82",
  M6: "#b39366", M7: "#e78fbb", M8: "#1b3f94", M9: "#f6c800", M11: "#7b3f98",
  B1: "#1d3b7a", B2: "#1d3b7a", T1: "#1e6cb5", T2: "#94b8a5", T3: "#8a4a2b", T4: "#f28c1e",
  T5: "#7c4ea3", T6: "#d7482f", F1: "#8d8358", F2: "#8d8358", F3: "#8d8358", F4: "#8d8358",
  TF1: "#3aa6a0", TF2: "#3aa6a0", 34: "#c9b34a",
});

export const lineColor = (code) => LINE_COLORS[code] || "#888888";

export function textOn(hex) {
  const n = parseInt(hex.slice(1), 16);
  const lum = 0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255);
  return lum > 170 ? "#101820" : "#ffffff";
}
