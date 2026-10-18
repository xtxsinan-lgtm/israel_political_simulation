# 设计决议记录（DECISIONS）

> [!IMPORTANT]
> 本文件记录主代理对各模块规格提出问题的裁决。**效力高于 contracts.md 中与之冲突的条文**；阶段2会把这些决议合并回 contracts.md 与 parameters.yaml。所有后续规格编写者必须先读本文件。

## 第1批（M01、M02、M12）

### 数值与漂移（M02）
| 编号 | 决议 |
|---|---|
| D-001 | **全局采用 M02 的换算**："toward X at k%/month" 统一表达为 惯性 α = 0.10 + 单步上限 k% × 量程。所有模块的漂移描述都按此换算。 |
| D-002 | **政策杠杆**登记为 parameters.yaml 的新类型 `lever`（不另建 levers.yaml），保持唯一事实来源。M02 附录A的5个杠杆与 appointment_gap、haredi_cohort 一并收录。 |
| D-003 | **事件冲击的衰减**采用 M02 方案：事件的 add 效果只有 30% 进入衰减记忆项（ρ=0.3, μ=0.05）。**需要长期或永久生效的效果，必须写成修正器挂边**，不得依赖一次性 add。事件 YAML 转换时按此规则改写。 |
| D-004 | 贝京1977开局值以 **M14 规格为准**；M14 完成后，M02 按其 §12 重新求解基线。 |
| D-005 | M02 附录C 的25条跨模块边草案，作为 M03、M07、M08、M09、M11 的**默认值**；这些模块的规格可以修改，但必须在自己的规格中写明替换了哪几条。 |
| D-006 | 采纳 M02 附录B 的 B1–B7（lever 类型、on_effect_applied 回调与 source_id、修正器 edges 字段、drift 以 causal_edges.yaml 为准、thr.* 阈值旗标自动登记、步骤10扩充、引擎 set 不进记忆项）。 |

### 核心循环（M01）
| 编号 | 决议 |
|---|---|
| D-010 | **流量参数的一次性效果**（如"财政 −3%"）不直接改 budget_balance，而是记入当月的 `one_off_flows[参数]` 累加器，由 owner 模块在月度结算时计入（M10 计入当月支出与债务）。 |
| D-011 | 批准新增随机子流 core / politics / ai / economy / cosmetic（cosmetic 只用于不影响状态的表现层，不计入哈希）。 |
| D-012 | **周结算日为星期日**（以色列一周从星期日开始，内阁例会在星期日举行）。 |
| D-013 | 继任初值采纳：政治资本 40；同党继任 党内地位 −5（下限30）；换党执政 党内地位 60。 |
| D-014 | 存档为明文 JSON、不压缩（第30年约0.7MB），接受。 |
| D-015 | 采纳 M01 附录B 的 B-1–B-8（效果 priority 字段与 mul 语义、暂停阶段P、owner 写入按增量、量化与规范化哈希、表达式 month/day/months_since/era 定义、修正器登记表、debt 减少规则）。 |

### 事件引擎（M12）
| 编号 | 决议 |
|---|---|
| D-020 | 接受 B-6：时代通用事件 E-Gxx 按冷却可重复，豁免"一局一次"规则。 |
| D-021 | **玩家的事件选择立即应用**（游戏处于暂停态，不影响确定性）；选择会作为输入记录进回放日志。 |
| D-022 | 承诺键、人物ID、职位ID 以 **M04（承诺）与 M06（人物、职位）规格为准**；M12 范例中的 peace_security、sadat、foreign_minister 等为占位，阶段2统一替换。 |
| D-023 | "顾问自动处理【小】事件"**默认开启**，可在设置中关闭。 |
| D-024 | 强制弹窗月上限3：P0 计入但不拦截（P0 总是弹出），采纳。 |
| D-025 | 采纳 M12 附录B 的 B-1–B-8（新 op、表达式增补函数、relation 职位键、修正器 terms 等、步骤18子步骤、玩家选择立即应用、stance_shift_by_corridor）。 |

