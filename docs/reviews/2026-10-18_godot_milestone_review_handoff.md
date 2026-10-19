# Godot M1–M8 复查与修复交接（2026-10-18）

> [!CAUTION]
> **本轮修改未在 Godot 中运行过。** 修改所在的电脑上 Godot 被安全策略（Santa）拦截，所有改动只做了静态校验：`gdparse` 语法解析、`tools/check_gdscript_isolation.py --strict`、`tools/compile_runtime_json.py --check`，以及局部变量重复声明扫描。Python 参考模拟 10/10 测试通过，365 天黄金对拍 14/14 吻合。
>
> **下一位协作者在开始任何新工作前，请先在能运行 Godot 4.6 的机器上执行：**
>
> ```bash
> python3 tools/run_all_gates.py          # 必须输出 ALL_GATES_PASSED，退出码为 0
> python3 tools/run_all_gates.py --perf   # 可选：30 年性能基准
> ```
>
> 如果 Godot 不在 PATH 中，请设置 `GODOT=/path/to/Godot`。门禁失败时，请先查看下面的「高风险点」。

相关提交：`7292358`、`fbb3257`、`bdc6eca`（基于 `95312df`）。

## 1. 门禁行为变化（务必知道）

- `tools/run_all_gates.py` 现在会在以下情况**返回非零**：
  - 任一测试脚本报错、超时，或没有打印成功标记
  - 黄金对拍不一致
  - 找不到 Godot（可加 `--allow-no-godot` 跳过）
- 门禁会先执行一次 `godot --headless --import` 来刷新 `class_name` 缓存，因为新增了 `FuzzyBand` 等类。
- 门禁改用 `compile_runtime_json.py --check`：**不写文件**，只检查已提交的 `game/res/data/*.json` 是否与 YAML 编译结果一致。改了 `data/*.yaml` 或编译器后，必须先运行 `python3 tools/compile_runtime_json.py` 重新生成数据，再一起提交。上一轮正是因为旧的 `--verify` 会直接重写文件，才漏提交了 `events.json` 和 `manifest.json`。

## 2. 高风险点（按优先级）

| # | 改动 | 风险 | 如何确认 / 回退 |
|---|---|---|---|
| R1 | 重新生成并提交了 `events.json` 和 `manifest.json`（新增 `when_ast`，来自上一轮编译器加入的 `"when"` 键） | 我推断另一台电脑的 14/14 黄金对拍用的正是这份重新生成的数据（因为旧门禁会先重写数据），但**没有实测**。 | 跑 `headless_golden_runner.gd`。如果不一致，用 `git show 95312df:game/res/data/events.json` 取回旧文件对比，排查 `when_ast` 求值。 |
| R2 | `m01_core.gd` 新增 `handle_custom_op`（`end_tenure`、`add_all_keys`、`if_then`、`random_branch`、`schedule_event_window` 等）；`EffectProcessor` 会把效果上的 `reason/event/branches/cond/then/else` 传给自定义处理函数 | 之前这些效果被静默丢弃。数据里只用到 `end_tenure`（E-1983-08，第一年之后）和 `add_all_keys`（只在玩家行动中出现），所以第一年的黄金对拍应该不受影响。`random_branch` 和 `schedule_event_window` 会消耗随机数，默认使用 `events` 流（和 Python 一致）。 | 跑黄金对拍和 `test_m5_scheduler.gd`。 |
| R3 | `m14_endings.gd` 按 Python 的 step 20 重写：原因词汇和优先级、30 天国家崩溃连续计数、领导人死亡或失能检查、第 5478 天时代结束（取代写死的 1995-11-04） | 健康检查只在领导人键已激活时才运行（Python 中贝京第一年健康值最低约 65.5）。如果 Godot 端 `health[begin]` 读出异常值，游戏可能**第 1 天就结束** → 黄金对拍会报 "ended early"。 | 跑黄金对拍。出问题时检查 `state.params.get_val("health","begin")`。 |
| R4 | `SimRNG`：`from_dict` 和按需创建的随机数流都保持 Python 一致模式 | 9 个内置流不受影响。只有读档或使用未知流名时行为会改变（改成和 Python 一致）。 | `test_m8_release.gd`（读档后继续运行，哈希一致）。 |
| R5 | `SaveSystem` 改为「种子 + 指令日志」存档，用 `load_into()` 回放恢复；`ReplaySystem` 按 (day, seq) 排序，包含目标日当天的指令，并沿用原局的 headless 模式 | 存档格式升级到 1.1.0。旧存档没有种子时默认用 19770620。 | `test_m8_release.gd`。 |
| R6 | UI 闭环（启动 → DeskMain、`autoload/SimEngine.gd` 逐日推进、输入映射、DeskMain 实例化抽屉和弹窗、D-088 模糊档位） | 最可能在运行时出错，比如 tscn 资源引用、Godot 4.6 类型检查、在 `-s` 脚本模式下访问 autoload。这些都**没有在编辑器里打开过**。 | 跑 `test_m6/m7/m8`、`ui_constraints_validator.gd`，并**在编辑器里手动启动一次游戏**：Space 暂停/继续，1–5 调速，Ctrl+1–7 开抽屉，F1–F7 切图层，L/C 打开账本/百科，F8/F9 快速存档/读档。 |
| R7 | `AutoPauseEvaluator`：投票请求到期才暂停；红色警报只在**新出现**时暂停（记录在 `state.run`，不参与哈希） | 只影响交互体验，不影响哈希。 | `test_m5_scheduler.gd`。 |

