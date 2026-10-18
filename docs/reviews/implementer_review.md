# 阶段 2C：首席程序员可实现性审查报告（Implementer Review）

- **审查角色**：首席程序员（Lead Programmer）
- **审查日期**：2026-04-20（基准剧本开局日：`1977-06-20`）
- **审查范围**：
  - 权威契约与总表：[contracts.md](../contracts.md)、[parameters.yaml](../../data/parameters.yaml)（同步镜像 [docs/registry/parameters.yaml](../registry/parameters.yaml)）、[DECISIONS.md](../registry/DECISIONS.md)（`D-001`–`D-088`）、[flags.yaml](../registry/flags.yaml)、[modifiers.yaml](../registry/modifiers.yaml)
  - 全部 15 份模块规格书：`docs/specs/M01_core_loop.md` 至 `docs/specs/M15_ui_presentation.md`
  - 核心数据表：[causal_edges.yaml](../../data/causal_edges.yaml)、[policies.yaml](../../data/policies.yaml)、[actions.yaml](../../data/actions.yaml)、[thresholds.yaml](../../data/thresholds.yaml)、[characters.yaml](../../data/characters.yaml)、[world_tracks.yaml](../../data/world_tracks.yaml)、[palestine_factions.yaml](../../data/palestine_factions.yaml)、[regions.yaml](../../data/regions.yaml)、[snapshot.yaml](../../data/scenarios/begin_1977/snapshot.yaml) 及 `data/events/*.yaml`（396 项结构化事件）
  - 自动化校验脚本：[audit_implementability.py](../../tools/audit_implementability.py)、[check_specs.py](../../tools/check_specs.py)、[validate_events.py](../../tools/validate_events.py)

> [!IMPORTANT]
> **核心审查结论：15 份规格无法实现之处 = 0**
> 全部 15 份模块规格（M01–M15）、权威接口契约（`docs/contracts.md`）与机器可读 YAML 数据表已 100% 闭环对齐，可通过确定性 Python 3.9 参考实现（阶段 3）与 Godot 4.x 移植（阶段 4）直接编码落地，无任何未决公式、悬空参数、未登记处理器或开局首月异常跳变。

---

## 1. 参数与 Scope 一致性审查（Parameter & Scope Consistency）

通过 [audit_implementability.py](../../tools/audit_implementability.py) 对全部 110 项注册表参数在全库中的定义、值域、实体索引（`scope`）与开局快照进行了静态与动态交叉核验：

| 检查项 | 核验结果 | 详细说明 |
|---|---|---|
| `data/parameters.yaml` $\leftrightarrow$ `docs/registry/parameters.yaml` | **通过（字节级一致）** | 110 项参数 ID、中文名、`type`、`scope`、`range`、`tick`、`owner`、`visible`、`era` 完全一致 |
| `snapshot.yaml` 110 项参数全覆盖与值域检查 | **通过（110/110）** | `data/scenarios/begin_1977/snapshot.yaml` `params:` 完整包含全部 110 项注册表参数，0 缺失、0 越界、0 非注册表遗留键 |
| 实体字典（`entities`）与别名路由（`aliases`）完备性 | **通过（0 非法键）** | 补全 `regions`（11区）、`fronts`（6战线）、`promises`、`characters`（含事件库历史人物）及职位缩写别名（`pm`, `defense`, `finance` 等），全库参数键引用 100% 合法 |
| 跨文件初值一致性（`snapshot` vs `regions` / `palestine_factions` / `M03` / `M04`） | **通过（零差异）** | 巴勒斯坦九大派系初值、11 区域安全/发展/疏离度/滑块、`party_cohesion: 57.04`、`cynicism: 20.0` 完全对齐 |
| 阶段 2B 事件库（396 事件）只读交叉校验 | **通过（396/396）** | `data/events/*.yaml` 的全部 `add/set/mul` 目标参数、实体键、旗标（211项）与修正器（111项）均与注册表 100% 匹配 |

---

## 2. 因果网 Day-0 (`1977-06-20`) 零漂移校验（Causal Net Zero-Drift）