### 跨模块约定（适用于后续所有规格）
- 表达式语言以 **M12 规格 §表达式** 为准（含其新增的函数）。
- 效果格式以 **M01 + M12 附录B 合并后的版本**为准。
- 数值漂移与因果边以 **M02 规格**为准，新参数的漂移一律写成因果边。
- 结算顺序以 **M01 规格**为准。

## 第2批

### 行动与政治资本（M05）
| 编号 | 决议 |
|---|---|
| D-030 | **杠杆边归属**采用 M05 的 B-1：政策随附的边由 M05 声明，可以指向任何模块的参数；目标模块只能调整系数，不能删边。 |
| D-031 | **政治资本规模**采纳：月产出约15、软上限92、继任40。事件库中的资本数值**不统一缩放**（"大"力度 ±20–30 约等于2个月产出，符合"大事件"的分量）；阶段3以 BOT 的 S6 指标再校准。 |
| D-032 | F5 指标口径：按"经济类行动 + 经济政策档位"统计，不把安全、外交类行动硬绑到经济轴。 |
| D-033 | **立场刻度**：五条轴统一使用绝对刻度 −100..+100。`gov_axis_position` 由当前政策档位与行动冲量计算，axis_base = 0，开局位置自然来自剧本开局的政策档位；**M04 的走廊区间写在同一绝对刻度上**。 |
| D-034 | **行动与事件不重复结算**：行动完成时设旗标 `act.<action_id>`；与之对应的事件在 YAML 转换时把该旗标列入"失效"条件（M12 转换规则统一追加）。 |
| D-035 | 采纳 M05 附录A（policy_level、gov_axis_position、favor_party、favor_character，新 scope `policy`）与附录B 的 B-1–B-10。 |

### 议会、选举与组阁（M03）
| 编号 | 决议 |
|---|---|
| D-040 | `bloc_support` 定义为**选民集团对现政府的支持度**（不是总理所在党的得票率）。各集团开局值由 M14 定稿；采纳 M03 建议的 arab_citizens 开局约15作为参考。 |
| D-041 | entities.parties 新增 M03 B-1 的18个ID（含 independents、other_lists、pm_new_party）。 |
| D-042 | 采纳 M03 对已完成规格的改动：M01 的 vote_requests 增加 due_day（B-3）；M12 的竞选钩子改到星期日（B-4，与 D-012 一致）。阶段2统一修订 M01、M12 文本。 |
| D-043 | M03 的月度结算（盟党满意度、执政疲劳、选民犬儒）放在**每月第一个星期日的步骤7**，不新增结算步骤。 |
| D-044 | **团结政府轮值**：玩家不担任总理的半段，玩家继续操作，任期不中断；此期间只能用副总理可用的行动，行动的政治资本价格 ×1.5，不能任免对方党派的部长。统计 S1（连任率）时，轮值政府算作胜选。 |
| D-045 | 采纳 M03 附录A 的11个参数与附录B 的 B-1–B-11（含 M05 的 absolute80、postpone_election 改用80票）。 |

## 第二批补充裁定（M04 完成后，供 M06–M11、M13–M15 遵守）

