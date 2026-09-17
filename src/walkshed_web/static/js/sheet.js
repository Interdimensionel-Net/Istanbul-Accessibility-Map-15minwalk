/* Bottom sheet (phone): a grip at the top drags between the peek and full heights, a tap cycles them. */
import { isPhone } from "./format.js";

export const STATION_SNAPS = Object.freeze({ peek: 0.4, full: 0.88 });
export const ROUTE_SNAPS = Object.freeze({ peek: 0.48, full: 0.88 });

export function makeSheet(el, grip, snaps) {
  const names = Object.keys(snaps);
  const heights = () => Object.fromEntries(names.map((n) => [n, window.innerHeight * snaps[n]]));
  const set = (name) => {
    el.dataset.snap = name;
    grip.setAttribute("aria-expanded", String(name === "full"));
  };
  const get = () => el.dataset.snap || names[0];
  let drag = null;
  let justDragged = false;
  grip.addEventListener("pointerdown", (e) => {
    if (!isPhone()) return;
    drag = { y: e.clientY, h: el.getBoundingClientRect().height, moved: false };
    grip.setPointerCapture(e.pointerId);
    el.classList.add("dragging");
  });
  grip.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dy = e.clientY - drag.y;
    if (Math.abs(dy) > 6) drag = { ...drag, moved: true };
    const lim = heights();
    el.style.height = `${Math.min(lim.full, Math.max(lim.peek, drag.h - dy))}px`;
  });
  const endDrag = () => {
    if (!drag) return;
    const h = el.getBoundingClientRect().height;
    const { moved } = drag;
    drag = null;
    el.classList.remove("dragging");
    el.style.height = "";
    if (!moved) return;
    justDragged = true;
    setTimeout(() => { justDragged = false; }, 0);
    const lim = heights();
    set(names.reduce((a, b) => (Math.abs(lim[b] - h) < Math.abs(lim[a] - h) ? b : a)));
  };
  grip.addEventListener("pointerup", endDrag);
  grip.addEventListener("pointercancel", endDrag);
  grip.addEventListener("click", () => { if (!justDragged) set(get() === "full" ? "peek" : "full"); });
  set(names[0]);
  return Object.freeze({ set, get });
}
