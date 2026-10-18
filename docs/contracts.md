# 模块接口约定（contracts）

> [!IMPORTANT]
> 本文件与 [registry/parameters.yaml](registry/parameters.yaml)、[registry/DECISIONS.md](registry/DECISIONS.md) 共同构成所有模块规格与参考实现的权威约束。本版本已完整统合阶段 1–2 全部设计裁决（`D-001` 至 `D-088`）。任何模块实现与本文件冲突时，以本文件为准；修改本文件须在 [registry/CHANGELOG.md](registry/CHANGELOG.md) 记录。

## 1. 技术前提与确定性规范

| 项目 | 决定 |
|---|---|
| 游戏引擎 | Godot 4.x，GDScript |
| 运行时数据格式 | JSON（Godot 原生支持）；设计数据以 YAML 编写，构建脚本转换为 JSON |
| 参考实现 | Python 3.9（`sim/` 目录），用于验证可玩性，同时作为 Godot 移植的**黄金标准** |
| 移植验收与量化 | 同一份开局数据 + 同一个随机种子 + 同一串玩家输入，Godot 与 Python 跑 N 天后的全部数值必须一致（浮点误差 ≤ 1e-6）。每步末尾对写入值执行量化 `q(x) = floor(x × 1e6 + 0.5) / 1e6`；规范化序列化将数字转为百万分之一整数（`D-015`） |
| 随机数（10子流） | 全部随机数来自确定性 `xoshiro128** + mul32` 生成器，按 10 个独立子流划分：`events`、`world`、`elections`、`combat`、`random_events`、`core`、`politics`、`ai`、`economy`、`cosmetic`（其中 `cosmetic` 仅用于纯表现层，不存档、不计入状态哈希，`D-011`、`D-086`） |
| 存档格式 | 明文 UTF-8 JSON、不压缩（`.ipsave.json`，第 30 年约 0.7 MB，确保 Python 与 Godot 双向零差异互读，`D-014`） |
| 首个可玩版本 | "贝京 1977"（`begin_1977`，开局日 `1977-06-20`） |

> [!NOTE]
> Python 3.9 不支持 `match` 语句和 `X | Y` 类型标注写法，参考实现须使用 `Optional[X]`、`Union[X, Y]`。

## 2. 目录结构与全局别名解析契约

```
docs/
  design_document.md          总设计（v5）
  contracts.md                本文件（权威接口契约）
  spec_template.md            模块规格模板
  registry/                   参数、实体、旗标、修正器、决议登记表
  specs/M01_*.md … M15_*.md   模块规格（M01–M15）
  research/                   对标研究與验收指标（benchmarks.md）
  events/                     事件库（Markdown，供人阅读）
data/                         机器可读设计数据（YAML），游戏与模拟共用
  causal_edges.yaml           M02 因果网节点、本模块边、跨模块边与政策杠杆边
  policies.yaml               M05 持续性政策定义（26项）
  actions.yaml                M05 政治/内阁/外交/军事/秘密行动目录（56项）
  characters.yaml             M06 历史人物库（43名）
  world_tracks.yaml           M07 1977–1992 外部世界历史轨道与世界旗标
  palestine_factions.yaml     M08 巴勒斯坦九大派系初始数据与AI参数
  regions.yaml                M11 11个区域、25个关键地点、5张战略规划图
  scenarios/begin_1977/       贝京1977剧本配置（scenario.yaml）与完整初始快照（snapshot.yaml）
sim/                          Python 参考实现与验证脚本
tools/                        转换、校验脚本（check_specs.py 等）
game/                         Godot 工程（阶段4以后）
```

### 2.1 参数与实体索引别名契约（`ParameterStore` & `GameState`）
状态访问层与表达式求值器内置以下零开销透明映射（详见 `parameters.yaml` 的 `aliases` 段）：
1. **合并与同义参数别名**：
   - `voter_cynicism` $\leftrightarrow$ `cynicism`（`D-055`，统一由 M04 主写，M03/M04 共享读写）；
   - `security_index` $\to$ `public_security`（`D-069`，供 M10 经济模块读取 M09 公众安全感，1977 开局同为 `62.0`）；
   - `country_stability[c]` $\leftrightarrow$ `regime_stability[c]`、`country_nuclear_progress[c]` $\leftrightarrow$ `enemy_nuclear_progress[c]`、`annual_immigration` $\leftrightarrow$ `immigration_inflow`（`D-068`）；
   - `country_relation[c]`（`D-068`）：自动路由至 `us_admin_relation`（当 `c == "usa"`）、`power_relation[c]`（当 `c` 属于 `powers`）或 `100.0 - regime_hostility[c]`（当 `c` 属于阿拉伯/外围中东国家）；
   - `palestinian_hostility` $\leftrightarrow$ `pal_hostility`、`intifada_risk` $\leftrightarrow$ `uprising_risk`、`islamic_assoc_strength` $\leftrightarrow$ `faction_strength[mujama]`（`D-072`）。
2. **`relation[key]` 双模解析（`D-065`）**：
   - M06 的 `relation[key]`、`health[key]`、`character_stress[key]`、`favor_character[key]` 同时接受 `CharacterId`（如 `"sharon"`）与 `OfficeId`（如 `"defense_minister"` / `"defense"`、`"pm"`）；传入职位 ID 时自动转发至当前在任人物 `holder_of(key)`，职位空缺时读取返回 `0.0`、写入作为安全空操作忽略。
3. **实体同义别名**：
   - **区域双向别名（`D-077`）**：`resolve_region_id` 支持 `north` $\leftrightarrow$ `galilee`、`central` $\leftrightarrow$ `triangle`、`south` $\leftrightarrow$ `negev`；
   - **巴勒斯坦派系别名（`D-072`）**：`notables` $\to$ `jordan_notables`、`left_factions` $\to$ `pflp`、`islamic_jihad` $\to$ `pij`；
   - **政党别名（`D-054`）**：`pm_new_party` $\to$ `new_party_a`、`alignment` $\to$ `labor`、`agudat_yisrael` $\to$ `agudat`、`hadash` $\to$ `rakah_hadash`。

