/* Scripted end-to-end smoke test, run by main.js when the page has ?e2e=1
 * (tools/web_e2e.py waits for document.title "E2E_PASS" / "E2E_FAIL: <reason>").
 * Assertions on the modals group (EventModal, Ledger, Codex) are strict; assertions on other
 * groups' components are skipped when that component has no DOM yet. */
import { DRAWER_TITLES } from "./core/UIManager.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class E2EFailure extends Error {}

export async function runE2E(ctx, desk) {
  const { ui, engine } = ctx;
  let logEl = document.getElementById("log");
  if (!logEl) {
    logEl = document.createElement("pre");
    logEl.id = "log";
    logEl.hidden = true;
    document.body.appendChild(logEl);
  }
  const t0 = performance.now();
  const log = (line) => {
    const msg = `[${((performance.now() - t0) / 1000).toFixed(1)}s] ${line}`;
    logEl.textContent += msg + "\n";
    console.log("[e2e] " + msg);
  };
  const assert = (cond, reason) => { if (!cond) throw new E2EFailure(reason); };
  const waitFor = async (pred, timeoutMs, what) => {
    const end = performance.now() + timeoutMs;
    while (performance.now() < end) {
      if (pred()) return;
      await sleep(40);
    }
    throw new E2EFailure(`timeout waiting for ${what}`);
  };
  const key = (k, opts = {}) => ui.handleKey(new KeyboardEvent("keydown", { key: k, ...opts }));
  const view = () => engine.view();
  const modal = desk.eventModal;
  const hasDom = (id) => { const n = document.getElementById(id); return !!(n && n.children.length); };
  const enabledOptions = () => [...modal.cards.querySelectorAll("button.event-option")].filter((b) => !b.disabled);
  const idle = () => !engine.busy && !modal.busy;
  let resolved = 0;
  let lastClicked = "";

  async function clickFirstOption() {
    await waitFor(() => !modal.busy, 10000, "modal idle");
    const before = modal.event && modal.event.id;
    const btn = enabledOptions()[0];
    assert(btn, `event ${before} has no enabled option`);
    btn.click();
    await sleep(0);
    await waitFor(() => !modal.busy, 15000, `resolve_event ${before}`);
    const stillPending = view().modules.M12.pending_events.some((e) => e.id === before);
    assert(!stillPending, `event ${before} still pending after clicking ${btn.dataset.option} (${view().clock.date})`);
    resolved += 1;
    if (before !== lastClicked) log(`resolved ${before} (${btn.dataset.option}) on ${view().clock.date}`);
    lastClicked = before;
    return before;
  }

  /** Run the clock, resolving events with the first enabled option, until pred() holds. */
  async function runUntil(pred, timeoutMs, what) {
    const end = performance.now() + timeoutMs;
    engine.setSpeed(5);
    let nextBeat = performance.now() + 5000;
    while (performance.now() < end) {
      if (pred()) return;
      const v = view();
      if (performance.now() > nextBeat) {
        nextBeat += 5000;
        log(`… ${v.clock.date} paused=${engine.paused}(${engine.pauseReason}) busy=${engine.busy} modal=${modal.visible}`);
      }
      if (v.ended) throw new E2EFailure(`game ended (${v.clock.date}) before ${what}`);
      if (modal.visible) {
        await clickFirstOption();
        continue;
      }
      if (engine.paused && idle()) {
        const pending = v.modules.M12.pending_events;
        // After a quick load the engine does not re-emit event_modal_requested.
        if (pending.length) modal.present(pending[0], v);
        else engine.setPaused(false);
      }
      await sleep(30);
    }
    throw new E2EFailure(`timeout: ${what} (at ${view().clock.date})`);
  }

  try {
    log("E2E start");
    // 1. TopBar initial text (TopBar group: skipped if no DOM).
    if (hasDom("HUDLayer")) {
      const txt = document.getElementById("HUDLayer").textContent;
      assert(txt.includes("1977-06-20  第0天  暂停"), `TopBar initial text missing date/pace: ${txt.slice(0, 80)}`);
      log("TopBar initial text OK");
    } else log("TopBar has no DOM yet: skipped");
    assert(view().clock.date === "1977-06-20" && engine.paused, "initial state is not 1977-06-20 paused");

    // 2. Unpause at speed 5 until the first event auto-pause.
    key("5"); // speed_5 also unpauses (UIManager.handle_action)
    assert(!engine.paused && engine.speedLevel === 5, "speed_5 did not unpause at speed 5");
    log("speed 5, running…");
    await waitFor(() => {
      if (modal.visible) return true;
      const v = view();
      if (v.ended) throw new E2EFailure("game ended before first event");
      if (engine.paused && idle() && !v.modules.M12.pending_events.length) engine.setPaused(false); // alert/vote pause
      return false;
    }, 120000, "first event modal");
    assert(engine.paused, "engine not paused while event modal is shown");
    const first = modal.event;
    const optCount = modal.cards.querySelectorAll("button.event-option").length;
    assert(optCount > 0, "event modal has no option buttons");
    assert(modal.titleLabel.textContent.includes(String(first.title || first.id)), "event modal title lacks event title");
    assert(modal.titleLabel.querySelector(".ink-stamp"), "event modal stamp missing");
    assert(modal.body.textContent.length > 0 && modal.body.textContent !== "大转折正在发生。", "event modal shows the default body instead of event text");
    log(`event ${first.id} 「${first.title}」 on ${view().clock.date}: ${optCount} options`);

    // Hover preview (OptionPreviewCard) on the first option.
    const firstBtn = enabledOptions()[0];
    firstBtn.dispatchEvent(new MouseEvent("mouseenter"));
    await waitFor(() => modal.preview.style.display !== "none" && !modal.preview.textContent.includes("推演中"), 15000, "option preview");
    assert(/L1 直接代价[\s\S]*L2 下游区间[\s\S]*L3 阈值预警/.test(modal.preview.textContent), "option preview lacks L1/L2/L3");
    log("option preview: " + modal.preview.textContent.replace(/\s+/g, " ").slice(0, 120));
    firstBtn.dispatchEvent(new MouseEvent("mouseleave"));

    // 3. Click the first option -> modal hides or advances; game stays paused.
    const clickedId = await clickFirstOption();
    assert(!modal.visible || (modal.event && modal.event.id !== clickedId), "event modal neither hid nor advanced");
    assert(engine.paused, "game unpaused after resolving an event");
    assert(!view().modules.M12.pending_events.some((e) => e.id === clickedId), `event ${clickedId} still pending`);
    log(`resolved ${clickedId}; modal ${modal.visible ? "advanced to " + modal.event.id : "hidden"}`);
    while (modal.visible) await clickFirstOption();

    // 4. Ledger (L): fuzzy words only, never exact numbers.
    key("l");
    assert(ui.ledgerOpen && desk.ledger.visible, "ledger did not open on L");
    const ledgerText = desk.ledger.body.textContent;
    assert(ledgerText.startsWith("国家总账本  情报估算"), "ledger header wrong");
    assert(ledgerText.split("\n").length === 8, `ledger expected 7 rows, got: ${ledgerText}`);
    assert(!/\d+\.\d+/.test(ledgerText), `ledger shows decimal numbers: ${ledgerText}`);
    assert(desk.ledger.root.style.display !== "none", "ledger DOM hidden");
    log("ledger OK: " + ledgerText.split("\n").slice(1, 3).join(" | "));
    key("l");
    assert(!ui.ledgerOpen && desk.ledger.root.style.display === "none", "ledger did not close on L");

    // 5. Codex (C): sentence with links; clicking a link shows the entry.
    key("c");
    assert(ui.codexOpen && desk.codex.root.style.display !== "none", "codex did not open on C");
    const links = desk.codex.body.querySelectorAll("a.codex-link");
    assert(desk.codex.body.textContent === "大转折之后，议会席位按巴德尔-奥弗法分配。", "codex sentence wrong");
    assert(links.length === 2, `codex expected 2 links, got ${links.length}`);
    links[1].click();
    assert(desk.codex.entry.style.display !== "none" && desk.codex.entryTitle.textContent.includes("巴德尔-奥弗法"), "codex link did not open its entry");
    log("codex OK: " + desk.codex.entryDef.textContent.slice(0, 30));
    key("c");
    assert(!ui.codexOpen && desk.codex.root.style.display === "none", "codex did not close on C");

    // 6. Drawers 1-7 via Ctrl+n (DrawerContainer group: DOM check skipped if no DOM).
    for (let n = 1; n <= 7; n++) {
      key(String(n), { ctrlKey: true });
      assert(ui.drawerIndex === n, `Ctrl+${n} did not open drawer ${n}`);
      await sleep(30);
      if (hasDom("DrawerLayer") && !document.getElementById("DrawerLayer").textContent.includes(DRAWER_TITLES[n])) {
        log(`warn: DrawerLayer DOM lacks title ${DRAWER_TITLES[n]}`);
      }
    }
    key("7", { ctrlKey: true });
    assert(ui.drawerIndex === 0, "Ctrl+7 again did not close the drawer");
    log("drawers 1-7 OK");

    // 7. Map layers F3/F4.
    key("F3");
    assert(ui.mapLayer === 3, "F3 did not switch map layer");
    key("F4");
    assert(ui.mapLayer === 4, "F4 did not switch map layer");
    key("F1");
    log("map layers F3/F4 OK");

    // 8. Quick save / quick load: same date and state hash.
    engine.setPaused(true);
    await waitFor(idle, 10000, "engine idle before save");
    const savedDate = view().clock.date;
    const savedHash = engine.snapshot.state_hash;
    await engine.quickSave();
    log(`quick saved ${savedDate} ${String(savedHash).slice(0, 12)}`);
    const loadRes = await engine.quickLoad();
    assert(loadRes && loadRes.ok !== false, `quick load failed: ${loadRes && loadRes.error}`);
    assert(view().clock.date === savedDate, `quick load date ${view().clock.date} != ${savedDate}`);
    assert(engine.snapshot.state_hash === savedHash, "quick load state_hash differs");
    assert(engine.paused && engine.pauseReason === "loaded", "quick load did not leave the engine paused (loaded)");
    log("quick load OK (same date + state_hash)");

    // 9. Run to 1978-01-01 resolving events with the first enabled option.
    await runUntil(() => view().clock.date >= "1978-01-01", 180000, "reach 1978-01-01");
    engine.setPaused(true);
    await waitFor(idle, 10000, "engine idle at end");
    log(`reached ${view().clock.date}, events resolved: ${resolved}`);
    document.title = "E2E_PASS";
    log("E2E_PASS");
  } catch (err) {
    const reason = err instanceof E2EFailure ? err.message : `exception: ${err && err.stack ? err.stack : err}`;
    log("FAIL " + reason);
    console.error("[e2e] FAIL", reason);
    try { engine.setPaused(true); } catch { /* ignore */ }
    document.title = `E2E_FAIL: ${reason}`.slice(0, 300);
  }
}
