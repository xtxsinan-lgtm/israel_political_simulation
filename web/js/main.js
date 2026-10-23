/* Boot: port of game/scenes/boot/BootSplash.gd.
 * 1. boot the Pyodide worker with the reference simulation,
 * 2. load static UI data (game/res/data copies in web/build/ui/),
 * 3. start begin_1977, mount DeskMain, hide the splash.
 * `?e2e=1` runs a scripted smoke test and reports through document.title (tools/web_e2e.py). */
import { SimClient } from "./sim/simClient.js";
import { EventBus } from "./core/EventBus.js";
import { SimEngine } from "./core/SimEngine.js";
import { UIManager } from "./core/UIManager.js";
import { DeskMain } from "./ui/DeskMain.js";

const STATIC_DATA = ["regions", "parameters", "characters", "policies", "actions", "palestine_factions", "causal_edges", "codex_terms", "world_tracks"];

function fitStage() {
  const stage = document.getElementById("stage");
  const s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
  stage.style.transform = `scale(${s})`;
  stage.style.left = `${(window.innerWidth - 1920 * s) / 2}px`;
  stage.style.top = `${(window.innerHeight - 1080 * s) / 2}px`;
}

async function loadStatic() {
  const data = {};
  await Promise.all(STATIC_DATA.map(async (name) => {
    try {
      const res = await fetch(`build/ui/${name}.json`);
      data[name] = res.ok ? await res.json() : {};
    } catch {
      data[name] = {};
    }
  }));
  return data;
}

async function boot() {
  fitStage();
  window.addEventListener("resize", fitStage);
  const logEl = document.getElementById("boot-log");
  const log = (t) => { logEl.textContent += t + "\n"; };
  const sim = new SimClient();
  sim.onProgress = log;
  const bus = new EventBus();
  const engine = new SimEngine(sim, bus);
  const ui = new UIManager(bus, engine);
  ui.inputBlocked = true;
  ui.install();
  try {
    const [data] = await Promise.all([loadStatic(), sim.init("build/sim_bundle.json")]);
    const ctx = { bus, ui, engine, sim, data };
    const desk = new DeskMain(ctx);
    desk.mount();
    log("开局：贝京 1977（begin_1977）…");
    await engine.startNewGame(19770620, false);
    document.getElementById("BootSplash").classList.add("hidden");
    ui.inputBlocked = false;
    window.__desk = { ctx, desk };
    desk.onboarding.maybeStart();
    if (new URLSearchParams(location.search).has("e2e")) {
      const { runE2E } = await import("./e2e.js");
      await runE2E(ctx, desk);
    }
  } catch (err) {
    console.error(err);
    log("启动失败：" + err.message);
    document.title = "E2E_BOOT_ERROR";
  }
}

boot();