---

## 3. 结算顺序（每个游戏日）

每个游戏日由 **暂停阶段 P → 每日 20 步结算 → 日终阶段** 三部分组成。每一步只能读取**上一步结束时**的状态，写入通过"效果队列"提交，在该步骤末尾统一应用。
- **周结算日固定为星期日**（`weekday == 6` / Sunday，以色列内阁例会日，`D-012`）；
- **月/季/年结算日**分别为每月 1 日、1/4/7/10 月 1 日、每年 1 月 1 日；
- **暂停阶段 P（`D-015`, `D-021`）**：玩家在暂停中做出的事件选项选择**立即应用**（使用 `events` 子流，`resolve_date` 记为当前暂停日）；玩家下达的主动行动在 P 登记，于下一结算日步骤 2 进入执行队列。

| 步骤 | 模块 | 内容与子步骤契约 | 周期 | 随机子流 |
|---|---|---|---|---|
| 1 | M01 | **推进日期与基础维护**（8个子动作：`1a` 日期与周期标记推进 $\to$ `1b` 月初 `one_off_flows` 账本轮换与 `forced_popups_month` 清零 $\to$ `1c` 年初 `era` 参数激活更新 $\to$ `1d` 到期与 `remove_if` 修正器移除 $\to$ `1e` 历史债务修正器 `strength` 更新 $\to$ `1f` 释放 `due_day == day_index` 的延迟效果与计划事件 $\to$ `1g` 周期效果生成 $\to$ `1h` 应用步骤1效果） | 每日 | `core` |
| 2 | M05 | **玩家行动入队**：应用暂停阶段下达的行动进入执行队列（每周主动槽位 2 个；部长主动提案 `MinisterProposal` 享 30% 政治资本折扣且不占槽位，`D-064`） | 每日 | `core` |
| 3 | M09 | **军事与战线日结**：每日动员水平渐进、交战战线推进与伤亡计算、防长/总参谋长越权检定（触发时发 `minister_overreach` 信号并激活 `AP04`，`D-069`）、战时财政消耗记入 `one_off_flows["budget_balance"]` | 每日 | `combat` |
| 4 | M07 | **外交与峰会日结**：多议题外交峰会推进、秘密渠道接触、国际停火施压与危机倒计时；星期三议会完成条约批准案表决后回调 `m07_ratification_result`（`D-067`） | 每日 | `world` |
| 5 | M05 | **执行中决议推进**：递减剩余天数；完成者结算效果、设置旗标 `act.<action_id>`（防事件重复结算，`D-034`）并触发 `action_completed` 钩子 | 每日 | `politics` |
| 6 | M06 | **AI 部长与人物周结**：内阁部长自主行为检定（越权、泄密、最后通牒、部门提案 `MinisterProposal`）、派系要价 | 每周（周日） | `ai` |
| 7 | M03 | **议会、民调与联盟周结**：<br>• **子步骤 `7a`（仅每月第一个星期日执行，`D-043`）**：M03 月度结算——政党生命周期检查、组阁协议条款义务检查、计算 `ally_deal_score`、通过因果网结算 `ally_satisfaction` 与 `govt_fatigue`；<br>• **子步骤 `7b`（每周日执行）**：更新 `bloc_policy_gap`、`bloc_promise_score`、通过因果网结算 `bloc_support`、生成带误差周民调 `poll_share` / `poll_seats` / `poll_lead`、推进议会排期法案表决 | 每周（周日，含月初首个周日月结） | `politics` |
| 8 | M11 / M09 / M08 | **区域安全与公众安全感周结（严格锁定子步骤顺序 `8a -> 8b`，`D-078`）**：<br>• **子步骤 `8a`（M11）**：执行 `tick_weekly_region_security` 更新各存在区域的 `region_security[r]` 与 `region_vote_share[r]`；<br>• **子步骤 `8b`（M09/M08）**：M09 读取更新后的核心区加权 `region_security`、威慑值、伤亡与导弹袭击状态（含爱国者防空减半规则，`D-071`）结算 `public_security`；M08 检定巴方武装袭击，追加 `public_security`/`deterrence` 即时冲击并发出 `sig.m08_armed_incident`（`D-075`） | 每周（周日） | `combat` |
| 9 | M10 | **财政与外汇月结**：汇总预算科目支出（含 `fiscal_spend` 乘数）、`m05_policy_fiscal_delta()` 政策持续财政成本及上月 `one_off_flows["budget_balance"]` 一次性收支（`D-010`），更新 `budget_balance`、`public_debt`、`fx_reserves`（含 `us_aid` 与 `fx_spend` 乘数，`D-061`）、`union_strength`、`strike_risk`、`absorption_capacity` | 每月（1日） | `economy` |
| 10 | M02 | **因果网与矛盾参数月结（`D-006`）**：<br>• **子步骤 `10a`**：记录全部参数与政策杠杆的月度历史快照 `hist`；<br>• **子步骤 `10b`**：结算全部模块 `thr.*` 阈值旗标的滞回状态；<br>• **子步骤 `10c`**：执行 M02 节点漂移（含挂载在节点上的 `term_provider` 动态贡献项，如 `m04_terms`、`m10_*_term`、`m11_settler_demography_term` 等，`D-052`） | 每月（1日） | `politics` |
| 11 | M04 | **党内政治、走廊与承诺月结**：计算 `gov_axis_position` 相对执政党走廊的 `stance_deviation`（含新政府前 24 个月“6个月全额豁免 + 18个月线性归零”遗产政策宽限期，`D-051`）、按本党在任部长去重人数占比计算派系内阁分肥 $ms_f$（`D-063`）、结算 `faction_mood`、`party_cohesion`、`party_standing`、`challenger_strength`、`cynicism`、`promise_credit`、更新承诺进度与到期判定、检查宏大愿景里程碑（主角离任未成即判愿景失败，`D-053`） | 每月（1日） | `politics` |
| 12 | M07 / M08 | **外部世界与巴勒斯坦月结**：<br>• **子步骤 `12a`（M07）**：推进 1977–1992 外部世界历史轨道关键帧与持久化偏差 $\Delta_{\text{perm}}$，结算 `regime_hostility`、`popular_hostility`、`regime_stability`、`country_war_readiness`、`war_probability`、`us_admin_relation`、`us_congress_relation`、`power_relation`、`intl_legitimacy`、`strategic_dependence`、`arms_reliability`、`immigration_inflow`、`enemy_nuclear_progress`；<br>• **子步骤 `12b`（M08）**：结算巴勒斯坦九大派系 `faction_strength`、`faction_legitimacy`、`faction_moderation`、`faction_cohesion`、`collaborator_stigma`、`pal_hostility`、`pal_living_standard`、`autonomy_progress`、`uprising_risk` | 每月（1日） | `world` |
| 13 | M11 | **地图与区域月结**：结算 `region_development`、`region_alienation`、`settler_population`、计算三难三角顶点数 `trilemma_jewish`、`trilemma_democratic`、`trilemma_territory` 与综合 `trilemma`（奥斯陆 A/B/C 区比例仅存于 `RegionState.oslo_shares` 内部，`D-079`） | 每月（1日） | `world` |
| 14 | M13 | **集权与宪政危机月结**：执行 `m13_monthly_tick`——结算 `centralization` 五阶段（C1–C5）、9 大阻力方姿态与反制、四级社会抗议状态机 `social_protest_tier`、`coup_risk` 与 `assassination_risk` 月度触发检定（政变检定命中直接触发 `end_tenure("coup")`，无反政变小游戏，`D-084`） | 每月（1日） | `politics` |
| 15 | M05 / M01 | **政治资本月产出与月度环形快照**：M05 计算并增加当月 `political_capital`（基线约 15、软上限 92，`D-031`）；步骤 15 结束时 M01 将可见参数快照推入容量为 12 的只读环形缓冲区 `monthly_snapshots`（支撑 UI 迷你趋势图与月变化量，`B-15-04`, `D-088`） | 每月（1日） | `politics` |
| 16 | M10 | **宏观经济季结**：结算季度 `growth`（含 M09 动员档位非线性拖累 `[0.0, -0.08, -0.25, -0.75]`，`D-070`）、`inflation`（含指数化工资-物价螺旋）、`unemployment`、`inequality` | 每季（季首1日） | `economy` |
| 17 | M10 / M06 / M11 | **年度结算**：<br>• **子步骤 `17a`（M10）**：开启新财年预算表决周期（`1977-06-20` 开局为 `PASSED`，首次强制周期于 `1978-01-01` 开启、`1978-04-01` 截止；单次未过退回 `DUE` 允许重提，满 90 天逾期未过触发议会解散，`D-061`, `D-062`）；<br>• **子步骤 `17b`（M06）**：人物年龄增长、衰老健康衰减与自然病逝检定；<br>• **子步骤 `17c`（M11）**：区域年度人口自然增长、移民安置落地与 `haredi_cohort` 更新 | 每年（1月1日） | `economy` / `ai` / `world` |
| 18 | M12 | **事件调度日结（子步骤 `18.0–18.6`，`D-025`）**：`18.0` 处理 `forced_events` $\to$ `18.1` 时代通用事件与冷却检查（`E-Gxx` 可按冷却重复，`D-020`）$\to$ `18.2` 固定历史事件窗口与条件扫描 $\to$ `18.3` 当日随机事件池掷骰 $\to$ `18.3b` 事件钩子（`trigger.hook`）处理 $\to$ `18.4` 弹窗队列排序与月度强制弹窗配额检查（月上限 3，P0 计入但不拦截，`D-024`）$\to$ `18.5` 顾问自动处理到期 `minor` 事件（默认开启，`D-023`）$\to$ `18.6` 维护 `event_engine_crisis` 旗标 | 每日 | `events` / `random_events` |
| 19 | M03 | **大选、不信任投票与组阁**：当 `pending.vote_requests` 中存在 `due_day <= day_index` 的到期请求时执行（未到期请求保留在队列中，`D-042`）；若处于 M13 `C5` 威权生存模式则冻结常规大选与不信任案（`D-083`） | 事件到期触发 | `elections` |
| 20 | M14 | **任期与终局条件检查**：每日检查硬性终局与任期结束条件；若同日存在多源 `end_tenure` 请求，严格按致命度优先级 `state_collapse > assassination > coup > death > overthrow > health_incapacity > primary_loss > no_confidence > coalition_failure > election_loss > resignation > player_quit` 保留最高优先级原因（`D-081`） | 每日 | `core` |

