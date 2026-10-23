# 网页原型（Web prototype）

在浏览器里 1:1 复刻 Godot 版的“总理办公桌”主界面（`game/ui/`），内核直接运行 **Python 参考模拟**（`sim/`，经 Pyodide 跑在 Web Worker 里）。屏幕上的数字和 Godot 版黄金对拍所用的参考轨迹（`data/golden/begin_1977_365d.json`）是同一个来源。

## 在线版

**https://xtxsinan-lgtm.github.io/israel_political_simulation/** （自检页：`selftest.html`）

每次推送到 main，只要改动了 `web/`、`sim/`、`data/` 等目录，`.github/workflows/pages.yml` 就会自动运行 `build_web.py --verify` 并重新部署。如果打包后的数据和黄金轨迹不一致，构建会失败，不会发布。

## 本地运行

```bash
python3 tools/build_web.py --verify   # 生成 web/build/（YAML→JSON 打包），并在打包后的数据上复跑 365 天黄金对拍
python3 tools/serve_web.py            # 打开 http://127.0.0.1:8777/
```

- 首次加载需要从 jsDelivr 下载 Pyodide（约 10 MB），之后由浏览器缓存。
- `http://127.0.0.1:8777/selftest.html`：在浏览器里复跑黄金对拍，应显示 14/14。
- 自动化检查（使用本机 Chrome 的无头模式，不需要 Node 或 Deno）：
  ```bash
  python3 tools/web_e2e.py http://127.0.0.1:8777/selftest.html                    # 黄金对拍
  python3 tools/web_e2e.py "http://127.0.0.1:8777/index.html?e2e=1" --timeout 240  # 端到端流程
  ```
- 改了 `sim/`、`data/*.yaml` 或 `web/py/*.py` 后，需要重新运行 `build_web.py`。`web/build/` 是生成目录，不提交到仓库。

## 操作（与 Godot 相同）

| 按键 | 作用 |
|---|---|
| Space | 暂停 / 继续 |
| 1–5 | 设定速度并继续（每天 2 / 1 / 0.5 / 0.25 / 0.1 秒） |
| Ctrl/⌘ + 1–7 | 打开 D1–D7 抽屉（再按一次关闭） |
| Tab | 依次切换抽屉 |
| F1–F7 | 切换地图热力层 |
| L / C | 打开国家总账本 / 历史百科 |
| F8 / F9 | 快速存档 / 快速读档（存在浏览器 localStorage） |
| Esc | 按层级关闭：提示 → 弹层 → 抽屉 → 总账本和百科 |

地图：滚轮缩放，右键或中键拖动平移，双击复位，左键点区域打开检视卡。点击顶栏数值、检视卡指标或因果图节点，会弹出因果提示（可锁定，最多 3 个）。

## 结构

```
web/
  index.html, css/            1920×1080 舞台，按窗口等比缩放；6 个 CanvasLayer 对应 DeskMain.tscn
  js/main.js                  启动（对应 BootSplash.gd）
  js/core/                    EventBus / SimEngine（推进与自动暂停）/ UIManager（按键与抽屉）/ StateView / FuzzyBand
  js/ui/                      各组件，逐一移植 game/ui 下的控制器
  js/sim/                     Pyodide Worker 和 Promise 客户端
  py/bridge.py                模拟桥：对应 SimDirector、AutoPauseEvaluator、SaveSystem
  py/yaml_shim.py             浏览器内的 yaml 替身（数据在构建时已转成 JSON）
```

## 复刻口径

按 Godot 的**代码意图**复刻：布局坐标、文字格式、按键、推进节奏、信号流都与 Godot 一致，同时套用作者设计的纸张主题，并接上 Godot 版里没生效的部分（D1–D7 抽屉内容、区域检视卡、因果提示、着色器效果）。逐项差异和对应的 Godot 修复建议见 [`docs/reviews/web_prototype_godot_gaps.md`](../docs/reviews/web_prototype_godot_gaps.md)。
