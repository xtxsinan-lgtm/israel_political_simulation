/* Port of game/ui/controllers/drawers/D2_KnessetController.gd: semicircle seat chart drawn on a
 * 920x420 canvas (120 dots max, t=i/(n-1), angle=PI(1-t), r=160+(i%4)*18, centre (460,280),
 * dot r4, baseline (80,300)-(840,300) #B8292E 2px).
 * Intent fix: dots are coloured per coalition (#B8292E) vs opposition (#0038B8) from
 * state.parliament.government.members/support (coalition parties first, then opposition,
 * each sorted by seats desc), plus a party legend. Falls back to Godot's i<61 rule. */
import { canvas, label, fmt } from "../../core/controls.js";

const RED = "#B8292E";
const BLUE = "#0038B8";

function roundHalfUp(v) { return Math.floor(Number(v) + 0.5); }

export class D2KnessetController {
  constructor(ctx) {
    this.ctx = ctx;
    this.partySeats = {};
    this.coalitionLoyalty = {};
    this.partyPolls = {};
    this.seatDots = 0;
    this.dotColors = [];
  }

  mount(parent) {
    this.root = document.createElement("div");
    this.root.className = "drawer-body d2-knesset";
    [this.canvas, this.g] = canvas(920, 420);
    this.canvas.classList.add("d2-seat-chart");
    this.legend = document.createElement("div");
    this.legend.className = "d2-legend";
    this.root.append(this.canvas, this.legend);
    parent.appendChild(this.root);
  }

  refresh(view) {
    this.partySeats = {};
    this.coalitionLoyalty = {};
    this.partyPolls = {};
    const seats = view.modules.M03.knesset_seats || view.parliament.knesset_seats || {};
    const ids = Object.keys(seats).sort();
    this.seatDots = 0;
    for (const id of ids) {
      const count = roundHalfUp(seats[id]);
      this.partySeats[id] = count;
      this.partyPolls[id] = count;
      this.seatDots += count;
      this.coalitionLoyalty[id] = view.params.get_val("ally_satisfaction", id);
    }
    if (this.seatDots <= 0) this.seatDots = 120;

    const gov = (view.raw.parliament && view.raw.parliament.government) || null;
    const coalitionSet = new Set(gov ? [...(gov.members || []), ...(gov.support || [])] : []);
    this.hasGov = coalitionSet.size > 0;
    const bySeats = (a, b) => (this.partySeats[b] - this.partySeats[a]) || (a < b ? -1 : 1);
    const parties = ids.filter((id) => this.partySeats[id] > 0);
    this.coalition = parties.filter((id) => coalitionSet.has(id)).sort(bySeats);
    this.opposition = parties.filter((id) => !coalitionSet.has(id)).sort(bySeats);
    this.dotColors = [];
    if (this.hasGov) {
      for (const id of this.coalition) for (let k = 0; k < this.partySeats[id]; k++) this.dotColors.push(RED);
      for (const id of this.opposition) for (let k = 0; k < this.partySeats[id]; k++) this.dotColors.push(BLUE);
    }
    this.draw();
    this.renderLegend();
  }

  seatTotal() { return this.seatDots; }

  draw() {
    const g = this.g;
    g.clearRect(0, 0, 920, 420);
    const total = Math.max(this.seatDots, 1);
    const shown = Math.min(total, 120);
    for (let i = 0; i < shown; i++) {
      const t = i / Math.max(shown - 1, 1);
      const angle = Math.PI * (1.0 - t);
      const radius = 160.0 + (i % 4) * 18.0;
      const x = 460 + Math.cos(angle) * radius;
      const y = 280 - Math.sin(angle) * radius;
      g.fillStyle = this.hasGov ? (this.dotColors[i] || BLUE) : (i < 61 ? RED : BLUE);
      g.beginPath();
      g.arc(x, y, 4.0, 0, Math.PI * 2);
      g.fill();
    }
    g.strokeStyle = RED;
    g.lineWidth = 2.0;
    g.beginPath();
    g.moveTo(80, 300);
    g.lineTo(840, 300);
    g.stroke();
  }

  renderLegend() {
    this.legend.replaceChildren();
    if (!this.hasGov) return;
    const row = (color, title, list) => {
      const sum = list.reduce((s, id) => s + this.partySeats[id], 0);
      const line = document.createElement("div");
      line.className = "d2-legend-row";
      const sw = document.createElement("span");
      sw.className = "d2-swatch";
      sw.style.background = color;
      line.append(sw, label(fmt("%s %d 席：", title, sum), { size: 14, cls: "d2-legend-title" }),
        label(list.map((id) => `${id} ${this.partySeats[id]}`).join(" · "), { size: 14, autowrap: true }));
      this.legend.appendChild(line);
    };
    row(RED, "执政联盟", this.coalition);
    row(BLUE, "反对派", this.opposition);
  }
}