---

## 4. 效果（Effect）统一格式与登记总表

### 4.1 效果数据结构（`D-003`, `D-010`, `D-015`, `D-025`）

```yaml
- op: add            # add | set | mul | add_modifier | remove_modifier | set_flag | clear_flag
                     # | trigger_event | schedule_event | event_multiplier | random_branch | if
                     # | add_relation | change_seat | custom
  target: bloc_support
  key: mizrahi       # scope 非 national 时必填（支持 §2.1 别名与职位ID）
  value: -5
  # 可选通用字段
  scale: "1 - region_development[negev]/200"   # 缩放表达式；对 mul 语义为 1 + (value - 1) * scale
  delay_days: 0                                # >0 时进入 delayed_effects，释放时再求值 chance/scale
  chance: 1.0                                  # 只要字段存在即消耗 1 次当前子流随机数
  priority: 0                                  # 默认 0；owner 写入固定为 100（仅用于同日 set 冲突裁决）
  display: true                                # 是否在 UI 效果预览中展示
```

- **记忆项与持久效果契约（`D-003`, `D-006`）**：事件/行动对 `level` 节点的 `add` 效果只有 **30% 进入衰减记忆项**（$\rho = 0.30, \mu = 0.05$），每次应用后自动回调 `CausalNet.on_effect_applied(param, key, delta_actual, source_id, date)`；需要长期或永久生效的效果必须写成修正器挂边（`edges`）。owner 模块在自身结算步骤提交的 `op: set`（`priority: 100`）不进记忆项。
- **流量型参数一次性冲击（`D-010`）**：对 `budget_balance` 的非 owner `add` 效果自动记入当月 `one_off_flows["budget_balance"]` 累加器，由 M10 在步骤 9 统一计入当月支出与公共债务。
- **债务型参数减少规则（`D-015` B-8）**：`type: debt` 参数（`draft_exemption, historical_grievance, land_grievance`）的负向 `add` 仅接受玩家主动偿还行动与 owner 自身衰减计算，其余来源丢弃并记 `W_DEBT_DECREASE`。
- **专用字段约定（`D-025` B-1）**：`set_flag`/`clear_flag` 使用字段 `flag`；`add_modifier`/`remove_modifier` 使用字段 `modifier`；`trigger_event`/`schedule_event`/`event_multiplier` 使用字段 `event`（无需填 `target`）。

