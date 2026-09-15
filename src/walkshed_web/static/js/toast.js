/* One shared #toast, per the Odysseus guide (§5.1). */

const el = () => document.getElementById("toast");
let timer = null;

export function showToast(message, msOrOpts = 1500) {
  const t = el();
  if (!t) return;
  const opts = typeof msOrOpts === "number" ? { duration: msOrOpts } : msOrOpts || {};
  clearTimeout(timer);
  t.textContent = "";
  t.className = "toast";
  const text = document.createElement("span");
  text.textContent = message;
  t.appendChild(text);
  if (opts.action && typeof opts.onAction === "function") {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "undo";
    b.textContent = opts.action;
    b.addEventListener("click", () => {
      hide();
      opts.onAction();
    });
    t.appendChild(b);
    t.classList.add("has-action");
  }
  if (opts.error) t.classList.add("error");
  requestAnimationFrame(() => t.classList.add("show"));
  timer = setTimeout(hide, opts.duration || (opts.action ? 5000 : 1500));
}

export function showError(message) {
  showToast(message, { duration: 3000, error: true });
}

function hide() {
  const t = el();
  if (t) t.classList.remove("show", "has-action");
}
