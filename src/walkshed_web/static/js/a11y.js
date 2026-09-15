/* Retrofit for click-only elements, per the Odysseus guide (§5.5). */

export function retrofit(node) {
  if (node.tabIndex < 0) node.tabIndex = 0;
  if (!node.getAttribute("role") && !node.querySelector("button, a, input")) node.setAttribute("role", "button");
  node.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      node.click();
    }
  });
  return node;
}

/* Layered Escape: the most recently opened surface closes first. */
export function createEscStack() {
  const stack = [];
  return Object.freeze({
    push: (close) => {
      stack.push(close);
      return () => {
        const i = stack.indexOf(close);
        if (i >= 0) stack.splice(i, 1);
      };
    },
    pop: () => {
      const close = stack.pop();
      if (close) close();
      return Boolean(close);
    },
    size: () => stack.length,
  });
}