### 4.2 `custom` 效果处理器总登记表（M01–M14 全量汇总）

所有 `op: custom` 效果引用的处理器名必须在此表中登记，未登记名称在校验阶段报错 `E_UNKNOWN_CUSTOM`：

| 处理器名称 | 所属模块 | 参数签名（`value` / `args`） | 功能说明 |
|---|---|---|---|
| `random_branch` | M01 | `{branches: [{weight: float, effects: [Effect]}]}` | 按权重抽取单个分支并返还其效果列表（消耗 1 次随机） |
| `if_then` | M01 | `{cond: str, then: [Effect], else?: [Effect]}` | 按当前状态求值条件表达式，返回对应分支效果 |
| `add_all_keys` | M01 | `{target: str, value: float, keys?: [str], exclude?: [str]}` | 对指定 scope 参数的全部活动键（如全体犹太选民集团）批量生成 `add` |
| `schedule_event_window` | M01 | `{event: str, chance: float, min_days: int, max_days: int}` | 先掷 `chance`，命中则在 `[min_days, max_days]` 均匀抽取延迟天数计划事件 |
| `end_tenure` | M01/M14 | `{reason: str, sub_type?: str}` | 登记任期结束请求（同日多源按 D-081 致命度优先级裁决；别名 `m01_trigger_tenure_end`） |
| `m01_raise_signal` | M01 | `{signal: str, payload?: dict}` | 向信号总线或自动暂停器发出生命周期信号（含 `minister_overreach`、`ally_minister_dismissed` 等） |
| `m01_force_pause` | M01 | `{reason_zh: str}` | 在当日日终强制触发自动暂停并显示原因条 |
| `m01_set_player_party` | M01 | `{party: str}` | 修改 `player.party_id` 并发出 `party_change` 信号（供退党另组新党使用，B-10） |
| `activate_key` / `deactivate_key` | M01 | `{param: str, key: str, value?: float}` | 动态激活或停用带 scope 参数的实体键（如 1990 开放 `russian` 或政党解散） |
| `m02_add_baseline_shift` | M02 | `{param: str, key?: str, delta: float}` | 永久调整指定因果网节点的自然回归基线 |
| `m03_apply_seat_change` | M03 | `{party: str, delta: int, to_party?: str}` | 调整议会席位并维护 120 席守恒与 `coalition_seats` 重算 |
| `m03_request_vote` | M03 | `{type: "election"\|"no_confidence"\|"formation"\|"early_election", due_day?: int}` | 向 `pending.vote_requests` 追加带 `due_day` 的表决/大选/组阁请求（`D-042`） |
| `m03_submit_bill` | M03 | `{bill_uid: int, action_uid?: int, vote: "simple"\|"absolute61"\|"absolute80"\|"confidence"\|"budget", hint?: dict, deadline_day?: int}` | 提交法案进入议会星期三排期表决（含 `absolute80` 推迟大选与 `budget` 年度预算案，`D-045`, `D-061`） |
| `m03_offer` | M03 | `{party: str, offer_type: str, target?: str}` | 组阁谈判中向指定政党提出职位、政策条款或预算承诺报价 |
| `m03_form_unity_rotation` | M03 | `{partner_party: str, rotation_months: int}` | 成立民族团结轮值政府（非总理半段玩家继续操作但成本 ×1.5，`D-044`） |
| `m03_add_to_coalition` / `m03_remove_from_coalition` | M03 | `{party: str}` | 将指定政党纳入或移出当前执政联盟 |
| `m03_split_party` / `m03_found_party` / `m03_merge_parties` / `m03_dissolve_party` | M03 | `{party: str, ...}` | 政党分裂、建党、合并与解散的席位与名单重构 |
| `m03_mk_defect` | M03 | `{from_party?: str, to_party?: str, count: int}` | 单个或数个议员叛逃脱党（事件库“联合政府席位 ±n”落点） |
| `m03_set_role` / `m03_assign_portfolio` | M03 | `{party: str, portfolio?: str, role?: str}` | 调整政党在联盟中的角色或内阁部委归属 |
| `m03_delay_demand` / `m03_force_support` | M03 | `{party: str}` | 推迟盟党要价期限或运用议会党鞭强制投票支持 |
| `m03_postpone_election` | M03 | `{months: int}` | 经 80 票绝对多数通过后延长本届议会任期（`D-045`, `D-083`） |
| `m03_dissolve_knesset` | M03 | `{reason: str}` | 解散议会并排期提前大选（如预算案满 90 天逾期未过 `reason="budget_overdue"`，`D-061`） |
| `stance_shift_by_corridor` | M04 | `{axis: str, amount: float, direction?: "away"\|"toward"\|"toward_left"\|"toward_right"}` | 按走廊方向移动政府立场冲量（别名 `m04_add_stance_by_corridor`，`D-050`） |
| `m04_push_corridor` / `m04_shift_corridor` | M04 | `{axis: str, direction: str, amount: float}` | 主动推动或通过历史事件迁移本党立场走廊边界 |
| `m04_add_promise_by_tag` / `m04_set_promises` | M04 | `{tag?: str, value?: float, promises?: list}` | 按类别标签增加承诺进度或设置承诺组合 |
| `m04_party_convention` / `m04_faction_deal` | M04 | `{axis?: str, concession?: str, faction?: str}` | 召开党代会重塑走廊或与党内派系达成妥协交易 |
| `m04_faction_exit` / `m04_party_split` / `m04_found_new_party` | M04 | `{faction?: str, new_party_slot?: str}` | 派系出走、政党分裂或总理退党创立新党（写入静态槽位 `new_party_a/b/c`，`D-054`） |
| `m04_leadership_vote` / `m04_force_challenge` | M04 | `{challenger_id?: str}` | 触发或提前召开党魁信任投票/初选挑战 |
| `m04_vision_event` | M04 | `{milestone_id?: str, amount?: float}` | 触发宏大愿景里程碑事件校验 |
| `m04_open_campaign_pool` / `m04_election_settle` / `m04_activate_campaign_promises` | M04 | `{}` | 竞选期开放承诺池、大选计票前结算承诺信誉、组阁后激活新一届政府承诺 |
| `m04_finalize_promises` / `m04_reset_goals_for_leader` | M04 | `{leader_id?: str}` | 卸任时结算承诺最终兑现率、继任者就任时重置三层目标（`D-053`） |
| `m05_change_policy` | M05 | `{policy: str, to?: int, toward_ask_of?: str, steps?: int, max_steps?: int, apply_side_effects?: bool, charge_costs?: bool, skip_vote?: bool}` | 调整持续性政策杠杆档位（`D-035`） |
| `m05_grant_favor` / `m05_incur_favor` | M05 | `{entity: str, kind: "party"\|"character", n: int, due_days?: int}` | 授予或借用政党/人物人情（IOU 账本记录） |
| `m05_cancel_action` / `m05_unlock` | M05 | `{action_id: str}` | 取消正在执行的决议或解锁时代/事件专属行动 |
| `m05_bill_result` | M05 | `{bill_uid: int, passed: bool}` | 接收 M03 议会法案表决结果回调 |
| `m05_add_axis_impulse` | M05 | `{axis: str, value: float}` | 向 `gov_axis_position[axis]` 注入行动立场冲量（每月按 ×0.95 衰减） |
| `m06_appoint` / `m06_dismiss` / `m06_open_reshuffle` | M06 | `{office?: str, character?: str}` | 任命、撤换内阁部长/安全首长或打开内阁改组面板（撤换盟党部长发出 `ally_minister_dismissed`，`D-065`） |
| `m06_add_relation_cabinet` / `m06_promote_group` | M06 | `{delta?: float, group?: str}` | 批量修改全体在任内阁部长关系或提拔特定族群高官（降低 `appointment_gap`） |
| `m06_pick_successor` / `m06_rebase_relations` | M06 | `{leader_id?: str}` | 卸任时按顺位/实力选出继任者并重算人物关系基线 |
| `m06_health_check` / `m06_kill_character` / `m06_inquiry_report` | M06 | `{character?: str, threshold?: float, on_fail?: [Effect], commission_type?: str}` | 人物健康检定、人物死亡/退场处理及国家调查委员会追责裁决 |
| `m07_set_world_track` | M07 | `{track: str, value: str}` | 切换外部世界轨道状态（如美国大选政党轮替或苏联路线变更） |
| `m07_open_negotiation` / `m07_set_issue_tier` / `m07_trade_concession` / `m07_conclude_summit` | M07 | `{negotiation_id?: str, issue_id?: str, to_tier?: int, give_issue?: str, ask_type?: str, action?: "sign"\|"walk_out"}` | 启动并操作多议题外交峰会状态机（如 1978 戴维营峰会，`D-067`） |
| `m07_ratification_result` | M07 | `{bill_uid: int, passed: bool, votes_for?: int, votes_against?: int}` | 接收 M03 星期三国际条约批准案表决结果回调（`D-067`） |
| `m08_spawn_hamas` | M08 | `{}` | 激活哈马斯（`hamas`）派系并将 `mujama` 实力转入武装对抗轨道（`D-073`） |
| `m08_activate_delegation` | M08 | `{partner: str}` | 激活巴勒斯坦谈判代表团并开启自治过渡进度 |
| `m08_set_autonomy_modality` | M08 | `{modality: "none"\|"civil_admin"\|"camp_david_autonomy"\|"oslo_interim"}` | 切换西岸与加沙自治治理模式（`D-073`） |
| `m08_start_intifada` | M08 | `{intensity?: str}` | 正式触发巴勒斯坦大起义状态机并挂载全局起义修正器（`D-073`） |
| `m09_start_war` / `m09_ceasefire` | M09 | `{front: str, scope?: "limited"\|"full", authorized_max_phase?: int, security_zone?: bool}` | 启动局部/全面战争或签署停火协定（支持保留南黎安全区） |
| `m09_set_mobilization` | M09 | `{level: int\|float}` | 设定预备役动员目标档位（`0->10, 1->35, 2->65, 3->95`） |
| `m10_pass_budget` / `m10_budget_result` | M10 | `{year?: int, passed?: bool}` | 年度预算法案通过生效或接收 M03 预算表决结果回调（`D-061`） |
| `m10_set_draft_slider` / `m10_set_enacted_slider_delta` | M10 | `{item: str, value?: float, delta?: float}` | 调整预算草案滑块或直接微调已生效预算科目拨款 |
| `m10_apply_stabilization_plan` / `m10_trigger_bank_bailout` / `m10_inject_external_inflation_shock` / `m10_spawn_aliyah_cohort` | M10 | `{...}` | 执行 1985 式经济稳定计划、银行股崩盘救市接管、外部石油通胀冲击或生成大规模移民安置队列 |
| `m11_activate_region` / `m11_remove_region` | M11 | `{region: str, evacuate_settlers?: bool}` | 激活动态区（如 `south_lebanon`，别名 `m11_create_region`）或撤离归还动态区（如归还 `sinai`，`D-076`） |
| `m11_set_legal_status` | M11 | `{region: str, status: str}` | 切换区域法律地位（`"sovereign"`, `"annexed_disputed"`, `"occupied_military"`, `"occupied_civil_admin"`, `"autonomy_transitional"`, `"security_zone"`, `"returned"`，`D-076`） |
| `m11_activate_overlay` | M11 | `{plan_id: str}` | 激活或切换战略区域规划图（如 `allon_plan`, `sharon_seven_stars`，`D-076`） |
| `m13_apply_centralization_impulse` | M13 | `{delta: float, source_action_id: str}` | 注入集权行动或事件脉冲并触发阻力方反制计算（`D-085`） |
| `m14_record_turning_point` | M14 | `{title_zh: str, summary_zh?: str, weight?: float, category?: str, player_caused?: bool}` | 向任期档案登记重大历史转折点（供双页历史书总结使用，`D-081`） |
| `m14_grant_achievement` | M14 | `{id: str}` | 立即授予全局成就（`ACH_01`..`ACH_30`，`D-081`） |
| `m14_generate_fictional_leader` | M14 | `{party_id: str, template_char?: str}` | 生成虚构同党或换党继任者并写入人物库（`D-081`） |