按照 [M02_contradiction_model.md](../specs/M02_contradiction_model.md) §4 与 `D-006`、`D-052` 规定的统一目标均衡方程：
$$T_{\text{raw}}(p, k) = \text{baseline}(p, k) + \sum_{e \in \text{causal\_edges}} c_e \cdot f_e(x_s) + \sum_{pe \in \text{policy\_edges}} c_{pe} \cdot f_{pe}(\ell) + \text{term\_provider}(p, k)$$
$$T(p, k) = \text{soft\_clamp}(T_{\text{raw}}(p, k), \text{lo}_s, \text{hi}_s, w)$$

1. **边目标节点 100% 闭环**：
   - 将 `policies.yaml` `e:` 与 `causal_edges.yaml`（`M11.TRI.01/02`）指向的 12 个由所属模块专职公式结合因果边增量共同结算的参数（`immigration_inflow, regime_hostility, popular_hostility, regime_stability, arms_reliability, strategic_dependence, faction_strength, faction_legitimacy, islamic_assoc_strength, nuclear_exposure_risk, trilemma_jewish, trilemma_democratic`）显式声明入 `data/causal_edges.yaml` `nodes:`（标注 `mode: derived, module_managed: true`），消除任何悬空目标节点。
2. **32 个 `mode: level` 节点（79 个开局激活 `param[key]` 实例）零漂移验证**：
   - 修正 `challenger_strength` 的软夹紧下界为 `soft: {lo_s: 0, hi_s: 85, w: 13}`（原 `lo_s: 15, w: 13` 导致渐近下界为 `15 - 13 = 2.0`，无挑战者时 `x_0 = 0.0` 会在首月凭空跳升至 `+2.0`）。
   - 对全部 32 个 `mode: level` 节点反解并校准 Day-0 自然回归基线 `baseline`，经 [audit_implementability.py](../../tools/audit_implementability.py) 实测，全部 79 个激活节点键在 `1977-06-20` 的最大均衡偏差为：
     $$\max_{(p, k)} |T(p, k) - x_0(p, k)| = 0.000049 < 0.01$$
   - 确保游戏开局第 1 周与第 1 月在无玩家干预、无随机事件冲击时数值严丝合缝，绝无由于基线未配平导致的“首月莫名崩盘或暴涨”。

---

## 3. 20 步日结算顺序与 `op: custom` 闭环校验（Settlement Loop & Custom Handlers）

1. **每日 20 步结算顺序与读写隔离**：
   - 核对了 [contracts.md](../contracts.md) §3 与 [M01_core_loop.md](../specs/M01_core_loop.md) §4 的每日 20 步结算表：
     - **周结算日**固定为星期日（`weekday == 6`），步骤 `8a`（M11 更新 `region_security`）严格先于步骤 `8b`（M09 读取 `region_security` 更新 `public_security`，M08 检定巴方武装袭击，`D-078`）；
     - **月度结算日**（每月 1 日）按 `步骤 9 (M10 财政) -> 步骤 10 (M02 因果网 10a/10b/10c) -> 步骤 11 (M04 党内/承诺) -> 步骤 12a/12b (M07/M08 外部与巴方) -> 步骤 13 (M11 区域与三难) -> 步骤 14 (M13 集权与阻力) -> 步骤 15 (M05 政治资本与 M01 月度环形快照)` 顺序执行，无任何循环依赖或跨步脏读。
2. **10 随机子流隔离契约（`D-011`, `D-086`）**：
   - `events, world, elections, combat, random_events, core, politics, ai, economy, cosmetic` 10 个 `xoshiro128** + mul32` 子流在 15 份规格书中职责边界清晰；M15 仅使用 `cosmetic` 子流且不写入存档、不参与状态哈希。
3. **`op: custom` 与 `term_provider` 100% 登记闭环**：
   - 扫描 `data/actions.yaml`（104项行动）、`data/events/*.yaml`（396项事件）及 15 份规格书中的全部 `op: custom` 处理器（共 54 个独立调用名）与 `data/causal_edges.yaml` 中的 `term_provider` 回调，全部在 [contracts.md](../contracts.md) §4.2 与 §4.2.1 登记完毕（含 `m11_add_region` 别名与 `m10_monthly_terms` / `m10_quarterly_terms`）。

---

## 4. 15 份模块规格（M01–M15）可实现性逐项核查表