| 编号 | 裁定 |
|---|---|
| D-050 | `stance_deviation` 改为 `derived`（M04 B-1）：事件库中的“立场偏离[轴] ±N”统一转写为 `stance_shift_by_corridor`（移动政府立场冲量）；在党走廊内仅影响派系情绪，超出走廊才产生党层偏离。 |
| D-051 | **开局立场宽限期**：采纳 M04 §4.2.2 的“6个月全额豁免 + 18个月线性归零（共24个月）”遗产政策宽限期，吸收新政府继承前任政策时的初始走廊偏离。 |
| D-052 | 采纳 M04 B-3 的 `term_provider` 机制：M02 节点可挂载 `term_provider` 处理函数动态提供贡献项并进入 `explain`，由 M02 统一执行惯性与夹紧计算。 |
| D-053 | **宏大愿景与继任者**：宏大愿景绑定剧本初始主角，主角离任时若未达成即判定愿景失败；同党继任者不可继承愿景成就本身，但可在继任承诺包中获得“延续前任路线”的普通承诺项。 |
| D-054 | **动态新党实体**：采用静态预留槽位 `new_party_a/b/c` 与派系 `founders_a/b/c`（阶段2将 M03 的 `pm_new_party` 统一合并为 `new_party_a`），不在存档中生成未登记的动态政党ID。 |
| D-055 | 采纳 M04 附录A 的6个参数（`faction_mood`、`faction_weight`、`party_cohesion`、`challenger_strength`、`cynicism`、`promise_credit`；注：阶段2将 M03 的 `voter_cynicism` 与 M04 的 `cynicism` 合并统一）及附录B 的 B-1–B-11、附录C 的旗标与修正器。 |

## 第三批裁定（M10 完成后，供后续模块遵守）