### 4.3 修正器因子总登记表（`KNOWN_MODIFIER_FACTORS`）

各模块通过 `factor(key, scope_key="")` 读取生效修正器对流量或成本的乘数/加值。全局合法的因子键如下（`D-015`, `D-045`, `D-061`）：

| 因子键（`key`） | 默认乘数 | 作用域（`scope_key`） | 读取模块与用途说明 |
|---|---|---|---|
| `pc_income` | `1.0` | `""`（全国） | **M05**：政治资本月产出乘数与平铺加值（步骤 15） |
| `pc_cost` | `1.0` | `""` 或行动标签/类别 | **M05**：行动政治资本消耗乘数（如看守内阁 `caretaker` ×1.3、轮值副总理期间 ×1.5，`D-044`） |
| `covert_cost` | `1.0` | `""`（全国） | **M05 / M07 / M09**：秘密外交与摩萨德/辛贝特秘密行动成本乘数 |
| `oratory_effect` | `1.0` | `""`（全国） | **M03 / M04 / M05**：公开演说与竞选集会效果乘数（如 `silent_pm` 期间大幅降低） |
| `swing_sensitivity` | `1.0` | `bloc`（选民集团ID） | **M03**：选民集团支持度对短期利好/利空的摆动敏感度（B-6） |
| `vote_attraction` | `1.0` | `party`（政党ID） | **M03**：政党在民调与大选计票中的选票吸引力乘数（B-6） |
| `fiscal_spend` | `1.0` | `""` 或 `budget_item` | **M10**：财政支出乘数（如战时或紧急救灾支出膨胀，`D-061`） |
| `fx_spend` | `1.0` | `""`（全国） | **M10**：外汇储备月度消耗乘数（如战时军火进口或贷款冻结，`D-061`） |
| `us_aid` | `1.0` | `""`（全国） | **M10 / M07**：美国对以财政与外汇援助乘数（如埃以和约加成或 1991 贷款担保冻结，`D-061`） |