| 模块 | 规格文件 | 章节完整性 (0–13章) | 状态 Schema 与存档契约 | 公式定义域防卫（除零/夹紧/边界） | 随机子流与确定性 | 可实现性结论 |
|---|---|---|---|---|---|---|
| **M01** | [M01_core_loop.md](../specs/M01_core_loop.md) | 齐全 | `GameState`, `EffectQueue`, `monthly_snapshots` 完整 | `q(x) = floor(x*1e6+0.5)/1e6`、除零返回 `0.0` 并记 `E_DIV0` | `core` | **可直接实现（0 缺陷）** |
| **M02** | [M02_numbers_model.md](../specs/M02_numbers_model.md) | 齐全 | `CausalNetState`, `MemoryItem`, `ThresholdState` 完整 | 7 种边形状、`soft_clamp`、`headroom`、滞回双阈值完备 | `politics` | **可直接实现（0 缺陷）** |
| **M03** | [M03_parliament.md](../specs/M03_parliament.md) | 齐全 | `ParliamentState`, `BillItem`, `VoteRequest` 完整 | 120 席最大余额法守恒、轮值内阁成本乘数 `×1.5` 明确 | `politics`, `elections` | **可直接实现（0 缺陷）** |
| **M04** | [M04_party_promises.md](../specs/M04_party_promises.md) | 齐全 | `PartyState`, `PromiseItem`, `VisionState` 完整 | 24 个月遗产政策宽限期（6m豁免+18m线性）、去重部长分肥占比防除零 | `politics` | **可直接实现（0 缺陷）** |
| **M05** | [M05_actions_capital.md](../specs/M05_actions_capital.md) | 齐全 | `ActionState`, `PolicyState`, `IOULedger` 完整 | 软上限 `92` 衰减、76 项政策档位与 104 项行动冷却/前置完备 | `core`, `politics` | **可直接实现（0 缺陷）** |
| **M06** | [M06_characters_ai.md](../specs/M06_characters_ai.md) | 齐全 | `CharacterState`, `CabinetState`, `MinisterProposal` 完整 | `relation[key]` 双模解析（空缺返回 `0.0`）、健康衰老曲线有上下界 | `ai` | **可直接实现（0 缺陷）** |
| **M07** | [M07_world_diplomacy.md](../specs/M07_world_diplomacy.md) | 齐全 | `WorldState`, `SummitState`, `TrackDeltaPerm` 完整 | `country_relation[c]` 三路路由、峰会交易矩阵与条约等级 `[0,3]` 闭环 | `world` | **可直接实现（0 缺陷）** |
| **M08** | [M08_palestine.md](../specs/M08_palestine.md) | 齐全 | `PalestineState`, `FactionState`, `UprisingState` 完整 | 九大派系实力/合法性/温和度/完整度/污名公式与 `mujama` 同步闭环 | `world`, `combat` | **可直接实现（0 缺陷）** |
| **M09** | [M09_military_intel.md](../specs/M09_military_intel.md) | 齐全 | `MilitaryState`, `FrontState`, `WarPlan` 完整 | 动员四档目标 `[10,35,65,95]`、防空减半规则、情报精度 `79.650` 精确对齐 | `combat` | **可直接实现（0 缺陷）** |
| **M10** | [M10_economy_budget.md](../specs/M10_economy_budget.md) | 齐全 | `EconomyState`, `BudgetCycleState`, `AliyahCohort` 完整 | 预算逾期 90 天解散议会、通胀螺旋与动员非线性增长拖累 `[0,-0.08,-0.25,-0.75]` 明确 | `economy` | **可直接实现（0 缺陷）** |
| **M11** | [M11_map_regions.md](../specs/M11_map_regions.md) | 齐全 | `MapState`, `RegionState`, `SiteState`, `OsloShares` 完整 | 11 区域人口构成、定居者增长与三难三角顶点公式无除零风险 | `world`, `combat` | **可直接实现（0 缺陷）** |
| **M12** | [M12_event_engine.md](../specs/M12_event_engine.md) | 齐全 | `EventEngineState`, `ActiveEventInstance` 完整 | DSL 递归下降文法、18.0–18.6 子步骤、月度强制弹窗上限 3 清晰 | `events`, `random_events` | **可直接实现（0 缺陷）** |
| **M13** | [M13_authoritarian.md](../specs/M13_authoritarian.md) | 齐全 | `AuthoritarianState`, `ResistanceActorState` 完整 | C1–C5 五阶段、9 大阻力方反制、政变/暗杀月度检定直接触发 `end_tenure` | `politics` | **可直接实现（0 缺陷）** |
| **M14** | [M14_scenario_endings.md](../specs/M14_scenario_endings.md) | 齐全 | `TenureArchive`, `EndingResult`, `HistoricalEvaluation` 完整 | 12 级卸任原因致命度优先级、40 结局、八维评价、三大史派权重总和=1.0 | `core` | **可直接实现（0 缺陷）** |
| **M15** | [M15_ui_presentation.md](../specs/M15_ui_presentation.md) | 齐全 | `UIState`, `UserSettings`, `OptionUIPreview` 完整 | 表现层与模拟态严格只读解耦、`fuzzy` 参数总账本区间中位数排序防泄露 | `cosmetic` | **可直接实现（0 缺陷）** |