| 编号 | 裁定 |
|---|---|
| D-060 | 采纳 M10 附录A：新增实体列表 `entities.budget_items`（`defense, absorption, religion, dev_towns, education, welfare, infrastructure, settlements`）及参数 `budget_slider`（lever, scope: budget_item）、`strike_risk`（derived, scope: national，总工会罢工风险指数）。 |
| D-061 | 采纳 M10 附录B：在 M01 `KNOWN_MODIFIER_FACTORS` 中补充登记 `"fiscal_spend"`（财政支出乘数）与 `"us_aid"`（美援财政/外汇乘数，供 M07 美国外交与贷款担保事件联动）；年度预算案表决若单次未过退回 `DUE` 允许修改重提，满 90 天（`deadline_day`）仍未通过才调用 `m03_dissolve_knesset(reason="budget_overdue")`。 |
| D-062 | **1977 开局预算周期**：1977-06-20 开局时 `budget_cycle.status = "PASSED"`，首次年度强制预算表决周期于 `1978-01-01`（步骤17）开启、`1978-04-01` 截止。 |
| D-063 | **内阁派系分肥口径**：计算 M04 本党派系内阁占比 $ms_f$ 时，采用**按本党在任部长去重人数占比**（与 M04 §4.1 对齐）。 |
| D-064 | **部长主动提案折扣**：批准内阁部长在每周步骤6主动提交的部门提案（`MinisterProposal`，每周最多1份）享受 **30% 政治资本折扣**且不占玩家每周 2 个主动行动槽位。 |
| D-065 | 采纳 M06 附录A 新增参数 `character_stress`（`stock`, `scope: character`, `range: [0, 100]`, `tick: monthly`, `owner: M06`）及附录B 的 `relation[key]` 双模解析（支持 `CharacterId` 与 `OfficeId` 自动转发在任者）与 `ally_minister_dismissed(party_id, trust_penalty)` 信号。 |
| D-066 | 采纳 M07 附录A：新增 `country_war_readiness`、`peace_treaty_state`（`scope: country`），并将 `enemy_nuclear_progress` 的 `scope` 统一修正为 `country`（対象 `iraq, iran`）。 |
| D-067 | 采纳 M07 附录B/C：M03 在星期三结算国际条约批准法案后回调 `m07_ratification_result {bill_uid, passed}`；M12 表达式新增 `peace_treaty(c)`、`treaty_tier(c)`、`secret_channel(c)`、`nuclear_progress(c)`。 |
| D-068 | 在 M02/M12 参数解析器中内置 M07 的 4 项别名映射（`country_stability -> regime_stability`、`country_nuclear_progress -> enemy_nuclear_progress`、`annual_immigration -> immigration_inflow`、`country_relation -> us_admin_relation / power_relation / (100 - regime_hostility)`）。 |
| D-069 | 采纳 M09 附录A/B/C：将 M10 读取的 `security_index` 设为指向 M09 `public_security` 的只读属性别名（初值同为 `62.0`）；在 M12 表达式中注册 `front_phase(front_id)` 与 `casualties_total(front_id)`；在 M01 信号总线与 `AP04` 自动暂停触发器中登记 `minister_overreach` 信号。 |
| D-070 | 批准 `M09.GRO.01`（`mobilization -> growth`）采用 M09 按动员档位非线性注入 `[0.0, -0.08, -0.25, -0.75]` 的 `term_provider` 实现。 |
| D-071 | 批准 1991 海湾战争部署“爱国者”防空系统对 `under_missile_attack` 每周 `public_security` 惩罚减半（`-12.0 -> -6.0`）的细则。 |
| D-072 | 采纳 M08 B-1/B-2：`entities.pal_factions` 扩充为 9 枚举（`fatah, pflp, jordan_notables, local_mayors, village_leagues, mujama, hamas, pij, pa_security`），并在 `ParameterStore` 内置 `notables -> jordan_notables`、`left_factions -> pflp`、`islamic_jihad -> pij`、`islamic_assoc_strength <-> faction_strength[mujama]`、`palestinian_hostility -> pal_hostility`、`intifada_risk -> uprising_risk` 兼容别名。 |
| D-073 | 采纳 M08 附录A 的 4 个参数（`faction_moderation, faction_cohesion, collaborator_stigma, autonomy_progress`）及 B-3..B-5（含 `m08_spawn_hamas, m08_activate_delegation, m08_set_autonomy_modality, m08_start_intifada` 处理器）。 |
| D-074 | M02 跨模块边 `X.SM.02`（`pal_living_standard -> uprising_risk`）系数定稿为 `coef: 0.12`。 |
| D-075 | **巴方武装袭击联动**：M08 在步骤8通过效果队列追加 `public_security` / `deterrence` 的即时冲击（遵循 D-010 增量原则），同时发出 `sig.m08_armed_incident` 供 M09 更新报复窗口与军事统计。 |
| D-076 | 采纳 M11 附录A/B/C：将 `south_lebanon` 补入 `entities.regions_dynamic`（1977-06-20 开局 `exists = False`），采纳 M11 的 8 个区级/三难三角参数（`region_absorption_priority, region_investment_priority, region_security_posture, settler_population, trilemma_jewish, trilemma_democratic, trilemma_territory, region_alienation`）及 4 个 `m11_*` 处理器、4 个条件表达式函数。 |
| D-077 | 将 `resolve_region_id`（`north/central/south` $\leftrightarrow$ `galilee/triangle/negev` 双向同义别名解析）纳入 M01 `GameState` 公共辅助函数。 |
| D-078 | 在 `contracts.md` §3 锁定每周日步骤 8 内部子步骤顺序为 `8a`（M11 更新 `region_security`）$\to$ `8b`（M09 读取并结算 `public_security`）。 |
| D-079 | 奥斯陆协议 A/B/C 区比例在第一阶段仅保留在 `RegionState.oslo_shares` 内部，不额外暴露顶层标量参数。 |
| D-080 | 1977-06-20 开局 `public_security = 62.0`、`mobilization = 10.0`（统一对齐 M09/M10/M14，阶段2同步修订 M02 表格说明，且不影响开局零漂移）。 |
| D-081 | **威权路线评价封顶**：当 `centralization >= 60.0` 或曾触发暂停大选时，综合历史总评等级最高封顶为 **`B` 级**（永不可获 `S` 或 `A` 级）；采纳 M14 附录B 的 `B-14-01`..`03`（8 个统计查询函数、3 个 `m14_*` 处理器、同日多源 `end_tenure` 致命度优先级）。 |
| D-082 | **“伟大背离”战略破局奖励**：当玩家偏离本党传统走廊但成功签署正式和平条约或创立新党赢下大选时，免除走廊偏离扣分并给予 `+8.0` 分战略破局奖励。 |