---

## 5. 条件与表达式语言

触发条件、概率修正、效果缩放、结局与成就判定统一使用确定性表达式 DSL（完整词法与语法见 `M12_event_engine.md` §4.4）：

```
alienation[mizrahi] >= 40 and region_development[haifa] < 30
flag("settlers_momentum_high") or months_since(event("E-1977-11")) > 6
0.25 * (1 + (60 - regime_hostility[egypt]) / 100)
```

### 5.1 内置变量与基础运算
- **内置只读变量**：`year`（当前年份）、`month`（1–12）、`day`（1–31）、`k`（随机事件规模系数）、`leader_id`（当前总理人物ID）、`party_id`（当前执政党ID）、`end_reason`（仅卸任结算上下文可用）。
- **运算符**：算术 `+ - * /`（除数为 0 返回 `0.0` 并记 `E_DIV0`）、比较 `< <= > >= == !=`（支持数字、字符串与布尔值）、逻辑 `and or not`（短路求值）、成员判断 `in` / `not in`。

### 5.2 内置只读查询函数总表（M01–M14 全量汇总）

| 函数签名 | 返回类型 | 提供模块 | 语义说明 |
|---|---|---|---|
| `min(a, b, ...)` / `max(a, b, ...)` | `float` | M12 | 多参数最小值 / 最大值 |
| `clamp(x, lo, hi)` | `float` | M12 | 将 `x` 夹紧在 `[lo, hi]` 区间内 |
| `floor(x)` / `abs(x)` | `float` | M12 | 向负无穷取整 / 绝对值 |
| `flag(s)` | `bool` | M01/M12 | 旗标 `s` 当前是否处于激活状态（含 `thr.*`、`act.*`、世界旗标） |
| `has_modifier(s)` / `has_modifier(s, key)` | `bool` | M01/M12 | 修正器 `s`（及可选 `scope_key`）当前是否存续 |
| `event_done(s)` | `bool` | M12 | 事件 `s` 在本局中是否至少已结算（`RESOLVED`）过一次 |
| `event(s)` | `int` | M12 | 事件 `s` 最近一次结算日的 `day_index`（从未发生返回 `-1`） |
| `event_choice(s)` | `str` | M12 | 事件 `s` 最近一次结算时玩家选择的选项 ID（未发生或被动事件返回 `""`） |
| `months_since(d)` / `days_since(d)` | `int` | M01/M12 | 距离日序号 `d` 的完整月数 / 天数（`d == -1` 时分别返回 `9999` / `999999`） |
| `scenario()` | `str` | M01/M14 | 当前剧本 ID（如 `"begin_1977"`） |
| `era()` | `int` | M01/M12 | 当前时代编号（`1`: ≤1955, `2`: 1956–1967.6, `3`: 1967.6–1977.6, `4`: 1977.6–1992.7, `5`: ≥1992.7） |
| `repeat_count(s)` | `int` | M12 | 事件 `s` 在当前任期内的已触发次数 |
| `slot(s)` / `arg(s)` | `str` | M12/M05 | 当前事件实例槽位 `s` 或行动实例参数 `s` 绑定的实体 ID |
| `term_months()` | `int` | M03 | 当前这届政府自宣誓就职日以来的完整月数 |
| `days_to_election()` | `int` | M03 | 距离法定下一届大选日的天数 |
| `party_seats(party_id)` | `int` | M03 | 返回指定政党当前议会席位数（等价于 `knesset_seats[party_id]`） |
| `party_in_coalition(party_id)` | `bool` | M03 | 指定政党当前是否属于执政联盟成员 |
| `party_has_tag(party_id, tag)` | `bool` | M03 | 指定政党是否带有标签 `tag`（如 `"haredi"`, `"religious"`, `"arab"`, `"left"`, `"right"`） |
| `party_stage()` | `int` | M04 | 当前执政党内部危机升级阶段（`0..4`，0=稳定，4=公开逼宫/分裂） |
| `promise_active(promise_id)` | `bool` | M04 | 指定承诺当前是否处于生效追踪期 |
| `vision_milestone_done(milestone_id)` | `bool` | M04 | 当前剧本宏大愿景的指定里程碑是否已达成 |
| `corridor_lo(axis)` / `corridor_hi(axis)` | `float` | M04 | 当前执政党在指定立场轴 `axis` 上的走廊下界 / 上界（绝对刻度 `[-100, 100]`，`D-033`） |
| `m05_iou_total()` | `int` | M05 | 当前总理欠出未还的政党与人物人情（IOU）总数 |
| `action_running(action_id)` | `bool` | M05 | 指定行动当前是否有处于排队、执行中或立法表决中的实例 |
| `action_done_count(action_id)` | `int` | M05 | 指定行动在本局/本任期内已成功完成的次数 |
| `character_in_office(id_or_post)` | `bool` | M06 | 若传人物ID则返回是否任职且在世；若传职位ID则返回该职位当前是否非空（`D-065`） |
| `character_alive(char_id)` | `bool` | M06 | 指定人物当前是否在世 |
| `holder_of(office_id)` | `str` | M06 | 返回当前担任 `office_id`（含部委、安全首长、政党/派系领袖、外国元首）的人物 ID，空缺返回 `""` |
| `ambition(char_id)` | `float` | M06 | 返回指定人物的野心属性 `[0, 100]` |
| `peace_treaty(country_id)` | `bool` | M07 | 返回与指定国家的 `peace_treaty_state[country_id] >= 2`（已签框架或正式和约，`D-067`） |
| `treaty_tier(country_id)` | `int` | M07 | 返回与指定国家的条约等级 `0..3`（0=敌对, 1=停火, 2=框架, 3=正式和约，`D-067`） |
| `secret_channel(country_id)` | `bool` | M07 | 返回是否已对该国建立秘密外交渠道（`D-067`） |
| `nuclear_progress(country_id)` | `float` | M07 | 返回指定敌国（`iraq` 或 `iran`）的核计划进度 `enemy_nuclear_progress[country_id]`（`D-067`） |
| `at_war()` / `at_war(front_or_country)` | `bool` | M09/M07 | 任一战线（或指定战线/国家）当前是否处于全面交战状态 |
| `last_ceasefire_date()` | `int` | M09 | 距离最近一次全面战争停火的天数 |
| `front_phase(front_id)` | `int` | M09 | 返回指定战线当前作战阶段 `0..3`（0=无战事，`D-069`） |
| `casualties_total(front_id="")` | `int` | M09 | 返回指定战线（空字符串为全部战线）当前战争以军累计阵亡人数（`D-069`） |
| `region_exists(region_id)` | `bool` | M11 | 返回指定区域当前是否处于以方实际控制/存在状态（固定 6 区恒为 `true`，动态 5 区随占领/撤离变化） |
| `legal_status(region_id)` | `str` | M11 | 返回区域当前法律地位字符串（别名 `region_legal_status(region_id)`，`D-076`） |
| `site_status(site_id)` | `str` | M11 | 返回关键地点当前状态（`"active"\|"under_construction"\|"evacuated"\|"inactive"`，`D-076`） |
| `settler_pop(region_id)` | `int` | M11 | 返回指定区域当前犹太定居者人数（不存在时为 `0`，`D-076`） |
| `active_plan()` | `str` | M11 | 返回当前激活的战略区域规划图 ID（无激活时为 `""`，`D-076`） |
| `m13_stage()` | `str` | M13 | 返回当前集权五阶段标识（`"C1"`..`"C5"`，`D-085`） |
| `m13_actor_posture(actor_id)` | `str` | M13 | 返回九大阻力方之一的当前姿态（`"compliant"\|"warning"\|"defiance"\|"crisis"`，`D-085`） |
| `m13_protest_tier()` | `int` | M13 | 返回全国宪政抗议与罢工拒服等级 `0..3`（等价于 `social_protest_tier`，`D-085`） |
| `m13_in_survival_mode()` | `bool` | M13 | 返回当前是否处于 C5 威权生存模式（`D-083`, `D-085`） |
| `tenure_months()` / `tenure_index()` | `int` | M14 | 返回当前总理在任完整月数 / 当前是第几任可玩总理（0 为开局主角，`D-081`） |
| `count_peace_treaties()` | `int` | M14 | 返回 `egypt, jordan, syria, lebanon, saudi` 中 `peace_treaty_state == 3` 的国家数量（`D-081`） |
| `settler_population_total()` | `int` | M14 | 返回动态占领区与东耶路撒冷新社区犹太定居者总人数（`D-081`） |
| `casualties_total_all_fronts()` | `int` | M14 | 返回本任期所有战线累计阵亡总人数（`D-081`） |
| `front_quagmire_months(front_id)` | `int` | M14 | 返回指定战线陷入占领泥潭（`OCCUPATION_QUAGMIRE`）的累计月数（`D-081`） |
| `region_pop_group_total(group_id)` | `int` | M14/M11 | 返回指定人口群体（如 `"russian"`）在全国各区域的总人口数（`D-081`） |

