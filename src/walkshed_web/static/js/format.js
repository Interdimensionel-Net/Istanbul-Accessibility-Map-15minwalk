import { lineColor, textOn } from "./lineColors.js";

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "`": "&#96;" };
export const esc = (t) => String(t).replace(/[&<>"'`]/g, (c) => ESC[c]);

export const fmt = (n, d = 0) =>
  Number(n).toLocaleString("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d });

export const chip = (code) =>
  `<span class="code" style="background:${lineColor(code)};color:${textOn(lineColor(code))}">${esc(code)}</span>`;

export const $ = (s) => document.querySelector(s);
export const $$ = (s) => Array.from(document.querySelectorAll(s));

export const phoneMq = window.matchMedia("(max-width: 640px)");
export const isPhone = () => phoneMq.matches;