---

## 5. 阶段 2C 审查期间当场修复的数据与契约偏差汇总

在本次可实现性审查中，我们对发现的跨文件微小不一致当场完成了修正，并纳入 [audit_implementability.py](../../tools/audit_implementability.py) 守护：

1. **参数 Scope 与实体注册表补全（[data/parameters.yaml](../../data/parameters.yaml) & [docs/registry/parameters.yaml](../registry/parameters.yaml)）**：
   - 将 `regime_hostility` 与 `regime_stability` 的 `scope` 从 `arab_state` 扩展为 `country`，与 `M07` 规格、`policies.yaml`（`periphery_alliances: regime_stability[iran]`）、`actions.yaml`（`secret_channel`）和 `fixed_1977_1992.yaml`（`iran, ethiopia, sudan`）的外围国家索引完全对齐；
   - 在 `entities:` 中补全 `regions`、`fronts`、`promises`、`characters` 列表，并在 `aliases:` 中补全 `offices` 缩写别名映射。
2. **巴勒斯坦派系别名规范化（[data/policies.yaml](../../data/policies.yaml) & [begin_peace_in_eretz_israel.yaml](../../data/visions/begin_peace_in_eretz_israel.yaml) & [snapshot.yaml](../../data/scenarios/begin_1977/snapshot.yaml)）**：
   - 将 `open_bridges`、`civil_administration`、`village_leagues` 三项政策 `e:` 中的遗留键 `k: notables` 以及愿景文件中的 `faction_legitimacy[notables]` 统一替换为规范主 ID `jordan_notables`。
3. **1977 开局快照 110 项参数全量补齐与对齐（[snapshot.yaml](../../data/scenarios/begin_1977/snapshot.yaml)、[M03.yaml](../../data/scenarios/begin_1977/modules/M03.yaml)、[M04.yaml](../../data/scenarios/begin_1977/modules/M04.yaml)、[palestine_factions.yaml](../../data/palestine_factions.yaml)、[regions.yaml](../../data/regions.yaml)）**：
   - 补齐 `snapshot.yaml` `params:` 此前未内联的 32 项注册表参数（使 `params:` 完整覆盖 110/110 项参数），移除已合并的旧键 `voter_cynicism`，修正 `party_cohesion: 57.04` 与 `cynicism_init: 20`，并同步 `regions.yaml` 与 `palestine_factions.yaml` 的 1977 开局字段。
4. **因果网节点闭环与 Day-0 零漂移校准（[data/causal_edges.yaml](../../data/causal_edges.yaml)）**：
   - 新增 12 个 `mode: derived, module_managed: true` 节点声明，使全部因果边与政策杠杆边目标节点 100% 在 `nodes:` 中受管；
   - 修正 `challenger_strength` 软下界 `lo_s: 0`，并精确校准全部 32 个 `mode: level` 节点的 `baseline`，使 `1977-06-20` Day-0 全体激活节点键 $|T - x_0| < 10^{-4} < 0.01$。
5. **权威接口契约更新（[docs/contracts.md](../contracts.md)）**：
   - 更新目录树说明为 `policies.yaml（76项）`、`actions.yaml（104项）`；
   - 在 §4.2 增补 `m11_add_region` 别名说明，并新增 §4.2.1 `term_provider` 动态贡献项提供器登记总表。

---

## 6. 自动化验证运行结果

运行以下三条自动化校验命令均以 **0 错误（Exit Code 0）** 通过：

```bash
.venv/bin/python tools/audit_implementability.py
.venv/bin/python tools/check_specs.py
.venv/bin/python tools/validate_events.py
```

**最终审查裁定：15 份规格无法实现之处 = 0。准予进入阶段 3（Python 参考实现与自动平衡测试）。**
