/* One frozen state object. Reducers return a new object; nothing is mutated in place. */

export function initialState(operators, lineCodes) {
  return Object.freeze({
    ops: Object.freeze([...operators]),
    lines: Object.freeze([...lineCodes]),
    focus: null,
  });
}

const without = (list, v) => list.filter((x) => x !== v);
const withItem = (list, v) => (list.includes(v) ? list : [...list, v]);

export function reduce(state, action) {
  switch (action.type) {
    case "toggleLine":
      return Object.freeze({
        ...state,
        focus: null,
        lines: Object.freeze(
          state.lines.includes(action.code) ? without(state.lines, action.code) : withItem(state.lines, action.code)
        ),
      });
    case "isolateLine":
      return Object.freeze({ ...state, focus: null, lines: Object.freeze([action.code]) });
    case "setLines":
      return Object.freeze({ ...state, focus: null, lines: Object.freeze([...action.codes]) });
    case "toggleOp":
      return Object.freeze({
        ...state,
        focus: null,
        ops: Object.freeze(state.ops.includes(action.op) ? without(state.ops, action.op) : withItem(state.ops, action.op)),
      });
    case "focus":
      return Object.freeze({ ...state, focus: action.sid === null ? null : String(action.sid) });
    default:
      return state;
  }
}

export function createStore(state) {
  let current = state;
  const listeners = new Set();
  return Object.freeze({
    get: () => current,
    dispatch(action) {
      const next = reduce(current, action);
      if (next === current) return;
      current = next;
      listeners.forEach((fn) => fn(current));
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  });
}

export const isSelected = (state, station) =>
  state.ops.includes(station.operator) && station.lines.some((c) => state.lines.includes(c));

export const isVisible = (state, station) =>
  station ? (state.focus ? String(station.sid) === state.focus : isSelected(state, station)) : false;
