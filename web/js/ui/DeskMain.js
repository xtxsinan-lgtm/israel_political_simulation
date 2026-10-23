/* Port of game/ui/controllers/DeskMainController.gd + DeskMain.tscn composition.
 * Every component follows the same contract:
 *   new Component(ctx)      ctx = {bus, ui, engine, sim, data}
 *   component.mount(layer)  build DOM inside the CanvasLayer div (absolute 1920x1080 coords)
 *   component.refresh(view) re-render from a StateView (optional)
 */
import { TopBarController } from "./TopBar.js";
import { AlertOutlinerController } from "./AlertOutliner.js";
import { DiegeticDeskPropsController } from "./DeskProps.js";
import { DrawerContainerController } from "./DrawerContainer.js";
import { IsraelMapCanvas } from "./map/IsraelMapCanvas.js";
import { RegionInspectorCard } from "./map/RegionInspectorCard.js";
import { CausalTooltipManager } from "./CausalTooltip.js";
import { OnboardingDirector } from "./Onboarding.js";
import { EventModalController } from "./modals/EventModal.js";
import { EndTenureBookController } from "./modals/EndTenureBook.js";
import { LedgerController } from "./modals/Ledger.js";
import { CodexController } from "./modals/Codex.js";

export class DeskMain {
  constructor(ctx) {
    this.ctx = ctx;
    const c = ctx;
    // Same node order as DeskMain.tscn (z order inside each layer).
    this.map = new IsraelMapCanvas(c);
    this.inspector = new RegionInspectorCard(c);
    this.props = new DiegeticDeskPropsController(c);
    this.topBar = new TopBarController(c);
    this.alerts = new AlertOutlinerController(c);
    this.drawers = new DrawerContainerController(c);
    this.ledger = new LedgerController(c);
    this.codex = new CodexController(c);
    this.eventModal = new EventModalController(c);
    this.book = new EndTenureBookController(c);
    this.tooltips = new CausalTooltipManager(c);
    this.onboarding = new OnboardingDirector(c);
  }

  mount() {
    const L = (id) => document.getElementById(id);
    this.map.mount(L("MapDeskLayer"));
    this.inspector.mount(L("MapDeskLayer"));
    this.props.mount(L("MapDeskLayer"));
    this.topBar.mount(L("HUDLayer"));
    this.alerts.mount(L("HUDLayer"));
    this.drawers.mount(L("DrawerLayer"));
    this.ledger.mount(L("LedgerCodexLayer"));
    this.codex.mount(L("LedgerCodexLayer"));
    this.eventModal.mount(L("ModalLayer"));
    this.book.mount(L("ModalLayer"));
    this.tooltips.mount(L("TooltipTutorialLayer"));
    this.onboarding.mount(L("TooltipTutorialLayer"));
    this._connect();
  }

  _connect() {
    const { bus, engine } = this.ctx;
    bus.connect("sim_day_advanced", (view) => this.refreshViews(view));
    bus.connect("snapshot_updated", (view) => this.refreshViews(view));
    bus.connect("pause_state_changed", () => { const v = engine.view(); if (v) this.topBar.refresh(v); });
    bus.connect("event_modal_requested", (ev) => this.eventModal.present(ev, engine.view()));
    bus.connect("end_tenure_triggered", (info) => { this.eventModal.hide(); this.book.show(info, engine.view()); });
    bus.connect("overlay_toggled", (id, open) => {
      if (id === "ledger") this.ledger.setVisible(open, engine.view());
      if (id === "codex") this.codex.setVisible(open);
    });
    bus.connect("drawer_requested", (id) => this.drawers.onDrawerRequested(Number(String(id).slice(1)), engine.view()));
    bus.connect("map_mode_changed", (mode) => this.map.setMapLayer(Number(String(mode).slice(1)), engine.view()));
    bus.connect("region_selected", (regionId) => this.inspector.present(regionId, engine.view()));
  }

  /** DeskMainController.refresh_views: TopBar -> map -> alerts -> open ledger/drawer. */
  refreshViews(view) {
    if (!view) return;
    this.topBar.refresh(view);
    this.map.refresh(view);
    this.alerts.refresh(view);
    this.drawers.refresh(view);
    this.inspector.refresh(view);
    if (this.ctx.ui.ledgerOpen) this.ledger.refresh(view);
  }
}