---

## 6. 模块读写矩阵与跨模块查询契约

### 6.1 模块主写参数矩阵（`owner`）

**增量写入原则（`D-015` B-4）**：只有 `owner` 模块可以在其结算步骤中以 `op: set`（`priority: 100`）直接写入参数（且不进入冲击记忆项，`D-006` B7）；非 `derived` 参数的 `owner` 必须基于“上一步末当前值 + 本期增量”计算新值，不得抹除其他模块通过效果队列施加的 `add` 冲击。

| 模块 | 主写参数（`owner`，共 110 项） | 主要读取与联动接口 |
|---|---|---|
| **M02** | `religious_status_quo, draft_exemption, alienation, historical_grievance, civic_identification, land_grievance, settler_momentum, rule_of_law, judicial_conflict`（9项） | 读取全部参数与杠杆；维护 `CausalNet`、`thr.*` 阈值滞回与 `get_parameter_history_12m`（`B-15-01`） |
| **M03** | `ally_satisfaction, bloc_support, coalition_seats, region_vote_share, knesset_seats, poll_share, poll_seats, poll_lead, months_to_election, govt_fatigue, bloc_policy_gap, bloc_promise_score, ally_deal_score, seat_expectation_bonus`（14项） | 读取矛盾参数、经济、安全、走廊与承诺；处理法案表决、大选与组阁 |
| **M04** | `party_standing, promise_progress, stance_deviation, vision_progress, faction_mood, faction_weight, party_cohesion, challenger_strength, cynicism, promise_credit`（10项） | 读取 `gov_axis_position`、内阁派系分肥、行动与事件历史；提供 `m04_terms` |
| **M05** | `political_capital, policy_level, gov_axis_position, favor_party, favor_character, exemption_coverage, outpost_enforcement`（7项） | 读取党内地位、选民支持、议会席位、修正器因子；提供 `m05_policy_fiscal_delta()` |
| **M06** | `relation, health, character_stress, appointment_gap`（4项） | 读取行动、事件、战时伤亡、派系情绪；提供内阁名单与继任者推选 |
| **M07** | `strategic_dependence, intl_legitimacy, us_admin_relation, us_congress_relation, power_relation, regime_hostility, popular_hostility, regime_stability, country_war_readiness, peace_treaty_state, war_probability, immigration_inflow, arms_reliability, enemy_nuclear_progress`（14项） | 读取军事行动、定居点、外交峰会；维护 1977–1992 世界轨道与 $\Delta_{\text{perm}}$ |
| **M08** | `pal_hostility, pal_living_standard, faction_strength, faction_legitimacy, faction_moderation, faction_cohesion, collaborator_stigma, autonomy_progress, uprising_risk, islamic_assoc_strength`（10项） | 读取占领区政策、定居点动量、军事镇压与外交进展 |
| **M09** | `readiness, mobilization, public_security, deterrence, complacency, nuclear_progress, nuclear_exposure_risk, state_integration, intel_accuracy`（9项） | 读取国防预算、武器可靠度、区域安全、在任安全首长属性 |
| **M10** | `budget_balance, public_debt, fx_reserves, inflation, growth, unemployment, absorption_capacity, economic_model, inequality, union_strength, budget_slider, strike_risk`（12项） | 读取预算滑块、政策成本、战时消耗、美援乘数、动员水平与治安 |
| **M11** | `trilemma, trilemma_jewish, trilemma_democratic, trilemma_territory, region_security, region_development, region_population, settlement_policy, region_land_policy, military_government, haredi_cohort, region_absorption_priority, region_investment_priority, region_security_posture, settler_population, region_alienation`（16项） | 读取预算拨款、移民流入、定居点与安全政策；提供 `resolve_region_id` 与 `m11_settler_demography_term` |
| **M12** | 无（只通过效果解释器执行效果） | 读取全部状态与表达式函数；提供 `preview_option_ui_metadata`（`B-15-02`） |
| **M13** | `centralization, coup_risk, assassination_risk, social_protest_tier`（4项） | 读取民主法治、工会实力、安全首长关系與紧急行动 |
| **M14** | `historical_rating`（1项） | 读取全部状态、历史序列与事件日志；结算 40 结局、八维评价、三大史派与 30 成就 |
| **M15** | 无（纯表现与交互层，`UIState` 与 `UserSettings` 严格与模拟态解耦，`D-086`） | 只读查询模拟态、`explain` Top-5 贡献边、`monthly_snapshots`（`B-15-04`）与 `ai_reason_breakdown`（`B-15-03`） |

