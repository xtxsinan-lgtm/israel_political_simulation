# 以色列政治策略游戏（设计阶段）

> [!CAUTION]
> **协作须知（2026-10-18）**：提交 `7292358`、`fbb3257`、`bdc6eca` 中的 Godot 改动**还没有在 Godot 中运行验证**（修改所在的机器上 Godot 被拦截）。开始新工作前，请先在能运行 Godot 4.6 的机器上执行 `python3 tools/run_all_gates.py`，确认输出 `ALL_GATES_PASSED`。风险清单、验证步骤和已知未修复问题见 [docs/reviews/2026-10-18_godot_milestone_review_handoff.md](docs/reviews/2026-10-18_godot_milestone_review_handoff.md)。验证通过后可以删除这条提示。

一款以以色列（1948年至今）为背景的硬核政治策略游戏。第一阶段采用剧本制：玩家扮演一位已去世的真实历史总理，从就任开始，在以天为单位推进的连续时间里，一方面兑现承诺、守住党的立场，一方面推动以色列走向自己想要的方向。同时还要平衡这个国家的结构性矛盾：世俗与宗教、族群分化、犹太国家与阿拉伯公民、大国依赖与战略自主、领土与定居、经济意识形态、安全与民主法治，以及外部冲突。

## 网页原型

`web/` 是 Godot 主界面的网页复刻版，内核直接运行 Python 参考模拟。启动方法：`python3 tools/build_web.py --verify && python3 tools/serve_web.py`，然后打开 http://127.0.0.1:8777/ 。详见 [web/README.md](web/README.md)。复刻过程中发现的 Godot 版问题见 [docs/reviews/web_prototype_godot_gaps.md](docs/reviews/web_prototype_godot_gaps.md)。

## 文档

| 文档 | 内容 |
|---|---|
| [design_document.md](docs/design_document.md) | 系统设计草案 v5：总理视角、剧本、三层目标（承诺/立场/愿景）、连任与继任、独裁路线、地图、数值、事件系统、第二阶段的生涯模式 |
| [contradiction_parameters.md](docs/contradiction_parameters.md) | 各对矛盾的参数设计（精简版） |
| [events/](docs/events/README.md) | 事件库：格式规范、数值词典，以及1948–2006年按时代分类的事件 |

## 状态

设计阶段。所有公式系数与阈值均为示意，尚未经过数值原型校准。首个原型计划从贝京1977剧本开始。