## 3. 已知未修复（会改变状态哈希，必须逐项做，每项都跑黄金对拍）

> [!WARNING]
> 当前黄金对拍只覆盖第 1 年，并且**不哈希 `modules`、`pending`、`history`、`run`**。下面这些差异在第 1 年都没被触发，所以「14/14 通过」**并不代表**和 Python 完全一致。建议先把 `tools/export_golden.py` 扩展到更长时间段（例如 5 年，加入有玩家行动的机器人对局），再处理这些差异。

1. **M2 与 Python 不一致**：
   - 政策杠杆边的字段映射（`c/t/k/s/w` → `coef/shape/pivot`）
   - 边上的 `gate` 被忽略
   - `delay` 被当成 `lag_months`
   - `quad` 形状公式不对
   - 冲击记忆没有 ±30 上限
   - 阈值逻辑简化（缺 `confirm/min_on/cooldown/latch`）
   - 历史长度应为 `history_24m`（24 条，预填当前值）
   - `era` 字段把年份当成了时代编号
   - `chance` 在 p≤0 或 p≥1 时 Python 不抽随机数
   - `weighted_pick` 在总权重为 0 时 Python 不抽随机数
   - `CanonicalSerializer` 在 |x|<1e-4 时没有用科学计数法
2. **M10 D-061**：一次否决后会关闭预算案，「逾期 90 天解散议会」这一分支永远到不了。另外每年 1 月 1 日都会自动提交预算案，Python 没有这一步。
3. **M08**：运行时没有执行 9 派系合法性守恒（总和 100）；`sig.m08_armed_incident` 写成了参与哈希的 flag（Python 是 `pending.hooks`）。M09 的 `minister_overreach` 也是同样问题。
4. **M13 与 Python step 14**：阈值应为 80/65/50/35，阶段编号从 0 开始；缺少政变和暗杀风险累积、90 天情报预警、法治回归；生存模式下风险每月翻倍的逻辑 Python 里没有。
5. **M14**：继任（`continue_as_successor`）和 40 结局矩阵还没移植，目前任期一结束整局就结束。
6. **机器人**：`BotAdapters.on_week` 是空实现，基于机器人的回放和基准都无法和 Python 对齐。
7. **规格口径冲突**：政治资本软上限的溢出衰减，代码是 25%，DoD 写的是 50%，需要决定以哪个为准。
8. **铁律 9**：TopBar、各抽屉、地图、区域检视卡仍然直接读取 `SimState`；`SimReadonlySnapshot` 需要扩展后才能全面替换。地图图层 F1/F2/F5–F7 仍是固定颜色。
9. `docs/architecture/godot_architecture.md` 里仍有 `autoload/EventBus.gd`、`m13_authoritarian.gd` 等旧路径，需要同步更新。

## 4. 本轮修复清单（摘要）

- 门禁和工具：同上面第 1 节；黄金对拍路径改为相对项目，可用 `$GOLDEN_PATH` 覆盖。
- 模拟层：
  - M01 补上自定义效果处理（见 R2）
  - M14 对齐 Python（见 R3）；M13 改发 `coup`，M06 的 `death` 改为字符串
  - SimDirector：注册表为空时也会加载数据；指令先校验后记录；玩家行动写入 M05 的 `staged_actions`
  - 删除死代码 `m13_authoritarian.gd`
- 存档和回放：见 R5。
- 性能基准：计入快照开销；按时钟标记区分日常和月初；不足 10950 天直接失败，不再出现 R=0 的假通过。
- UI：见 R6；新增 `FuzzyBand.gd`；快速存档改为 F8，不再和 F5 冲突。
- 测试：
  - M8 改为真实读档后继续运行，比对哈希
  - M5 补了结局仲裁、字符串结束原因、M01 自定义效果、警报暂停的测试
  - M7 断言账本行里不含原始数值
