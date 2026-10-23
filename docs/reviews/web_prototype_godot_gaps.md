# Godot 版与代码意图的差距（网页原型复刻时发现）

> 网页原型（`web/`）按**代码意图**复刻 Godot 版：布局坐标、文字格式、按键、推进节奏、信号流都和 Godot 一致，但下面这些在 Godot 版里实际**没生效**或**明显是 bug** 的地方，网页版按设计意图实现了。若要两边重新一致，应该在 Godot 里修下面这些点（编号便于在提交信息里引用）。
>
> **状态（2026-10-23）**：G1–G13 均已在 Godot 端修复。唯一例外是 G10 中给事件标题加 `ink_stamp` 墨章的部分，还没做。这些修改**同样没有在 Godot 中运行过**，只做了静态校验：`gdparse`、`check_gdscript_locals.py`、`check_gdscript_isolation.py --strict`。验证步骤见交接文档的风险项 R8。
>
> 来源：静态阅读 `game/ui/**`、`game/autoload/SimEngine.gd`、`game/project.godot`（Godot 无法在复刻所用的机器上运行，个别渲染结论基于 Godot 4 的已知行为，需要在 Godot 里确认）。

| # | Godot 现状 | 网页版做法 | 建议的 Godot 修复 |
|---|---|---|---|
| G1 | `mahapach_1977_theme.tres` 挂在 `DeskMain` 上，但所有控件都在 `CanvasLayer` 下，Godot 4 的主题继承不穿过 CanvasLayer，所以实际显示的是 Godot 默认深色主题（半透明深灰面板、白字、16px），背景是默认清屏色 #4D4D4D | 使用作者设计的纸张主题：纸色 #F4EFE6、墨色 #1E1C1A、14px；按钮悬停 #0038B8，按钮获得焦点 #C88A1E；桌面背景用纸张底色加 `paper_grain` 颗粒效果 | 在每个 CanvasLayer 的根 Control 上设置 `theme`，或在 project.godot 里设置 `gui/theme/custom` |
| G2 | TopBar 的 4 个槽读取不存在的参数：`government_approval`、`idf_readiness`、`us_wh_warmth`、`us_cong_support`，永远显示 0 | 映射到参考模拟里的真实参数：`party_standing`、`readiness`、`us_admin_relation`、`us_congress_relation`（见 `web/js/core/StateView.js` 的 `PARAM_ALIASES`） | 把 TopBarController 和 D5 改成读取真实参数名 |
| G3 | DeskMain 从未实例化 `D1–D7_*Drawer.tscn`；打开抽屉只显示一个 920×800 面板和标题，而且面板盖住了标签行 | 面板放在标签行下方，内容按 D1–D7 控制器的格式显示；D3 增加可执行行动列表，D4 画出真实的一跳因果图 | 在 DrawerContainer 的面板里实例化对应的 D 场景，面板向下偏移 |
| G4 | `CausalGraphCanvas` 对每条边都画同一条线 (80,70)→(240,180) | 每条边画在实际的两个端点之间 | 改为按节点索引画线 |
| G5 | 地图区域只能看不能点：没有任何代码调用 `select_from_ui()` 或 `contains_point()`，所以 `region_selected` 永远不会触发，区域检视卡永远不出现 | 左键点击区域时做多边形命中检测，弹出检视卡 | 在 IsraelMapCanvas 的 `_gui_input` 里做命中检测并发出信号 |
| G6 | 地图缩放以左上角为中心；平移和双击复位会把地图跳到屏幕 (0,0)，丢掉 (240,52) 的偏移 | 以光标为中心缩放；平移时保留偏移；双击回到原始位置 | 修正 position 的计算 |
| G7 | DrawerContainer 是隐形的 920×900 Control，`mouse_filter=STOP`，会挡住它下面地图区域的鼠标事件 | 没有打开抽屉时不拦截鼠标 | 把 mouse_filter 设为 IGNORE，只有面板本身接收事件 |
| G8 | `occupied_hatch` 着色器读取一张不存在的纹理；未带纹理的 Polygon2D 很可能直接渲染成纯白，看不到斜纹 | 在热力层颜色上叠加 45° 斜纹（density 14，rgba(46,41,36,0.55)） | 着色器改用 `COLOR` 作为底色，不再采样 TEXTURE |
| G9 | 区域检视卡的“治安姿态”下拉框把选项序号 0/1/2 当作 0–100 参数的值提交；`SimDirector` 也拒收 `region_absorption_priority`，所以阿利亚安置滑块无效 | 序号映射为 20/50/80；接受三个区域参数的修改 | 改映射，并在 `submit_command` 的白名单里加入 absorption |
| G10 | CausalTooltip、引导聚光灯、`ink_stamp` 和 `paper_grain` 着色器都没有任何调用方 | 点击顶栏数值、检视卡指标或因果图节点会打开因果提示，可锁定，最多 3 个；首次进入时显示 8 步引导；事件标题用墨章效果 | 把对应信号接上 |
| G11 | 卸任史书的 `next_page()` 没有接任何输入；翻页后会用 "C" 重新渲染 | 点击或按 → 翻页 | 接上输入，翻页时保留评级 |
| G12 | 事件弹窗正文几乎总是默认句“大转折正在发生。”（待处理事件不带 summary） | 显示事件的 summary 或 background，并自动加上百科链接 | 把事件定义里的文本带进待处理事件 |
| G13 | TopBar 的通胀红色是“粘住”的，降回 100 以下也不恢复 | 降回后恢复原色 | 加上 else 分支 |

另外两点不是 bug，但两边实现方式不同：

- **模拟内核**：网页版运行的是 Python 参考模拟（`sim/`，通过 Pyodide）。它和 Godot 的 GDScript 移植版在第一年黄金对拍上一致，但 Godot 版仍有若干未对齐的地方，见 `2026-10-18_godot_milestone_review_handoff.md` 第 3 节。所以长期运行时，网页版的数值以 Python 参考实现为准。
- **存档**：网页版的快速存档放在浏览器 `localStorage` 里，格式是“种子 + 指令日志”，读档时回放并校验哈希；Godot 版写到 `user://quicksave.ipsave.json`，两者文件不互通。
