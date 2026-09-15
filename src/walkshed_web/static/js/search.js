/* Station search combobox against /api/search, debounced, with one in-flight request at a time. */
import { ApiError, getJson } from "./api.js";
import { $, chip, esc } from "./format.js";
import { showError } from "./toast.js";

const DEBOUNCE_MS = 120;

export function createSearch({ onPick, onFocus }) {
  const input = $("#search");
  const list = $("#hits");
  let hits = [];
  let active = -1;
  let timer = null;
  let controller = null;

  function render() {
    list.innerHTML = hits
      .map((s, i) => `<li role="option" id="hit-${i}" aria-selected="${i === active}" data-sid="${esc(s.sid)}">${s.lines.map(chip).join("")}<span class="nm">${esc(s.name)}</span></li>`)
      .join("");
    list.hidden = !hits.length;
    input.setAttribute("aria-expanded", String(Boolean(hits.length)));
    input.setAttribute("aria-activedescendant", active >= 0 ? `hit-${active}` : "");
  }

  function close() {
    clearTimeout(timer);
    if (controller) controller.abort();
    hits = [];
    active = -1;
    render();
  }

  async function query(text) {
    if (controller) controller.abort();
    if (!text) {
      close();
      return;
    }
    controller = new AbortController();
    try {
      const { data } = await getJson(`/api/search?q=${encodeURIComponent(text)}&limit=7`, { signal: controller.signal });
      hits = data;
      active = hits.length ? 0 : -1;
      render();
    } catch (e) {
      if (e.name === "AbortError") return;
      if (e instanceof ApiError && e.status === 429) showError(e.message);
      close();
    }
  }

  function pick(sid) {
    const s = hits.find((h) => String(h.sid) === String(sid));
    close();
    if (!s) return;
    input.value = s.name;
    input.blur();
    onPick(s.sid);
  }

  input.addEventListener("input", () => {
    clearTimeout(timer);
    const text = input.value.trim().slice(0, 80);
    timer = setTimeout(() => query(text), DEBOUNCE_MS);
  });
  input.addEventListener("focus", () => onFocus && onFocus());
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!hits.length) return;
      e.preventDefault();
      active = (active + (e.key === "ArrowDown" ? 1 : hits.length - 1)) % hits.length;
      render();
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (hits[active]) pick(hits[active].sid);
    } else if (e.key === "Escape") {
      close();
      input.blur();
    }
  });
  input.addEventListener("blur", close);
  list.addEventListener("mousedown", (e) => {
    const li = e.target.closest("li");
    if (li) {
      e.preventDefault();
      pick(li.dataset.sid);
    }
  });

  return Object.freeze({
    focus: () => {
      input.focus();
      input.select();
    },
    close,
  });
}
