/* Promise wrapper around simWorker.js. Mirrors the Godot SimDirector surface. */
export class SimClient {
  constructor(workerUrl = new URL("./simWorker.js", import.meta.url)) {
    this.worker = new Worker(workerUrl);
    this.nextId = 1;
    this.pending = new Map();
    this.onProgress = () => {};
    this.worker.onmessage = (e) => {
      const msg = e.data || {};
      if (msg.progress) {
        this.onProgress(msg.progress);
        return;
      }
      const entry = this.pending.get(msg.id);
      if (!entry) return;
      this.pending.delete(msg.id);
      if (msg.ok) entry.resolve(msg.result);
      else entry.reject(new Error(msg.error));
    };
  }

  call(fn, ...args) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage({ id, fn, args });
    });
  }

  // Resolve against the page URL: the worker lives in js/sim/, so relative URLs would break.
  init(bundleUrl = "build/sim_bundle.json") { return this.call("init", new URL(bundleUrl, document.baseURI).href); }
  newGame(seed = 19770620, ironman = false) { return this.call("new_game", seed, ironman); }
  setReads(reads) { return this.call("set_reads", reads); }
  step(maxDays = 1) { return this.call("step", maxDays); }
  command(cmd) { return this.call("command", cmd); }
  actions() { return this.call("actions"); }
  history(param, key = null, days = 30) { return this.call("history", param, key, days); }
  explain(param, key = null) { return this.call("explain", param, key); }
  preview(effects) { return this.call("preview", effects); }
  evaluate(reason = "resignation") { return this.call("evaluate", reason); }
  eventDef(id) { return this.call("event_def", id); }
  eventOptions(id) { return this.call("event_options", id); }
  finalEvaluation(reason = "resignation") { return this.call("final_evaluation", reason); }
  save() { return this.call("save"); }
  load(text) { return this.call("load", text); }
  goldenCheck(goldenText) { return this.call("golden_check", goldenText); }
}
