/* Web Worker hosting the reference Python simulation (sim/) in Pyodide.
 *
 * Protocol (postMessage):
 *   main -> worker  {id, fn, args}        fn = "init" or any web/py/bridge.py Bridge method
 *   worker -> main  {id, ok, result}      result is the decoded JSON value
 *                   {id, ok:false, error}
 *                   {progress: "text"}    boot progress lines
 */
const PYODIDE_VERSION = "0.26.4";
const PYODIDE_BASE = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
const REPO = "/repo";

let pyodide = null;
let pyCall = null;

function progress(text) {
  self.postMessage({ progress: text });
}

async function boot(bundleUrl) {
  progress("加载 Pyodide 运行时…");
  importScripts(PYODIDE_BASE + "pyodide.js");
  pyodide = await loadPyodide({ indexURL: PYODIDE_BASE });
  progress("下载模拟内核与数据…");
  const bundle = await (await fetch(bundleUrl, { cache: "no-cache" })).json();
  const FS = pyodide.FS;
  const mkdirp = (dir) => {
    let cur = "";
    for (const part of dir.split("/").filter(Boolean)) {
      cur += "/" + part;
      if (!FS.analyzePath(cur).exists) FS.mkdir(cur);
    }
  };
  const write = (rel, text) => {
    const path = `${REPO}/${rel}`;
    mkdirp(path.substring(0, path.lastIndexOf("/")));
    FS.writeFile(path, text, { encoding: "utf8" });
  };
  for (const [rel, text] of Object.entries(bundle.files)) write(rel, text);
  for (const [rel, text] of Object.entries(bundle.sources)) {
    // sim/*.py live at repo root; web/py/*.py are keyed "py/<name>" relative to web/.
    write(rel.startsWith("sim/") ? rel : `web/${rel}`, text);
  }
  progress("初始化数据注册表（DataRegistry）…");
  await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, "${REPO}")
sys.path.insert(0, "${REPO}/web/py")
import yaml_shim
sys.modules["yaml"] = yaml_shim
import bridge
`);
  pyCall = pyodide.globals.get("bridge").call;
  progress("模拟内核就绪");
}

self.onmessage = async (event) => {
  const { id, fn, args } = event.data || {};
  try {
    if (fn === "init") {
      if (!pyodide) await boot(args && args[0] ? args[0] : "build/sim_bundle.json");
      self.postMessage({ id, ok: true, result: { pyodide: PYODIDE_VERSION } });
      return;
    }
    if (!pyCall) throw new Error("simulation not initialised");
    const out = pyCall(fn, JSON.stringify(args || []));
    self.postMessage({ id, ok: true, result: JSON.parse(out).r });
  } catch (err) {
    self.postMessage({ id, ok: false, error: String(err && err.message ? err.message : err) });
  }
};
