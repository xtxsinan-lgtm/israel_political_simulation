/* Tiny helpers that build DOM nodes the way Godot Controls are laid out:
 * absolute rects in the 1920x1080 stage (offset_left/top/right/bottom), Labels, Buttons,
 * Panels, Box containers. Keeps component ports close to the .tscn/.gd originals. */

export function el(tag, cls = "", text = null) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== null && text !== undefined) n.textContent = text;
  return n;
}

/** Position a node with Godot offsets (left, top, right, bottom) in parent-local px. */
export function rect(node, left, top, right, bottom) {
  node.classList.add("ctl");
  node.style.left = `${left}px`;
  node.style.top = `${top}px`;
  if (right !== undefined && right !== null) node.style.width = `${right - left}px`;
  if (bottom !== undefined && bottom !== null) node.style.height = `${bottom - top}px`;
  return node;
}

export function label(text = "", { size = 14, autowrap = false, cls = "" } = {}) {
  const n = el("div", `label${autowrap ? " autowrap" : ""}${cls ? " " + cls : ""}`, text);
  if (size !== 14) n.style.fontSize = `${size}px`;
  return n;
}

export function button(text, onClick, { size = 14, cls = "" } = {}) {
  const n = el("button", `btn${cls ? " " + cls : ""}`, text);
  n.type = "button";
  if (size !== 14) n.style.fontSize = `${size}px`;
  if (onClick) n.addEventListener("click", onClick);
  return n;
}

export function panel(cls = "") { return el("div", `panel${cls ? " " + cls : ""}`); }
export function vbox(cls = "") { return el("div", `vbox${cls ? " " + cls : ""}`); }
export function hbox(cls = "") { return el("div", `hbox${cls ? " " + cls : ""}`); }

/** Godot-style printf for the formats used in the .gd files (%s %d %.Nf %+0.2f %%). */
export function fmt(pattern, ...args) {
  let i = 0;
  return pattern.replace(/%([+0-9.]*)([sdf%])/g, (m, flags, conv) => {
    if (conv === "%") return "%";
    const v = args[i++];
    if (conv === "s") return String(v);
    if (conv === "d") return String(Math.trunc(Number(v)));
    const prec = /\.(\d+)/.exec(flags);
    let s = Number(v).toFixed(prec ? Number(prec[1]) : 6);
    if (flags.includes("+") && Number(v) >= 0) s = "+" + s;
    return s;
  });
}

/** Device-pixel-aware canvas sized to a Godot rect. Returns [canvas, ctx]. */
export function canvas(width, height) {
  const c = el("canvas");
  const dpr = Math.max(1, window.devicePixelRatio || 1) * 1.5;
  c.width = Math.round(width * dpr);
  c.height = Math.round(height * dpr);
  c.style.width = `${width}px`;
  c.style.height = `${height}px`;
  const ctx = c.getContext("2d");
  ctx.scale(dpr, dpr);
  return [c, ctx];
}
