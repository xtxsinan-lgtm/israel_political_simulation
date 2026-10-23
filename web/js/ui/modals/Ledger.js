/* Port of game/ui/controllers/LedgerController.gd (+ scenes/modals/LedgerOverlay.tscn).
 *
 * LedgerOverlay: Control (500,120)-(1420,520) on LedgerCodexLayer, toggled by L.
 * One autowrap Label (14px): header "国家总账本  情报估算" + one row "%s  %s" per national
 * fuzzy param (FuzzyBand.LEDGER_FUZZY), sorted by band centre then id. Only the coarse band
 * is kept — raw values are never stored or displayed (D-088).
 * Web intent: paper panel background (Godot draws the bare label over the map).
 */
import { el, rect, label, fmt } from "../../core/controls.js";
import { FuzzyBand, LEDGER_FUZZY } from "../../core/FuzzyBand.js";
import { registerReads } from "../../core/StateView.js";

registerReads(LEDGER_FUZZY.map((p) => [p, ""]));

export class LedgerController {
  constructor(ctx) {
    this.ctx = ctx;
    this.rows = [];
    this.page = 0;
    this.visible = false;
  }

  mount(layer) {
    this.layer = layer;
    this.root = rect(el("div", "ledger-overlay panel"), 500, 120, 1420, 520);
    this.root.id = "LedgerOverlay";
    this.root.style.display = "none";
    this.body = label("", { autowrap: true, cls: "ledger-body" });
    this.root.appendChild(this.body);
    layer.appendChild(this.root);
    this._render();
  }

  setVisible(open, view) {
    this.visible = !!open;
    this.root.style.display = this.visible ? "" : "none";
    if (this.visible) this.refresh(view);
  }

  refresh(view) {
    this.refreshFromSnapshot(view);
  }

  /** refresh_from_snapshot: rows straight from the banded national fuzzy params. */
  refreshFromSnapshot(view) {
    this.rows = [];
    if (!view) { this._render(); return; }
    for (const id of [...LEDGER_FUZZY].sort()) {
      this.rows.push(this._makeRow({ id, param_id: id }, FuzzyBand.bandIndex(view.param(id, ""))));
    }
    this.rows.sort((a, b) => (a.band_centre === b.band_centre ? (a.id < b.id ? -1 : a.id > b.id ? 1 : 0) : a.band_centre - b.band_centre));
    this._render();
  }

  _makeRow(src, band) {
    const row = {};
    for (const [k, v] of Object.entries(src)) {
      if (k === "hidden" || typeof v === "number") continue; // floats are dropped (D-088)
      row[k] = v;
    }
    const paramId = String(src.param_id || "");
    row.fuzzy_sort_band = band;
    row.band_centre = FuzzyBand.bandCentre(band);
    row.band_label = FuzzyBand.bandWord(band, paramId);
    row.band_range = band < 0 ? "" : FuzzyBand.rangeText(band);
    row.display = FuzzyBand.describeBand(band, paramId);
    return row;
  }

  displayHidden(row) {
    if (row.display !== undefined) return String(row.display);
    return FuzzyBand.describeBand(Number(row.fuzzy_sort_band ?? -1), String(row.param_id || ""));
  }

  _render() {
    if (!this.body) return;
    const lines = ["国家总账本  情报估算"];
    for (const row of this.rows) lines.push(fmt("%s  %s", String(row.id || ""), this.displayHidden(row)));
    this.body.textContent = lines.join("\n");
  }
}