### 6.2 界面与表现层只读查询契约（M15，`D-086`–`D-088`）
1. **`get_parameter_history_12m(param_id: str, key: str = "national") -> List[float]`（`B-15-01`）**：由 M01/M02 从 `monthly_snapshots` 环形缓冲区返回最近 12 个结算月的历史值，供因果 Tooltip 绘制迷你折线图。
2. **`preview_option_ui_metadata(event_id: str, option_idx: int) -> OptionUIPreview`（`B-15-02`）**：由 M12 返回确定性效果定性预览、触及的三层目标徽章，以及事前暴行/失控风险的四档定性警告（自动剥离后续被动事件 ID 以防剧透）。
3. **`ai_reason_breakdown` 透明化载荷（`B-15-03`）**：M03/M06/M07/M08 在触发 AI 行动信号或事件时附带 `{actor_id, primary_param_id, current_val, threshold_val, top_factors}`，确保 UI 100% 透明展示 AI 行动理由。
4. **总账本战争迷雾一致性（`D-088`）**：对 `visible: fuzzy` 参数，国家总账本（Ledger）按模糊估算区间中心值排序，单元格仅展示五档定性词与估算区间（如 `严峻 (65%–85%)`），绝不向客户端 UI 泄露底层精确浮点数。

---

## 7. 规格完成的判定（Definition of Done）

一份模块规格只有同时满足以下条件才算完成：
1. 使用 [spec_template.md](spec_template.md) 的全部章节（0–13 章齐全）。
2. 所有参数都来自 [registry/parameters.yaml](registry/parameters.yaml)；所有跨模块接口与 `custom` 处理器均在本文件中登记。
3. 每个公式都有初始系数、单位和一个可复算算例。
4. 至少 8 条**可自动判定**的验收测试（输入状态 → 期望输出）。
5. 通过 `.venv/bin/python tools/check_specs.py` 自动化校验且无未登记引用。
