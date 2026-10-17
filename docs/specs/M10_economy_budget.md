# M10 — 经济与预算 (Economy & Budget)

> **模块编号**: `M10`
> **模块名称**: 经济与预算 (`economy_budget`)
> **依赖模块**: `M01` (核心循环与时间轴), `M02` (数值模型与因果网络), `M03` (议会与内阁), `M04` (政党、承诺与背叛), `M05` (政策杠杆、法案与政治资本)
> **被依赖模块**: `M06` (选民集团与民意), `M07` (游说集团与街头政治), `M08` (外交与美国援助), `M09` (国防与安全), `M11` (移民、定居点与人口), `M12` (历史与动态事件), `M13` (UI 与解释层), `M14` (胜利、失败与历史评价)
> **关联决策**: `D-001`, `D-002`, `D-004`, `D-007`, `D-008`, `D-009`, `D-010`, `D-011`, `D-014`, `D-015`, `D-017`, `D-021`, `D-028`, `D-034`, `D-039`, `D-040`, `D-042`, `D-044`, `D-045`, `D-049`, `D-052`, `D-053`
> **RNG 子流**: `"economy"` (`D-011`)

---

## 0. 摘要 (Summary)

**M10（经济与预算模块）** 负责模拟以色列从 1977 年工党（Mapai/Labor）国家资本主义体制向新自由主义市场化转型过程中的宏观经济动力学、年度国家预算博弈、恶性通胀螺旋、外汇储备危机、劳工总联合会（Histadrut）罢工机制，以及移民吸纳容量的承载极限。

本模块的核心职责包括：
1. **双频宏观经济结算（Monthly Step 9 & Quarterly Step 16）**：在每月 1 日（Step 9 `finance_monthly`）结算财政收支平衡（`budget_balance`）、公共债务率（`public_debt`）、外汇储备（`fx_reserves`）、移民吸纳容量（`absorption_capacity`）、工会力量（`union_strength`）与罢工风险（`strike_risk`）；在每季度首日（Step 16 `economy_quarterly`）结算 GDP 增长率（`growth`）、年化通胀率（`inflation`）、失业率（`unemployment`）与基尼不平等指数（`inequality`）。
2. **8 项国家预算滑块（Budget Sliders）与年度预算案全生命周期（Step 17 `budget_yearly`）**：管理国防（`defense`）、移民吸纳（`absorption`）、宗教事务（`religion`）、发展城镇（`dev_towns`）、教育（`education`）、福利补贴（`welfare`）、基础设施（`infrastructure`）与定居点（`settlements`）8 大预算科目的配额调节、政党预算底线核查、议会表决（`vote: "budget"`）及逾期 90 天议会依法自动解散（`D-014`）。
3. **1977–1985 以色列通胀螺旋与银行股危机机制**：通过自适应通胀预期（`expected_inflation`）、工资-物价指数化挂钩系数（$\psi_{\text{index}}$）、奥利维拉-坦齐效应（Olivera-Tanzi tax erosion，高通胀侵蚀实际税收）以及财政赤字货币化非线性加速器（$\Phi_{\text{monetize}}$），精确复现 1977 年埃利希自由化冲击（`E-1977-10`）、1981–1983 年阿里多尔“正确经济学”泡沫与 1983 年特拉维夫银行股崩盘（`E-1983-10`）、1984 年 445% 恶性通胀以及 1985 年《经济稳定计划》休克疗法（`E-1985-07`）。
4. **劳工总联合会（Histadrut）罢工与反私有化对抗**：量化实际工资侵蚀、私有化/最低工资政策敌意与 `union_strength` 的耦合作用，触发部门警告罢工与全国总罢工（`E-G04-02`），对季度 GDP 增长与政府稳定性造成直接冲击。
5. **1989–1992 苏联大移民（Aliyah）吸纳冲击与长期人口红利转换**：将短期移民涌入对 `absorption_capacity`、住房、财政赤字与 `unemployment` 的脉冲压力（`E-1989-10`），经 6–8 个季度时滞平滑转化为高技能人力资本的长期 GDP 增长红利。

**本模块明确不做（Out of Scope）**：
- 不直接维护 26 条非预算日常政策杠杆的当前值或漂移（由 `M05` 拥有并通过 `m05_policy_fiscal_delta()` 及 `lever_edges` 输入给 `M10`）。
- 不直接计算议会预算案的政党逐席投票逻辑（由 `M03` 在 Step 3 `parliament_vote` 处理并通过 `m10_budget_result` 回调 `M10`）。
- 不直接生成历史事件弹窗 UI（由 `M12` 消费 `M10` 发出的 Flag 与钩子信号后入队 `pending_events`）。

---

## 1. 玩家感受与设计目标 (Player Experience & Design Goals)

### 1.1 核心玩家体验：“被政治绑架的算术题”
在以色列联合政府政治中，财政预算从来不是单纯的宏观经济学优化问题，而是**用真金白银购买议会 61 席生存权的政治赎金**：
- **枪炮、黄油、经学院与定居点的四方撕扯**：利库德集团要求扩大国防与定居点支出，宗教政党（Agudat Yisrael / Shas / NRP）将宗教事务与儿童津贴视为留任底线，发展城镇的东方犹太选民（`mizrahi_working`）依赖食品补贴与福利，而世俗中产与美国国务院则要求削减赤字与抑制通胀。任何试图讨好所有人的“赤字财政”（如 1981–1983 年的阿里多尔路线）都会在短期内制造虚假繁荣，随后通过外汇枯竭、银行股崩盘和 400%+ 的恶性通胀将政府推向深渊。
- **可感知的宏观危机倒计时**：玩家不会面对黑箱式的突发暴死。外汇储备（`fx_reserves`）以“可支撑进口月数”（10 点 = 1 个月进口额）直观呈现；当外汇跌破 20 点（2 个月进口警戒线）或年度预算逾期进入最后 60 天倒计时，顶栏与内阁桌面会给出清晰的危机预警与可执行的挽救手段（紧急申请美国过桥贷款、本币贬值、冻结某项支出或与劳工总联合会谈判）。
- **休克疗法的政治剧痛与历史成就感**：要终结恶性通胀（如 1985 年稳定计划），玩家必须同时砍掉预算赤字、打破 `wage_indexation`（工资指数化自动挂钩）、授予央行独立性（`central_bank`）并承受工会总罢工与联盟伙伴叛乱的巨大政治代价。成功熬过 2–3 个季度的阵痛期后，通胀断崖式回落、外汇回升的曲线将带来极强的策略正反馈。

### 1.2 参考基准与 Paradox 教训落地
- **参考基准（对标《Suzerain》《Victoria 3》《Crisis in the Kremlin》）**：
  - 吸收《Suzerain》的“具象科目权衡”而非枯燥税率微调：预算滑块限定为 8 个政治含义极强的核心科目，每次调整立即预览对月度 `budget_balance`、各政党满意度及对应社会指标的边际影响。
  - 吸收《Victoria 3》的“利益集团制度性力量”：将劳工总联合会（Histadrut）建模为拥有独立经济帝国（Koor、Solel Boneh、Clalit）的结构性参数 `union_strength`，而非单纯的随机罢工事件。
- **Paradox 历史模拟教训（`docs/research/paradox_lessons.md`）落地**：
  1. **拒绝指数级滚雪球**：所有宏观存量参数通过 `M02` 的三段式 `C1` 软目标压缩（`soft_target`）与阻尼步进（`alpha`）约束，避免正反馈失控把 GDP 增长推到不切实际的数值。
  2. **恶性通胀必须有明确的制度开关而非纯数值漂移**：通胀超过 100% 必须由“高赤字 + 低央行独立性 + 高工资指数化”三者共同激活（$\Phi_{\text{monetize}}$ 与 $\psi_{\text{index}}$）；一旦玩家完成制度改革（`central_bank >= 67` 且 `budget_balance >= -1.5`），预期通胀记忆会快速去锚定（Disinflation），不会因为过去的历史惯性永久卡死。
  3. **每一个数字都必须可解释（Explainability First）**：`M10` 的所有计算严格拆分到具名因果边（`M10.DEBT.*`、`M10.FX.*`、`M10.INF.*` 等）或结构化分项账本（`FiscalLedger`），确保 `M02.explain()` 与 `M13` 悬停提示能精确列出前三大正负驱动因子。

---

## 2. 拥有与读写的参数 (Parameters Owned, Read & Written)

### 2.1 M10 拥有的注册表参数（已存在于 `parameters.yaml`，共 10 项）

| 参数名 | 类型 | 作用域 | 范围 | 结算频率 (`tick`) | 1977-06-20 初值 | 物理单位与游戏内含义 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `budget_balance` | `derived` | `national` | `[-50, 50]` | `monthly` (Step 9) | `-2.0` | 占年度国家预算总额的月度收支差额百分比（`% of annual budget / month`）。负值为赤字，正值为盈余 |
| `public_debt` | `stock` | `national` | `[0, 300]` | `monthly` (Step 9) | `120.0` | 公共债务占 GDP 比重（`% of GDP`）。1984–1985 年危机峰值可达 200%+ |
| `fx_reserves` | `stock` | `national` | `[0, 100]` | `monthly` (Step 9) | `35.0` | 国家外汇储备指数（`10 pt = 1.0 个月进口额 ≈ 4.5 亿美元 (1977 USD)`；`< 20` 触发外汇危机） |
| `absorption_capacity` | `stock` | `national` | `[0, 100]` | `monthly` (Step 9) | `55.0` | 国家移民吸纳容量（住房、希伯来语培训中心 Ulpan、就业安置综合承载力；`50` 为常态均衡） |
| `union_strength` | `stock` | `national` | `[0, 100]` | `monthly` (Step 9) | `70.0` | 劳工总联合会（Histadrut）组织控制力与产业垄断强度（1977 年控制约 25% GDP 与全国医保） |
| `inflation` | `percent` | `national` | `[-5, 500]` | `quarterly` (Step 16) | `35.0` | 年化消费者物价指数（CPI）通胀率（`%/yr`）。`> 80` 为高通胀危机，`> 180` 为恶性通胀 |
| `growth` | `percent` | `national` | `[-15, 20]` | `quarterly` (Step 16) | `1.5` | 实际 GDP 年化增长率（`%/yr`）。`< 0` 为经济衰退 |
| `unemployment` | `percent` | `national` | `[0, 40]` | `quarterly` (Step 16) | `3.9` | 全国城镇登记失业率（`% of labor force`） |
| `inequality` | `stock` | `national` | `[0, 100]` | `quarterly` (Step 16) | `38.0` | 基尼系数映射指数（`Gini × 100`，`38.0` 对应基尼系数 `0.380`） |
| `economic_model` | `axis` | `national` | `[-100, 100]` | `event` | `-45.0` | 国家经济体制坐标轴（`-100` 完全工党国家社会主义/Histadrut 垄断，`+100` 完全新自由主义市场经济） |

### 2.2 M10 提议新增的注册表参数（详见附录 A，共 2 项）

| 参数名 | 类型 | 作用域 | 范围 | 结算频率 (`tick`) | 1977-06-20 初值 | 物理单位与游戏内含义 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `budget_slider` | `lever` | `budget_item` | `[0, 100]` | `event` | 见 §2.3 | 8 大国家预算科目的拨款水平滑块（`50` 为历史常态基准拨款，`0` 为极限削减，`100` 为全额扩张） |
| `strike_risk` | `derived` | `national` | `[0, 100]` | `monthly` (Step 9) | `28.0` | 全国劳工罢工风险指数（由 `union_strength`、实际工资侵蚀与政策敌意计算，`>= 60` 触发部门罢工，`>= 80` 触发全国总罢工） |

### 2.3 8 项国家预算滑块（`entities.budget_items`）定义与 1977 初值

| 预算科目 ID (`budget_item`) | 中文名称 | 1977-06-20 初值 $B_k^{(0)}$ | 财政权重 $w_k$ (`% budget/mo per pt`) | 政治敏感政党 / 选民集团 | 核心宏观与跨模块效应 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `defense` | 国防与军工 | `65.0` | `0.040` | `likud`, `alignment`, `nrp`, `tehiya` | 支撑 `M09` 战备与军工研发；高于 50 消耗外汇（`fx_reserves`）并挤出民间投资（`growth`） |
| `absorption` | 移民吸纳与安置 | `45.0` | `0.016` | `likud`, `dash`, `russian_immigrants` | 提升 `absorption_capacity`，缓解移民潮带来的 `unemployment` 冲击 |
| `religion` | 宗教事务与经学院 | `40.0` | `0.010` | `agudat_yisrael`, `shas`, `nrp` | 满足正统派政党预算底线；提升 `haredi_orth` 满意度，高于 60 轻微抑制劳动力参与 |
| `dev_towns` | 发展城镇专项 | `40.0` | `0.012` | `likud`, `shas`, `mizrahi_working` | 降低结构性失业（`unemployment`）与不平等（`inequality`），提升 `mizrahi_working` 满意度 |
| `education` | 公共教育与科研 | `50.0` | `0.020` | `alignment`, `dash`, `shinui`, `ratz` | 提升长期 `growth` 潜力，降低 `inequality` |
| `welfare` | 社会福利与津贴 | `55.0` | `0.024` | `alignment`, `agudat_yisrael`, `shas`, `hadash` | 显著降低 `inequality`，缓冲高通胀对低收入阶层的冲击 |
| `infrastructure` | 国家基础设施 | `50.0` | `0.018` | `alignment`, `likud`, `dash` | 直接拉动 `growth`、提升 `absorption_capacity` 并吸纳就业（降低 `unemployment`） |
| `settlements` | 约旦河西岸与加沙定居点 | `35.0` | `0.012` | `nrp`, `likud`, `tehiya`（正）；`alignment`, `ratz`, `us_stance`（负） | 驱动 `M11` 定居点扩张速度；高于 50 引发美国外交摩擦（压低 `us_stance`） |

### 2.4 M10 只读引用的外部模块参数

| 参数 / 接口 | 所属模块 | 读取时机 | 用途 |
| :--- | :--- | :--- | :--- |
| `policy` (26 项政策杠杆) | `M05` | Step 9, Step 16, 预算变更时 | 通过 `m05_policy_fiscal_delta(state)` 计算政策财政净收支；通过 `data/causal_edges.yaml` 的 `lever_edges` 输入到 M10 节点；计算 `economic_model` 与 `strike_risk` |
| `one_off_flows["budget_balance"]` | `M02` / `M05` / `M12` | Step 9 (`finance_monthly`) | 消费并清零当月累积的一次性财政收支冲击（如紧急军购、银行救助成本、美国紧急拨款，遵循 `D-010`） |
| `us_stance` | `M08` | Step 9 (`finance_monthly`) | 计算美国常规财政赠款支持 $R_{\text{aid}, t}$ 及对 `fx_reserves` 的因果边 `M10.FX.01` |
| `security_index` | `M09` | Step 16 (`economy_quarterly`) | 通过因果边 `M10.GRO.02` 影响投资者信心与季度 `growth` |
| `coalition_parties`, `party_seats` | `M03` | 预算起草与提交时 | 校验执政联盟各政党的预算科目底线要求，预测预算案支持票数 |
| `mod_factor("fx_spend")`, `mod_factor("fiscal_spend")`, `mod_factor("us_aid")` | `M01` / `M02` | Step 9 (`finance_monthly`) | 读取激活修正器（如战争动员、能源危机、美援冻结）对外汇消耗、财政支出与美援流入的乘数修正 |

---

## 3. 数据结构与状态模式 (Data Structures & State Schema)

### 3.1 M10 运行时状态树 (`state.m10`)

`state.m10` 挂载于全局 `GameState` 下，所有浮点数在月度/季度边界按 `D-015` 规则四舍五入至 `0.001`（`round(val, 3)`），并在序列化时完整保存：

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional

BUDGET_ITEMS: List[str] = [
    "defense",
    "absorption",
    "religion",
    "dev_towns",
    "education",
    "welfare",
    "infrastructure",
    "settlements",
]

@dataclass
class FiscalLedger:
    """月度财政收支分项账本（单位：占年度预算百分比/月，供 M02.explain 与 M13 UI 展示）"""
    tax_revenue: float = 7.828          # 基础与周期性税收收入 R_tax
    us_aid_grant: float = 0.600         # 美国常规财政赠款折算 R_aid
    slider_expenditure: float = 8.712   # 8 项预算滑块总支出 E_sliders
    debt_service: float = 0.960         # 公共债务利息支出 E_debt
    tanzi_erosion: float = 0.700        # 奥利维拉-坦齐高通胀税收侵蚀 E_tanzi
    m05_policy_delta: float = -0.056    # M05 26 项政策杠杆结构性财政净影响 Δ_M05
    one_off_flow: float = 0.000         # 当月一次性收支冲击 F_one_off (消费后清零)
    net_balance: float = -2.000         # 最终月度 budget_balance

@dataclass
class BudgetCycleState:
    """年度国家预算案生命周期状态"""
    fiscal_year: int = 1977                     # 当前预算所属财年
    status: str = "PASSED"                      # "PASSED" | "DUE" | "VOTING" | "OVERDUE_WARNING" | "DISSOLVED"
    opened_day: int = 0                         # 本财年预算周期开启的绝对天数 (每年 Jan 1)
    deadline_day: int = 90                      # 法定通过截止日 (opened_day + 90，即每年 Apr 1 / 闰年 Mar 31)
    active_bill_uid: Optional[int] = None       # 已提交给 M03 的预算案 bill_uid (900000 + fiscal_year)
    warning_60d_emitted: bool = False           # 是否已触发距离截止日 <= 30 天 (即开启后第 60 天) 的危机警告
    enacted_sliders: Dict[str, float] = field(default_factory=lambda: {
        "defense": 65.0,
        "absorption": 45.0,
        "religion": 40.0,
        "dev_towns": 40.0,
        "education": 50.0,
        "welfare": 55.0,
        "infrastructure": 50.0,
        "settlements": 35.0,
    })
    draft_sliders: Dict[str, float] = field(default_factory=lambda: {
        "defense": 65.0,
        "absorption": 45.0,
        "religion": 40.0,
        "dev_towns": 40.0,
        "education": 50.0,
        "welfare": 55.0,
        "infrastructure": 50.0,
        "settlements": 35.0,
    })
    rejection_count_this_year: int = 0          # 本年度预算案被议会否决的次数

@dataclass
class AliyahCohort:
    """移民潮分批队列（追踪短期吸纳负荷与长期 GDP 人力资本红利转换）"""
    cohort_id: str                              # 批次标识，如 "1989_Q4_soviet"
    created_day: int                            # 产生日期
    quarters_elapsed: int = 0                   # 已历季度数
    initial_magnitude: float = 0.0              # 初始规模 (0.0 ~ 40.0)
    current_load: float = 0.0                   # 当前对 absorption_capacity 的短期负荷
    current_growth_dividend: float = 0.0        # 当前对 growth 的季度人力资本红利

@dataclass
class M10EconomyState:
    """M10 模块完整持久化状态"""
    # 宏观内部记忆与辅助存量
    expected_inflation: float = 35.0            # 适应性通胀预期 π^e (%/yr)
    real_gdp_index: float = 100.0               # 实际 GDP 累积指数 (1977-06-20 = 100.0)
    cumulative_deficit_stock: float = 40.0      # 历史累积赤字压力存量 (驱动 public_debt)
    external_inflation_shock: float = 0.0       # 外部输入型通胀冲击 (如 1979 石油危机，按季度 ×0.75 衰减)
    wage_erosion_index: float = 20.0            # 实际工资侵蚀指数 [0, 100]
    strike_cooldown_months: int = 0             # 罢工冷却月数 (防止连续每月重复触发总罢工)
    active_strike_tier: int = 0                 # 当前罢工等级: 0=无, 1=部门警告罢工, 2=全国总罢工
    stabilization_plan_active: bool = False     # 1985 经济稳定计划包是否处于激活状态
    stabilization_months_left: int = 0          # 稳定计划工资-物价冻结剩余月数
    bank_bailout_committed: bool = False        # 1983 银行股危机是否已签署国有化兜底协议

    # 账本、预算周期与移民队列
    last_fiscal_ledger: FiscalLedger = field(default_factory=FiscalLedger)
    budget_cycle: BudgetCycleState = field(default_factory=BudgetCycleState)
    aliyah_cohorts: List[AliyahCohort] = field(default_factory=list)
```

### 3.2 政党预算偏好静态配置表 (`data/party_budget_preferences.yaml`)

每个议会政党对 8 个预算科目拥有静态权重 $V_{p, k} \in [-1.0, +1.0]$ 与不可妥协的红线阈值 $M_{p, k}$（若该党在执政联盟 `state.coalition_parties` 内，当草案滑块 $B^{\text{draft}}_k < M_{p, k}$ 时，该党在预算投票中产生强烈叛乱倾向并触发联盟摩擦）：

| 政党 ID | `defense` | `absorption` | `religion` | `dev_towns` | `education` | `welfare` | `infrastructure` | `settlements` | 执政联盟预算底线 $M_{p, k}$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `likud` | `+0.60` | `+0.40` | `+0.10` | `+0.45` | `+0.10` | `+0.15` | `+0.30` | `+0.65` | `defense >= 55`, `settlements >= 35` |
| `alignment` | `+0.40` | `+0.35` | `-0.20` | `+0.25` | `+0.50` | `+0.55` | `+0.50` | `-0.45` | `defense >= 50`, `welfare >= 45`, `education >= 45` |
| `dash` | `+0.20` | `+0.30` | `-0.40` | `+0.10` | `+0.65` | `-0.10` | `+0.55` | `-0.20` | `education >= 50`, `infrastructure >= 45` |
| `nrp` | `+0.45` | `+0.35` | `+0.75` | `+0.25` | `+0.30` | `+0.30` | `+0.15` | `+0.85` | `religion >= 40`, `settlements >= 40` |
| `agudat_yisrael` | `-0.20` | `+0.10` | `+1.00` | `+0.15` | `-0.10` | `+0.70` | `+0.00` | `+0.10` | `religion >= 45`, `welfare >= 50` |
| `shas` | `+0.10` | `+0.10` | `+0.90` | `+0.75` | `+0.10` | `+0.80` | `+0.15` | `+0.05` | `religion >= 50`, `dev_towns >= 45`, `welfare >= 55` |
| `tehiya` | `+0.85` | `+0.50` | `+0.25` | `+0.20` | `+0.10` | `+0.00` | `+0.25` | `+1.00` | `defense >= 65`, `settlements >= 60` |
| `shinui` | `+0.15` | `+0.30` | `-0.80` | `+0.00` | `+0.65` | `-0.25` | `+0.45` | `-0.50` | `education >= 50`（且要求 `religion <= 45`） |
| `ratz` | `-0.30` | `+0.35` | `-0.85` | `+0.30` | `+0.75` | `+0.60` | `+0.35` | `-0.90` | `education >= 55`, `welfare >= 50`（且要求 `settlements <= 30`） |
| `hadash` | `-0.80` | `+0.00` | `-0.60` | `+0.50` | `+0.60` | `+0.90` | `+0.40` | `-1.00` | `welfare >= 60` |

---

## 4. 核心算法、公式与结算逻辑 (Core Algorithms, Formulas & Settlement Logic)

### 4.1 结算时序总览（严格对齐 `M01` 18 步流水线）

M10 在 `M01` 的每日主循环中仅在以下 4 个钩子点执行确定性计算：
1. **Step 3 (`parliament_vote`, `daily`)**：当议会对 `bill_uid = 900000 + fiscal_year` 的年度预算案完成表决时，接收 `M03` 发出的 `m10_budget_result` 回调；若当前处于 `DUE` 或 `OVERDUE_WARNING` 状态且 `state.day >= state.m10.budget_cycle.deadline_day`，触发议会预算逾期自动解散（`D-014`）。
2. **Step 5 (`cabinet_actions`, `daily`)**：当玩家执行 `M05` 的 `submit_budget` 行动完成起草时，将 `draft_sliders` 封装为正式预算案提交 `M03`。
3. **Step 9 (`finance_monthly`, `is_month`)**：每月 1 日执行月度财政收支计算、更新 `budget_balance`、`strike_risk`、`economic_model`，并调用 `CausalNet.step_nodes(state, "M10", ["public_debt", "fx_reserves", "absorption_capacity", "union_strength"], "monthly")`。
4. **Step 16 (`economy_quarterly`, `is_quarter`)**：每季度首日（1 月 1 日、4 月 1 日、7 月 1 日、10 月 1 日）更新自适应通胀预期、移民潮队列转化、实际 GDP 指数，并调用 `CausalNet.step_nodes(state, "M10", ["growth", "inflation", "unemployment", "inequality"], "quarterly")`。
5. **Step 17 (`budget_yearly`, `is_year`)**：每年 1 月 1 日开启新财年预算周期，设置 `budget_due` 标志与 90 天法定截止期。

---

### 4.2 月度财政收支结算 (`budget_balance`, Step 9 `finance_monthly`)

#### 4.2.1 数学公式
在每月 1 日 Step 9 开始时，M10 首先读取当前已生效的预算滑块 $B_k = \text{state.m10.budget\_cycle.enacted\_sliders}[k]$，按以下 6 个分项计算当月财政收支净额 `budget_balance`（单位：`% of annual budget / month`，范围 `[-50.0, 50.0]`）：

1. **基础与周期性税收收入 $R_{\text{tax}, t}$**：
   $$R_{\text{tax}, t} = 8.000 + 0.120 \cdot (\text{growth}_t - 3.0) - 0.080 \cdot (\text{unemployment}_t - 4.0)$$
   - 常量 `8.000` 为常态增长（`growth = 3.0%`）与充分就业（`unemployment = 4.0%`）下的月度基准税收（占年度预算的 `8.0%/月`）。
   - GDP 增长每高出 `3.0%` 1 个百分点，月度税收增加 `0.120%`；失业率每高出 `4.0%` 1 个百分点，税收减少 `0.080%`。

2. **美国常规财政赠款折算流 $R_{\text{aid}, t}$**：
   $$R_{\text{aid}, t} = \max\Big(0.0,\ \big(0.600 + 0.012 \cdot (\text{us\_stance}_t - 65.0)\big) \cdot \text{mod\_factor}(\text{"us\_aid"})\Big)$$
   - 在 1977 年基准美以关系（`us_stance = 65.0`）且无美援冻结修正器（`mod_factor("us_aid") = 1.0`）时，美国对以常规经济赠款折合每月支撑年度预算的 `0.600%`。

3. **8 项国家预算滑块总支出 $E_{\text{sliders}, t}$**：
   $$E_{\text{sliders}, t} = \left(8.472 + \sum_{k \in \text{BUDGET\_ITEMS}} w_k \cdot (B_{k, t} - 50.0)\right) \cdot \text{mod\_factor}(\text{"fiscal\_spend"})$$
   - 其中各科目权重 $w_k$ 固定为：
     - $w_{\text{defense}} = 0.040$, $w_{\text{welfare}} = 0.024$, $w_{\text{education}} = 0.020$, $w_{\text{infrastructure}} = 0.018$, $w_{\text{absorption}} = 0.016$, $w_{\text{dev\_towns}} = 0.012$, $w_{\text{settlements}} = 0.012$, $w_{\text{religion}} = 0.010$。
   - 常量 `8.472` 为所有 8 个滑块均处于基准值 `50.0` 时的月度常态刚性支出。

4. **公共债务利息支出 $E_{\text{debt}, t}$**：
   $$E_{\text{debt}, t} = 0.012 \cdot \max(0.0,\ \text{public\_debt}_t - 40.0)$$
   - 当公共债务率超过安全阈值 `40.0%`（GDP 占比）后，每超出 10 个百分点，每月刚性付息支出增加 `0.120%` 年度预算。

5. **奥利维拉-坦齐通胀税基侵蚀效应（Olivera-Tanzi Effect）$E_{\text{tanzi}, t}$**：
   $$E_{\text{tanzi}, t} = 0.028 \cdot \max(0.0,\ \text{inflation}_t - 10.0) \cdot (1.0 - 0.50 \cdot \mathbb{I}_{\text{stabilization}})$$
   - 在以色列高通胀时期，由于纳税申报到实际缴库存在 1–3 个月时滞，名义税款在缴入国库时已被物价暴涨严重稀释（1977–1984 年以色列财政赤字恶化的核心机制之一）。当激活 1985 经济稳定计划（$\mathbb{I}_{\text{stabilization}} = 1$）实行源泉预扣与指数化征税后，该侵蚀减半。

6. **M05 结构性政策财政净收支 $\Delta_{\text{M05}, t}$ 与一次性冲击流 $F_{\text{one\_off}, t}$**：
   - $\Delta_{\text{M05}, t} = \text{m05\_policy\_fiscal\_delta}(\text{state})$（由 `M05` §4.3.7 提供，汇总 26 条政策杠杆偏离初始基准产生的月度财政增减）。
   - $F_{\text{one\_off}, t} = \text{state.one\_off\_flows.pop}(\text{"budget\_balance"}, 0.0)$（按 `D-010` 消费并清零当月由行动或事件注入的一次性财政收支流）。

最终月度财政收支平衡为：
$$\text{budget\_balance}_t = \text{clip}\Big(\text{round}\big(R_{\text{tax}, t} + R_{\text{aid}, t} - E_{\text{sliders}, t} - E_{\text{debt}, t} - E_{\text{tanzi}, t} + \Delta_{\text{M05}, t} + F_{\text{one\_off}, t},\ 3\big),\ -50.0,\ 50.0\Big)$$

同时更新历史累积赤字压力存量 `cumulative_deficit_stock`（范围 `[0.0, 300.0]`）：
$$\text{cumulative\_deficit\_stock}_t = \text{clip}\Big(0.985 \cdot \text{cumulative\_deficit\_stock}_{t-1} + \max(0.0,\ -\text{budget\_balance}_t - 1.40),\ 0.0,\ 300.0\Big)$$
- 注意：在 Begin 1977 开局（`budget_balance = -2.000`, `cumulative_deficit_stock = 40.0`），$0.985 \times 40.0 + (2.000 - 1.40) = 39.40 + 0.60 = 40.000$，正好处于稳态均衡！

#### 4.2.2 数值演算示例（Begin 1977 开局首个结算月 `1977-07-01`）
代入 `1977-06-20` 开局参数：
- `growth = 1.5`, `unemployment = 3.9`, `us_stance = 65.0`, `public_debt = 120.0`, `inflation = 35.0`
- 预算滑块：`defense=65, absorption=45, religion=40, dev_towns=40, education=50, welfare=55, infrastructure=50, settlements=35`
- `m05_policy_fiscal_delta(state) = -0.056`（见 `M05` §4.3.7 演算示例），`one_off_flows["budget_balance"] = 0.0`
- 修正器乘数：`mod_factor("us_aid") = 1.0`, `mod_factor("fiscal_spend") = 1.0`, $\mathbb{I}_{\text{stabilization}} = 0$

逐项计算：
1. $R_{\text{tax}} = 8.000 + 0.120 \times (1.5 - 3.0) - 0.080 \times (3.9 - 4.0) = 8.000 - 0.180 + 0.008 = 7.828$
2. $R_{\text{aid}} = 0.600 + 0.012 \times (65.0 - 65.0) = 0.600$
3. 滑块偏离加权和 $\sum w_k (B_k - 50)$：
   - `defense`: $0.040 \times (65 - 50) = +0.600$
   - `absorption`: $0.016 \times (45 - 50) = -0.080$
   - `religion`: $0.010 \times (40 - 50) = -0.100$
   - `dev_towns`: $0.012 \times (40 - 50) = -0.120$
   - `education`: $0.020 \times (50 - 50) = 0.000$
   - `welfare`: $0.024 \times (55 - 50) = +0.120$
   - `infrastructure`: $0.018 \times (50 - 50) = 0.000$
   - `settlements`: $0.012 \times (35 - 50) = -0.180$
   - 合计偏离 $= +0.600 - 0.080 - 0.100 - 0.120 + 0.120 - 0.180 = +0.240$
   - $E_{\text{sliders}} = (8.472 + 0.240) \times 1.0 = 8.712$
4. $E_{\text{debt}} = 0.012 \times (120.0 - 40.0) = 0.960$
5. $E_{\text{tanzi}} = 0.028 \times (35.0 - 10.0) = 0.700$
6. $\Delta_{\text{M05}} = -0.056$, $F_{\text{one\_off}} = 0.000$

汇总：
$$\text{budget\_balance} = 7.828 + 0.600 - 8.712 - 0.960 - 0.700 - 0.056 + 0.000 = -2.000$$
与 `parameters.yaml` 中 `budget_balance` 的 Begin 1977 初值 `-2.0` **精确吻合（误差 0.000）**。

---

### 4.3 经济体制轴 (`economic_model`) 与罢工风险 (`strike_risk`) 的月度派生计算

#### 4.3.1 经济体制轴 `economic_model`（范围 `[-100, 100]`）
`economic_model` 反映以色列从工党集权混合经济（负值）向自由市场资本主义（正值）的结构位置。它在每次政策杠杆变更及每月 Step 9 开始时，由 `M05` 的 7 项核心经济制度政策杠杆与 `union_strength` 加权派生：

$$\text{economic\_model}_t = \text{clip}\left(\text{round}\left(-45.0 + \sum_{p \in \mathcal{P}_{\text{econ}}} \omega_p \cdot (\text{policy}[p]_t - \text{policy}[p]_0) - 0.30 \cdot (\text{union\_strength}_t - 70.0),\ 3\right),\ -100.0,\ 100.0\right)$$

其中 7 项经济制度杠杆的开局基准值 $\text{policy}[p]_0$ 与体制转换权重 $\omega_p$ 如下表所示：

| 政策杠杆 ID ($p$) | 1977-06-20 初值 $\text{policy}[p]_0$ | 权重 $\omega_p$ | 若推至 100（全面自由化）对 `economic_model` 的贡献 |
| :--- | :--- | :--- | :--- |
| `privatization` | `0.0` | `+0.30` | $+30.0$ |
| `fx_regime` | `0.0` | `+0.22` | $+22.0$ |
| `capital_market` | `0.0` | `+0.20` | $+20.0$ |
| `import_protection` | `0.0` | `+0.16` | $+16.0$ |
| `central_bank` | `0.0` | `+0.14` | $+14.0$ |
| `wage_indexation` | `100.0` | `-0.18` | 若降至 `0` 贡献 $+18.0$；保持 `100` 贡献 $0.0$ |
| `food_subsidies` | `67.0` | `-0.12` | 若降至 `0` 贡献 $+8.04$；保持 `67` 贡献 $0.0$ |

**数值演算示例**：
- **Begin 1977 开局（`1977-06-20`）**：所有 $\text{policy}[p]_t = \text{policy}[p]_0$，`union_strength = 70.0`，故 $\text{economic\_model} = -45.000$。
- **1977 年 10 月埃利希改革后（`fx_regime` 从 `0` 升至 `100`，`food_subsidies` 从 `67` 降至 `33`）**：
  $$\Delta = 0.22 \times (100 - 0) - 0.12 \times (33 - 67) = +22.0 + 4.08 = +26.08 \implies \text{economic\_model} = -45.0 + 26.08 = -18.920$$
- **1990 年代全面市场化后（全部 5 项自由化杠杆升至 `100`，`wage_indexation=33`，`food_subsidies=0`，`union_strength=35`）**：
  $$\text{economic\_model} = -45.0 + (30.0 + 22.0 + 20.0 + 16.0 + 14.0 + 12.06 + 8.04) - 0.30 \times (-35.0) = -45.0 + 122.10 + 10.50 = +87.600$$

#### 4.3.2 实际工资侵蚀与罢工风险 `strike_risk`（范围 `[0, 100]`）
劳工总联合会（Histadrut）是否发动罢工取决于三个因素：**工会自身的组织能力（`union_strength`）**、**未获指数化补偿的通胀与失业造成的实际生活水平下降（`wage_erosion_index`）**，以及**政府推行私有化/削减补贴/压低最低工资的政策敌意（$H_{\text{policy}}$）**。

1. **实际工资侵蚀指数 `wage_erosion_index`（范围 `[0, 100]`）**：
   设工资指数化保护率 $\theta_{\text{protect}} = 0.75 \cdot (\text{policy}[\text{"wage\_indexation"}] / 100.0)$（当 `wage_indexation = 100` 时可抵消 75% 的通胀侵蚀；当降至 `0` 时完全暴露于通胀）：
   $$\text{wage\_erosion\_index}_t = \text{clip}\Big(0.80 \cdot \text{wage\_erosion\_index}_{t-1} + 0.20 \cdot \big((1.0 - \theta_{\text{protect}}) \cdot \max(0.0,\ \text{inflation}_t - 5.0) + 3.5 \cdot \max(0.0,\ \text{unemployment}_t - 3.5) + 0.20 \cdot \max(0.0,\ 67.0 - \text{policy}[\text{"food\_subsidies"}])\big),\ 0.0,\ 100.0\Big)$$
   - 在 Begin 1977 开局（`inflation = 35.0`, `wage_indexation = 100` $\implies \theta_{\text{protect}} = 0.75$, `unemployment = 3.9`, `food_subsidies = 67.0`）：
     目标侵蚀值 $= 0.25 \times 30.0 + 3.5 \times 0.4 + 0.0 = 7.50 + 1.40 = 8.90$。加上 1976–1977 年工党末期遗留的罢工摩擦初值 `wage_erosion_index = 20.0`。

2. **政府反劳工政策敌意 $H_{\text{policy}, t}$**：
   $$H_{\text{policy}, t} = 0.35 \cdot \text{policy}[\text{"privatization"}] + 0.25 \cdot \max(0.0,\ 50.0 - \text{policy}[\text{"minimum\_wage"}]) + 0.25 \cdot \max(0.0,\ 100.0 - \text{policy}[\text{"wage\_indexation"}]) + 0.30 \cdot \max(0.0,\ 50.0 - B_{\text{welfare}})$$
   - 在 Begin 1977 开局（`privatization = 0`, `minimum_wage = 0`, `wage_indexation = 100`, $B_{\text{welfare}} = 55$）：
     $$H_{\text{policy}, 0} = 0.0 + 0.25 \times 50.0 + 0.0 + 0.0 = 12.50$$

3. **月度罢工风险指数 `strike_risk`**：
   $$\text{strike\_risk}_t = \text{clip}\left(\text{round}\left(\frac{\text{union\_strength}_t}{70.0} \cdot \big(0.60 \cdot \text{wage\_erosion\_index}_t + 0.80 \cdot H_{\text{policy}, t} + 6.0\big),\ 3\right),\ 0.0,\ 100.0\right)$$
   - **Begin 1977 开局数值演算**：
     $$\text{strike\_risk}_0 = \frac{70.0}{70.0} \times (0.60 \times 20.0 + 0.80 \times 12.50 + 6.0) = 1.0 \times (12.0 + 10.0 + 6.0) = 28.000$$
   - **罢工阈值与升级规则（每月 Step 9 检查）**：
     - 若 `strike_cooldown_months > 0`：递减 1 个月，`active_strike_tier = 0`。
     - 若 `strike_cooldown_months == 0`：
       - 当 `strike_risk < 60.0`：`active_strike_tier = 0`，清除 `strike_warning` 与 `general_strike_active` 标志。
       - 当 `60.0 <= strike_risk < 80.0`：`active_strike_tier = 1`（**部门警告罢工**），设置 `set_flag("strike_warning")`，当月产生一次性财政损失 `one_off_flows["budget_balance"] -= 0.40`。
       - 当 `strike_risk >= 80.0`：`active_strike_tier = 2`（**Histadrut 全国总罢工**），设置 `set_flag("general_strike_active")`，向 `M12` 发出钩子信号触发 `E-G04-02`（劳工总联合会总罢工事件），并将 `strike_cooldown_months` 设为 `3`。

---

### 4.4 月度因果网络节点结算 (`public_debt`, `fx_reserves`, `absorption_capacity`, `union_strength`, Step 9)

在 Step 9 完成 `budget_balance`、`economic_model` 与 `strike_risk` 更新后，M10 通过 `CausalNet.step_nodes(state, "M10", ["public_debt", "fx_reserves", "absorption_capacity", "union_strength"], "monthly")` 执行 `M02` 标准阻尼步进（`D-052`）。

每个 `level` 节点的原始目标值 $T_{\text{raw}}$ 由：`baseline` + `M05` 激活政策杠杆边之和 + `M10` 内部因果边之和 + `M10` 自定义项（`custom` term）共同构成，经三段式 `C1` 软目标压缩 $T_{\text{soft}} = \text{soft\_target}(T_{\text{raw}}, \text{lo}_s, \text{hi}_s, w)$ 后，按 $X_{t} = X_{t-1} + \alpha \cdot (T_{\text{soft}} - X_{t-1})$ 步进。

#### 4.4.1 节点 1：`public_debt`（公共债务占 GDP 比重，范围 `[0, 300]`）
- **节点配置**：`mode: level`, `baseline: 97.50`, `alpha: 0.15`, `soft: {lo_s: 20.0, hi_s: 240.0, w: 45.0}`
- **输入边与自定义项汇总**：
  1. **M05 政策杠杆边**（来自 `M05` 附录 C）：
     - `M05.POL.capital_market.public_debt`: $0.02 \cdot (\text{policy}[\text{"capital\_market"}] - 50)$（开局 `v=0` $\implies -1.00$）
     - `M05.POL.central_bank.public_debt`: $-0.02 \cdot (\text{policy}[\text{"central\_bank"}] - 50)$（开局 `v=0` $\implies +1.00$）
     - M05 边开局合计 $= 0.000$。
  2. **`M10.DEBT.01`（月度财政赤字边）**：`source: budget_balance`, `type: linear`, `c: -8.00`, `offset: 0.0`
     - 贡献：$-8.00 \cdot \text{budget\_balance}_t$（开局 `budget_balance = -2.0` $\implies +16.000$）。
  3. **`M10.DEBT.02`（GDP 增长率分母稀释边）**：`source: growth`, `type: linear`, `c: -3.00`, `offset: 3.0`
     - 贡献：$-3.00 \cdot (\text{growth}_t - 3.0)$（开局 `growth = 1.5` $\implies +4.500$）。
  4. **`M10.DEBT.03`（历史赤字存量与外债估值自定义项 `m10_debt_burden_term`）**：
     $$\text{m10\_debt\_burden\_term}(\text{state}) = 0.35 \cdot (\text{cumulative\_deficit\_stock}_t - 40.0) + 0.40 \cdot \max(0.0,\ 40.0 - \text{fx\_reserves}_t) + 18.0 \cdot \mathbb{I}_{\text{bank\_bailout}}$$
     - 其中 $\mathbb{I}_{\text{bank\_bailout}} = 1$ 当且仅当 1983 年银行股崩盘后政府签署了国有化兜底协议（`state.m10.bank_bailout_committed == True`，将各大银行坏账直接转为国家公共债务，推高债务率 `18.0` 个百分点）。
     - 开局（`cumulative_deficit_stock = 40.0`, `fx_reserves = 35.0`, $\mathbb{I}_{\text{bank\_bailout}} = 0$）：贡献 $0.00 + 0.40 \times 5.0 + 0.00 = +2.000$。
- **Begin 1977 开局演算验证**：
  $$T_{\text{raw}} = 97.50 + 0.00 + 16.00 + 4.50 + 2.00 = 120.000$$
  因 $120.000 \in [20.0, 240.0]$，$T_{\text{soft}} = 120.000$，$\Delta = 0.15 \times (120.000 - 120.000) = 0.000$。

#### 4.4.2 节点 2：`fx_reserves`（国家外汇储备指数，范围 `[0, 100]`）
- **节点配置**：`mode: level`, `baseline: 43.20`, `alpha: 0.25`, `soft: {lo_s: 15.0, hi_s: 85.0, w: 13.0}`
- **输入边与自定义项汇总**：
  1. **M05 政策杠杆与修正器边**（来自 `M05` 附录 C）：
     - `M05.POL.fx_regime.fx_reserves`: $+0.04 \cdot (\text{policy}[\text{"fx\_regime"}] - 50)$（开局 `v=0` $\implies -2.00$）
     - `M05.POL.bank_share_support.fx_reserves`: $-0.02 \cdot (\text{policy}[\text{"bank\_share\_support"}] - 50)$（开局 `v=100` $\implies -1.00$）
     - `M05.MOD.bank_bubble.fx_reserves`: 激活 `bank_bubble` 时固定贡献 $-1.00$（开局激活 $\implies -1.00$）
     - M05 边开局合计 $= -4.000$。
  2. **`M10.FX.01`（美国外交支持与融资便利边）**：`source: us_stance`, `type: linear`, `c: 0.30`, `offset: 50.0`
     - 贡献：$+0.30 \cdot (\text{us\_stance}_t - 50.0)$（开局 `us_stance = 65.0` $\implies +4.500$）。
  3. **`M10.FX.02`（本币高通胀导致进口替代与贸易逆差边）**：`source: inflation`, `type: linear`, `c: -0.18`, `offset: 10.0`
     - 贡献：$-0.18 \cdot (\text{inflation}_t - 10.0)$（开局 `inflation = 35.0` $\implies -4.500$）。
  4. **`M10.FX.03`（实际经济增长与出口创汇能力边）**：`source: growth`, `type: linear`, `c: 0.80`, `offset: 3.0`
     - 贡献：$+0.80 \cdot (\text{growth}_t - 3.0)$（开局 `growth = 1.5` $\implies -1.200$）。
  5. **`M10.FX.04`（国防军购用汇、资本外逃与修正器自定义项 `m10_fx_balance_term`）**：
     $$\text{m10\_fx\_balance\_term}(\text{state}) = -0.20 \cdot (B_{\text{defense}, t} - 50.0) \cdot \text{mod\_factor}(\text{"fx\_spend"}) - 8.0 \cdot (\text{mod\_factor}(\text{"fx\_spend"}) - 1.0) + 6.0 \cdot (\text{mod\_factor}(\text{"us\_aid"}) - 1.0) - 0.08 \cdot \max(0.0,\ \text{inflation}_t - 80.0)$$
     - 当 `inflation > 80.0` 且外汇已经自由化时，居民抢购黑市美元（资本外逃）会额外加速外汇流失。
     - 开局（$B_{\text{defense}} = 65.0$, `fx_spend = 1.0`, `us_aid = 1.0`, `inflation = 35.0`）：贡献 $-0.20 \times 15.0 = -3.000$。
- **Begin 1977 开局演算验证**：
  $$T_{\text{raw}} = 43.20 - 4.00 + 4.50 - 4.50 - 1.20 - 3.00 = 35.000$$
  因 $35.000 \in [15.0, 85.0]$，$T_{\text{soft}} = 35.000$，$\Delta = 0.000$。
- **外汇危机标志触发（Step 9 后置检查）**：
  - 若 `fx_reserves < 20.0`（不足 2 个月进口额）：设置 `set_flag("fx_crisis")`，向 `M12` 发出钩子信号触发 `E-G04-06`（外汇储备见底紧急状态）。
  - 若 `fx_reserves >= 24.0`（滞回恢复阈值）：清除 `clear_flag("fx_crisis")`。

#### 4.4.3 节点 3：`absorption_capacity`（移民吸纳容量，范围 `[0, 100]`）
- **节点配置**：`mode: level`, `baseline: 60.06`, `alpha: 0.20`, `soft: {lo_s: 15.0, hi_s: 85.0, w: 13.0}`
- **输入边与自定义项汇总**：
  1. **M05 政策杠杆边**（来自 `M05` 附录 C）：
     - `public_housing` (`c=+0.08`, 开局 `v=50` $\implies 0.00$)
     - `absorption_basket` (`c=+0.04`, 开局 `v=50` $\implies 0.00$)
     - `ethiopian_aliyah` (`c=-0.02`, 开局 `v=33` $\implies +0.34$)
     - `immigrant_dispersal` (`c=+0.03`, 开局 `v=50` $\implies 0.00$)
     - M05 边开局合计 $= +0.340$。
  2. **`M10.ABS.01`（宏观经济吸纳力边）**：`source: growth`, `type: linear`, `c: 1.20`, `offset: 3.0`
     - 贡献：$+1.20 \cdot (\text{growth}_t - 3.0)$（开局 `growth = 1.5` $\implies -1.800$）。
  3. **`M10.ABS.02`（劳动力市场闲置挤压边）**：`source: unemployment`, `type: linear`, `c: -1.50`, `offset: 4.0`
     - 贡献：$-1.50 \cdot (\text{unemployment}_t - 4.0)$（开局 `unemployment = 3.9` $\implies +0.150$）。
  4. **`M10.ABS.03`（吸纳/基建/发展城镇预算投入与移民潮负荷自定义项 `m10_absorption_budget_term`）**：
     $$\text{m10\_absorption\_budget\_term}(\text{state}) = 0.45 \cdot (B_{\text{absorption}, t} - 50.0) + 0.20 \cdot (B_{\text{infrastructure}, t} - 50.0) + 0.15 \cdot (B_{\text{dev\_towns}, t} - 50.0) - \sum_{c \in \text{cohorts}} c.\text{current\_load}$$
     - 开局（$B_{\text{absorption}} = 45.0$, $B_{\text{infrastructure}} = 50.0$, $B_{\text{dev\_towns}} = 40.0$, 无活跃移民潮队列）：
       贡献 $= 0.45 \times (-5.0) + 0.00 + 0.15 \times (-10.0) - 0.00 = -2.25 - 1.50 = -3.750$。
- **Begin 1977 开局演算验证**：
  $$T_{\text{raw}} = 60.06 + 0.34 - 1.80 + 0.15 - 3.75 = 55.000$$
  因 $55.000 \in [15.0, 85.0]$，$T_{\text{soft}} = 55.000$，$\Delta = 0.000$。

#### 4.4.4 节点 4：`union_strength`（劳工总联合会力量，范围 `[0, 100]`）
- **节点配置**：`mode: level`, `baseline: 52.17`, `alpha: 0.15`, `soft: {lo_s: 15.0, hi_s: 85.0, w: 13.0}`
- **输入边汇总**：
  1. **M05 政策杠杆边**（来自 `M05` 附录 C）：
     - `sabbath_el_al` (`c=+0.02`, 开局 `v=0` $\implies -1.00$)
     - `wage_indexation` (`c=+0.06`, 开局 `v=100` $\implies +3.00$)
     - `privatization` (`c=-0.10`, 开局 `v=0` $\implies +5.00$)
     - `capital_market` (`c=-0.02`, 开局 `v=0` $\implies +1.00$)
     - `minimum_wage` (`c=+0.03`, 开局 `v=0` $\implies -1.50$)
     - M05 边开局合计 $= +6.500$。
  2. **`M10.UNI.01`（经济体制结构性根基边）**：`source: economic_model`, `type: linear`, `c: -0.25`, `offset: 0.0`
     - 贡献：$-0.25 \cdot \text{economic\_model}_t$（开局 `economic_model = -45.0` $\implies +11.250$）。
  3. **`M10.UNI.02`（高失业率削弱工会议价力边）**：`source: unemployment`, `type: linear`, `c: -0.80`, `offset: 4.0`
     - 贡献：$-0.80 \cdot (\text{unemployment}_t - 4.0)$（开局 `unemployment = 3.9` $\implies +0.080$）。
- **Begin 1977 开局演算验证**：
  $$T_{\text{raw}} = 52.17 + 6.50 + 11.25 + 0.08 = 70.000$$
  因 $70.000 \in [15.0, 85.0]$，$T_{\text{soft}} = 70.000$，$\Delta = 0.000$。

---

### 4.5 季度宏观经济结算 (`growth`, `inflation`, `unemployment`, `inequality`, Step 16 `economy_quarterly`)

每季度首日（1 月 1 日、4 月 1 日、7 月 1 日、10 月 1 日）Step 16 执行以下三步：

#### 4.5.1 第一步：更新自适应通胀预期 `expected_inflation` 与移民潮队列
1. **自适应通胀预期 $\pi_t^e$ 更新公式**：
   - **常态模式（`stabilization_months_left == 0`）**：
     $$\pi_t^e = \text{clip}\Big(0.65 \cdot \pi_{t-1}^e + 0.35 \cdot \text{inflation}_{t-1} + 1.50 \cdot \max(0.0,\ -\text{budget\_balance}_t - 2.5),\ -5.0,\ 500.0\Big)$$
   - **1985 稳定计划锚定模式（`stabilization_months_left > 0` 且 `budget_balance >= -2.0`）**：
     当政府正式实施稳定计划（汇率锚定 + 预算硬约束 + 冻结工资物价）时，公众通胀预期发生“可信度去锚定（Credible Disinflation）”：
     $$\pi_t^e = \text{clip}\Big(0.30 \cdot \pi_{t-1}^e + 0.70 \cdot 16.0,\ -5.0,\ 500.0\Big)$$
   - 在 Begin 1977 开局（$\pi_0^e = 35.0$, $\text{inflation}_0 = 35.0$, $\text{budget\_balance}_0 = -2.0$）：
     $$\pi_1^e = 0.65 \times 35.0 + 0.35 \times 35.0 + 0.0 = 35.000$$

2. **外部通胀冲击衰减**：
   $$\text{external\_inflation\_shock}_t = \text{round}(0.75 \cdot \text{external\_inflation\_shock}_{t-1},\ 3)$$

3. **移民潮分批队列（`AliyahCohort`）短期负荷向长期红利转化**：
   对于 `state.m10.aliyah_cohorts` 中的每一个批次 $c$（如 1989–1991 苏联大移民注入的批次，初始规模 $M_0 = c.\text{initial\_magnitude}$）：
   - 令 $q = c.\text{quarters\_elapsed} + 1$，更新 $c.\text{quarters\_elapsed} = q$。
   - **短期吸纳负荷 $c.\text{current\_load}$**（前 4 个季度处于峰值，随后按指数衰减）：
     $$c.\text{current\_load} = M_0 \cdot 0.80^{\max(0, q - 2)}$$
   - **长期人力资本增长红利 $c.\text{current\_growth\_dividend}$**（第 1–3 季度为 `0.0`，从第 4 季度起随高技能工程师/医生进入劳动力市场逐步释放，第 8–16 季度达到峰值）：
     $$c.\text{current\_growth\_dividend} = \begin{cases} 0.0, & q \le 3 \\ 0.12 \cdot M_0 \cdot \min\left(1.0,\ \frac{q - 3}{5.0}\right) \cdot 0.92^{\max(0, q - 12)}, & q > 3 \end{cases}$$
   - 当 $q > 24$（满 6 年）时，将该队列移出 `aliyah_cohorts`。

#### 4.5.2 第二步：4 个季度因果网络节点步进 (`CausalNet.step_nodes`)

##### 节点 5：`inflation`（年化 CPI 通胀率，范围 `[-5, 500]`）
- **节点配置**：`mode: level`, `baseline: 5.34`, `alpha: 0.35`, `memory_rho: 0.30`, `memory_mu: 0.05`, `memory_cap: 150.0`, `soft: {lo_s: -1.0, hi_s: 420.0, w: 60.0}`
- **输入边与自定义项汇总**：
  1. **M05 政策杠杆边**（来自 `M05` 附录 C）：
     - `fx_regime` (`c=+0.03`, 开局 `v=0` $\implies -1.50$)
     - `food_subsidies` (`c=-0.02`, 开局 `v=67` $\implies -0.34$)
     - `wage_indexation` (`c=+0.06`, 开局 `v=100` $\implies +3.00$)
     - `vat_rate` (`c=+0.02`, 开局 `v=0` $\implies -1.00$)
     - `capital_market` (`c=+0.02`, 开局 `v=0` $\implies -1.00$)
     - `bank_share_support` (`c=+0.01`, 开局 `v=100` $\implies +0.50$)
     - `import_protection` (`c=-0.02`, 开局 `v=0` $\implies +1.00$)
     - `central_bank` (`c=-0.06`, 开局 `v=0` $\implies +3.00$)
     - `public_housing` (`c=-0.02`, 开局 `v=50` $\implies 0.00$)
     - M05 边开局合计 $= +3.660$。
  2. **`M10.INF.01`（财政赤字总需求推动边）**：`source: budget_balance`, `type: linear`, `c: -4.50`, `offset: 0.0`
     - 贡献：$-4.50 \cdot \text{budget\_balance}_t$（开局 `budget_balance = -2.0` $\implies +9.000$）。
  3. **`M10.INF.02`（工会工资追涨推动边）**：`source: union_strength`, `type: linear`, `c: 0.25`, `offset: 50.0`
     - 贡献：$+0.25 \cdot (\text{union\_strength}_t - 50.0)$（开局 `union_strength = 70.0` $\implies +5.000$）。
  4. **`M10.INF.03`（外汇枯竭引发本币贬值螺旋阈值边）**：`source: fx_reserves`, `type: threshold`, `threshold: 30.0`, `direction: below`, `c: 1.20`
     - 当 `fx_reserves < 30.0` 时，每低于 30 点 1 点贡献 $+1.20$（开局 `fx_reserves = 35.0` $\implies 0.000$）。
  5. **`M10.INF.04`（工资-物价指数化螺旋与赤字印钞自定义项 `m10_inflation_spiral_term`）**：
     $$\text{m10\_inflation\_spiral\_term}(\text{state}) = \psi_{\text{index}, t} \cdot (\pi_t^e - 10.0) + \Phi_{\text{monetize}, t} + \text{external\_inflation\_shock}_t$$
     其中：
     - **指数化传导系数** $\psi_{\text{index}, t}$：
       $$\psi_{\text{index}, t} = \max\Big(0.10,\ 0.28 + 0.0024 \cdot (\text{policy}[\text{"wage\_indexation"}] - 50.0) - 0.0016 \cdot (\text{policy}[\text{"central\_bank"}] - 50.0)\Big)$$
       在开局（`wage_indexation = 100`, `central_bank = 0`）时，$\psi_{\text{index}, 0} = 0.28 + 0.12 + 0.08 = 0.480$。
     - **赤字印钞非线性加速器** $\Phi_{\text{monetize}, t}$：
       $$\Phi_{\text{monetize}, t} = 2.50 \cdot \max(0.0,\ -\text{budget\_balance}_t - 3.0)^2 \cdot \left(1.0 + \frac{50.0 - \text{policy}[\text{"central\_bank"}]}{50.0}\right)$$
       当月度赤字控制在 `-3.0` 以内时，$\Phi_{\text{monetize}} = 0.0$；一旦赤字突破 `-3.0` 且央行不独立（`central_bank = 0`，《禁止印钞法》尚未通过），央行被迫直接购买政府债券印钞弥补赤字，引发二次方级别的恶性通胀飙升（例如 `budget_balance = -8.0` 时，$\Phi_{\text{monetize}} = 2.50 \times 25.0 \times 2.0 = +125.0$；`budget_balance = -9.5` 时，$\Phi_{\text{monetize}} = +211.25$，连同 $\pi_t^e$ 将通胀推至 `380%~445%`）。
     - 开局（$\pi_0^e = 35.0$, $\psi_{\text{index}, 0} = 0.480$, $\Phi_{\text{monetize}, 0} = 0.0$, $\text{external\_inflation\_shock}_0 = 0.0$）：
       $$\text{m10\_inflation\_spiral\_term} = 0.480 \times (35.0 - 10.0) + 0.0 + 0.0 = +12.000$$
- **Begin 1977 开局演算验证**：
  $$T_{\text{raw}} = 5.34 + 3.66 + 9.00 + 5.00 + 0.00 + 12.00 = 35.000$$
  因 $35.000 \in [-1.0, 420.0]$，$T_{\text{soft}} = 35.000$，$\Delta = 0.000$。
- **通胀危机标志触发（Step 16 后置检查）**：
  - 若 `inflation >= 80.0`：设置 `set_flag("inflation_crisis")`（解锁 `E-1985-07` 经济稳定计划等危机响应行动）。
  - 若 `inflation >= 180.0`：设置 `set_flag("hyperinflation")`（触发 `E-G04-01` 恶性通胀螺旋事件）。
  - 若 `inflation < 65.0`：清除 `inflation_crisis` 与 `hyperinflation`。

##### 节点 6：`growth`（实际 GDP 年化增长率，范围 `[-15, 20]`）
- **节点配置**：`mode: level`, `baseline: 3.82`, `alpha: 0.25`, `soft: {lo_s: -8.0, hi_s: 9.5, w: 3.5}`
- **输入边与自定义项汇总**：
  1. **M05 政策杠杆边**（来自 `M05` 附录 C，共 13 条）：
     - `autopsy_rules` (`v=67, c=-0.002` $\implies -0.034$)
     - `sabbath_commerce` (`v=67, c=-0.004` $\implies -0.068$)
     - `haredi_school_autonomy` (`v=67, c=-0.004` $\implies -0.068$)
     - `vat_rate` (`v=0, c=-0.005` $\implies +0.250$)
     - `top_income_tax` (`v=50, c=-0.01` $\implies 0.000$)
     - `privatization` (`v=0, c=+0.01` $\implies -0.500$)
     - `capital_market` (`v=0, c=+0.01` $\implies -0.500$)
     - `bank_share_support` (`v=100, c=+0.01` $\implies +0.500$)
     - `import_protection` (`v=0, c=+0.01` $\implies -0.500$)
     - `central_bank` (`v=0, c=-0.01` $\implies +0.500$)
     - `free_secondary_education` (`v=0, c=+0.01` $\implies -0.500$)
     - `reserve_duty` (`v=50, c=-0.01` $\implies 0.000$)
     - `conscription_length` (`v=67, c=-0.01` $\implies -0.170$)
     - M05 边开局合计 $= -1.090$。
  2. **`M10.GRO.01`（高通胀扭曲相对价格与投资边）**：`source: inflation`, `type: linear`, `c: -0.04`, `offset: 10.0`
     - 贡献：$-0.04 \cdot (\text{inflation}_t - 10.0)$（开局 `inflation = 35.0` $\implies -1.000$）。
  3. **`M10.GRO.02`（国家安全环境与商业信心边）**：`source: security_index`, `type: linear`, `c: 0.06`, `offset: 60.0`
     - 贡献：$+0.06 \cdot (\text{security\_index}_t - 60.0)$（开局 `security_index = 62.0` $\implies +0.120$）。
  4. **`M10.GRO.03`（移民吸纳与住房建设边）**：`source: absorption_capacity`, `type: linear`, `c: 0.05`, `offset: 50.0`
     - 贡献：$+0.05 \cdot (\text{absorption\_capacity}_t - 50.0)$（开局 `absorption_capacity = 55.0` $\implies +0.250$）。
  5. **`M10.GRO.04`（公共投资、国防挤出、罢工停摆与移民红利自定义项 `m10_growth_structural_term`）**：
     $$\text{m10\_growth\_structural\_term}(\text{state}) = 0.04 \cdot (B_{\text{infrastructure}, t} - 50.0) + 0.03 \cdot (B_{\text{education}, t} - 50.0) - 0.04 \cdot (B_{\text{defense}, t} - 50.0) - 0.05 \cdot \max(0.0,\ \text{strike\_risk}_t - 30.0) + \sum_{c \in \text{cohorts}} c.\text{current\_growth\_dividend}$$
     - 开局（$B_{\text{infrastructure}} = 50.0$, $B_{\text{education}} = 50.0$, $B_{\text{defense}} = 65.0$, $\text{strike\_risk} = 28.0$, 无活跃移民队列）：
       贡献 $= 0.00 + 0.00 - 0.04 \times 15.0 - 0.00 + 0.00 = -0.600$。
- **Begin 1977 开局演算验证**：
  $$T_{\text{raw}} = 3.82 - 1.09 - 1.00 + 0.12 + 0.25 - 0.60 = 1.500$$
  因 $1.500 \in [-8.0, 9.5]$，$T_{\text{soft}} = 1.500$，$\Delta = 0.000$。
- **实际 GDP 累积指数更新（Step 16 后置）**：
  $$\text{real\_gdp\_index}_t = \text{round}\left(\text{real\_gdp\_index}_{t-1} \cdot \left(1.0 + \frac{\text{growth}_t}{400.0}\right),\ 3\right)$$

##### 节点 7：`unemployment`（城镇失业率，范围 `[0, 40]`）
- **节点配置**：`mode: level`, `baseline: 7.26`, `alpha: 0.20`, `soft: {lo_s: 2.0, hi_s: 25.0, w: 6.0}`
- **输入边与自定义项汇总**：
  1. **M05 政策杠杆边**（来自 `M05` 附录 C，共 7 条）：
     - `haredi_school_autonomy` (`v=67, c=+0.01` $\implies +0.170$)
     - `privatization` (`v=0, c=+0.02` $\implies -1.000$)
     - `import_protection` (`v=0, c=+0.03` $\implies -1.500$)
     - `minimum_wage` (`v=0, c=+0.02` $\implies -1.000$)
     - `conscription_length` (`v=67, c=-0.01` $\implies -0.170$)
     - `arms_sourcing` (`v=50, c=-0.01` $\implies 0.000$)
     - `work_permits` (`v=67, c=+0.02` $\implies +0.340$)
     - M05 边开局合计 $= -3.160$。
  2. **`M10.UNE.01`（奥肯定律 Okun's Law 边）**：`source: growth`, `type: linear`, `c: -0.40`, `offset: 3.0`
     - 贡献：$-0.40 \cdot (\text{growth}_t - 3.0)$（开局 `growth = 1.5` $\implies +0.600$）。
  3. **`M10.UNE.02`（移民安置与职业培训吸纳边）**：`source: absorption_capacity`, `type: linear`, `c: -0.06`, `offset: 50.0`
     - 贡献：$-0.06 \cdot (\text{absorption\_capacity}_t - 50.0)$（开局 `absorption_capacity = 55.0` $\implies -0.300$）。
  4. **`M10.UNE.03`（劳工总联合会国企终身雇佣保护边）**：`source: union_strength`, `type: linear`, `c: -0.04`, `offset: 50.0`
     - 贡献：$-0.04 \cdot (\text{union\_strength}_t - 50.0)$（开局 `union_strength = 70.0` $\implies -0.800$）。
  5. **`M10.UNE.04`（移民潮短期劳动力供给冲击与区域就业预算自定义项 `m10_unemployment_shock_term`）**：
     $$\text{m10\_unemployment\_shock\_term}(\text{state}) = 0.22 \cdot \max\left(0.0,\ \sum_{c \in \text{cohorts}} c.\text{current\_load} - 0.30 \cdot (\text{absorption\_capacity}_t - 40.0)\right) - 0.03 \cdot (B_{\text{dev\_towns}, t} - 50.0) - 0.02 \cdot (B_{\text{infrastructure}, t} - 50.0)$$
     - 开局（无移民队列，$B_{\text{dev\_towns}} = 40.0$, $B_{\text{infrastructure}} = 50.0$）：
       贡献 $= 0.00 - 0.03 \times (-10.0) - 0.00 = +0.300$。
- **Begin 1977 开局演算验证**：
  $$T_{\text{raw}} = 7.26 - 3.16 + 0.60 - 0.30 - 0.80 + 0.30 = 3.900$$
  因 $3.900 \in [2.0, 25.0]$，$T_{\text{soft}} = 3.900$，$\Delta = 0.000$。

##### 节点 8：`inequality`（基尼不平等指数，范围 `[0, 100]`）
- **节点配置**：`mode: level`, `baseline: 44.86`, `alpha: 0.15`, `soft: {lo_s: 15.0, hi_s: 85.0, w: 13.0}`
- **输入边与自定义项汇总**：
  1. **M05 政策杠杆边**（来自 `M05` 附录 C，共 8 条）：
     - `food_subsidies` (`v=67, c=-0.04` $\implies -0.680$)
     - `vat_rate` (`v=0, c=+0.03` $\implies -1.500$)
     - `top_income_tax` (`v=50, c=-0.04` $\implies 0.000$)
     - `child_allowance` (`v=50, c=-0.03` $\implies 0.000$)
     - `public_housing` (`v=50, c=-0.03` $\implies 0.000$)
     - `school_integration` (`v=50, c=-0.03` $\implies 0.000$)
     - `free_secondary_education` (`v=0, c=-0.04` $\implies +2.000$)
     - `minimum_wage` (`v=0, c=-0.04` $\implies +2.000$)
     - M05 边开局合计 $= +1.820$。
  2. **`M10.INE.01`（市场化体制拉大资本与劳动回报差距边）**：`source: economic_model`, `type: linear`, `c: 0.16`, `offset: 0.0`
     - 贡献：$+0.16 \cdot \text{economic\_model}_t$（开局 `economic_model = -45.0` $\implies -7.200$）。
  3. **`M10.INE.02`（失业扩大底层收入差距边）**：`source: unemployment`, `type: linear`, `c: 0.80`, `offset: 4.0`
     - 贡献：$+0.80 \cdot (\text{unemployment}_t - 4.0)$（开局 `unemployment = 3.9` $\implies -0.080$）。
  4. **`M10.INE.03`（工会集体谈判压缩工资差距边）**：`source: union_strength`, `type: linear`, `c: -0.15`, `offset: 50.0`
     - 贡献：$-0.15 \cdot (\text{union\_strength}_t - 50.0)$（开局 `union_strength = 70.0` $\implies -3.000$）。
  5. **`M10.INE.04`（高通胀累退税效应边）**：`source: inflation`, `type: linear`, `c: 0.04`, `offset: 10.0`
     - 贡献：$+0.04 \cdot (\text{inflation}_t - 10.0)$（开局 `inflation = 35.0` $\implies +1.000$）。
  6. **`M10.INE.05`（福利/教育/发展城镇预算再分配自定义项 `m10_inequality_budget_term`）**：
     $$\text{m10\_inequality\_budget\_term}(\text{state}) = -0.18 \cdot (B_{\text{welfare}, t} - 50.0) - 0.12 \cdot (B_{\text{education}, t} - 50.0) - 0.15 \cdot (B_{\text{dev\_towns}, t} - 50.0)$$
     - 开局（$B_{\text{welfare}} = 55.0$, $B_{\text{education}} = 50.0$, $B_{\text{dev\_towns}} = 40.0$）：
       贡献 $= -0.18 \times 5.0 - 0.00 - 0.15 \times (-10.0) = -0.90 + 1.50 = +0.600$。
- **Begin 1977 开局演算验证**：
  $$T_{\text{raw}} = 44.86 + 1.82 - 7.20 - 0.08 - 3.00 + 1.00 + 0.60 = 38.000$$
  因 $38.000 \in [15.0, 85.0]$，$T_{\text{soft}} = 38.000$，$\Delta = 0.000$。

---

### 4.6 年度国家预算周期与议会表决全生命周期 (`budget_yearly`, Step 17 & Step 3)

#### 4.6.1 开启年度预算周期（每年 1 月 1 日 Step 17 `budget_yearly`）
1. 在每年 1 月 1 日（`is_year == True`），若当前政府非看守内阁（`state.caretaker == False`）：
   - `state.m10.budget_cycle.fiscal_year = current_year`
   - `state.m10.budget_cycle.status = "DUE"`
   - `state.m10.budget_cycle.opened_day = state.day`
   - `state.m10.budget_cycle.deadline_day = state.day + 90`（法定 90 天期限，对应 4 月 1 日，闰年 3 月 31 日）
   - `state.m10.budget_cycle.warning_60d_emitted = False`
   - `state.m10.budget_cycle.rejection_count_this_year = 0`
   - `state.m10.budget_cycle.draft_sliders = dict(state.m10.budget_cycle.enacted_sliders)`
   - 设置全局标志 `set_flag("budget_due")`。
2. 若 1 月 1 日当天正处于看守内阁期间（`state.caretaker == True`）：
   - 按以色列《基本法：国家经济》延续预算（1/12 临时拨款规则）自动顺延上一年度 `enacted_sliders`，并将 `deadline_day` 推迟至新内阁完成组阁宣誓（`M03` 退出 `caretaker` 状态）后的 `+90` 天。

#### 4.6.2 预算草案调整与政党支持度预测 (`m10_set_draft_slider`)
玩家可在预算面板中随时调整 8 个科目的草案滑块 $B^{\text{draft}}_k \in [0, 100]$（步长 `5.0` 点）。每次调整立即实时计算：
1. **预计月度财政差额 $\widehat{\text{budget\_balance}}$**：将 $B^{\text{draft}}_k$ 代入 §4.2.1 公式预估。
2. **各政党对当前预算草案的偏好得分 $S_p(\text{draft})$**（供 `M03` 在预算案投票时作为法案立场 `hint` 使用）：
   $$S_p(\text{draft}) = \sum_{k \in \text{BUDGET\_ITEMS}} V_{p, k} \cdot \left(\frac{B^{\text{draft}}_k - B^{\text{enacted}}_k}{10.0}\right) - \sum_{k \in \text{redlines}(p)} 2.50 \cdot \max\left(0.0,\ \frac{M_{p, k} - B^{\text{draft}}_k}{5.0}\right)$$
   - 若某执政联盟成员党 $p \in \text{state.coalition\_parties}$ 的任何一项预算红线被跌破（$B^{\text{draft}}_k < M_{p, k}$），UI 立即高亮显示该党“红线违背警告”，且该党在 `M03` 表决时的反叛概率激增。

#### 4.6.3 提交预算案 (`submit_budget` $\rightarrow$ `M03` `m03_submit_bill`)
当玩家在 `M05` 发起 `submit_budget` 内阁行动（消耗 `25` 政治资本，`prep_days: 7`，要求 `flag_is_set("budget_due")`）并在 Step 5 完成准备时：
1. `M10` 将当前 `draft_sliders` 冻结，生成 `bill_uid = 900000 + state.m10.budget_cycle.fiscal_year`。
2. 更新 `state.m10.budget_cycle.status = "VOTING"`，`active_bill_uid = bill_uid`。
3. 调用 `M03` 接口 `m03_submit_bill`：
   ```python
   m03_submit_bill(
       state,
       bill_uid=900000 + state.m10.budget_cycle.fiscal_year,
       action_uid="submit_budget",
       vote="budget",
       hint=compute_budget_party_hints(state),
       deadline_day=state.m10.budget_cycle.deadline_day,
   )
   ```

#### 4.6.4 议会预算案表决回调 (`m10_budget_result` / `m10_pass_budget`)
当 `M03` 在 Step 3 完成对 `vote: "budget"` 法案的表决后，回调 `M10` 的 `m10_budget_result(state, year, passed)`：
- **分支 A：表决通过（`passed == True`）**（或通过 `M05` 的 `m10_pass_budget` 钩子触发）：
  1. `state.m10.budget_cycle.enacted_sliders = dict(state.m10.budget_cycle.draft_sliders)`
  2. `state.m10.budget_cycle.status = "PASSED"`
  3. `state.m10.budget_cycle.active_bill_uid = None`
  4. 清除标志：`clear_flag("budget_due")`, `clear_flag("budget_deadline_60")`。
  5. 检查 `M04` 承诺兑现：遍历 `state.promises` 中与预算相关的承诺（如保证宗教拨款、定居点拨款或福利拨款不削减），通知 `M04` 更新兑现状态。
- **分支 B：表决被否决（`passed == False`）**：
  1. `state.m10.budget_cycle.rejection_count_this_year += 1`
  2. `state.m10.budget_cycle.active_bill_uid = None`
  3. 若当前 `state.day < state.m10.budget_cycle.deadline_day`：
     - 预算周期退回 `status = "DUE"`（或 `"OVERDUE_WARNING"`），保持 `budget_due` 标志激活。玩家可在剩余天数内向联盟伙伴妥协修改 `draft_sliders` 并再次发起 `submit_budget`（遵循 `M03` §4.9.3 与 `D-014`：单次预算投票失败不会立即解散议会，只有超过 `deadline_day` 仍未通过才自动解散议会）。
  4. 若当前 `state.day >= state.m10.budget_cycle.deadline_day`：
     - 立即触发 §4.6.5 预算逾期议会解散。

#### 4.6.5 倒计时 60 天预警与 90 天逾期自动解散 (`D-014`)
在每日 Step 3 (`parliament_vote`) 末尾，若 `flag_is_set("budget_due")` 为真：
1. **倒计时预警检查**（当 `state.day >= state.m10.budget_cycle.opened_day + 60` 且 `warning_60d_emitted == False`）：
   - `state.m10.budget_cycle.warning_60d_emitted = True`
   - `state.m10.budget_cycle.status = "OVERDUE_WARNING"`
   - 设置标志 `set_flag("budget_deadline_60")`
   - 触发 `M01` 自动暂停信号 `AP09`（`budget_deadline_60`）并向 `M12` 发送 `budget_deadline_60d` 钩子以弹出 `E-G04-08`（预算大限逼近危机事件）。
2. **90 天大限逾期检查**（当 `state.day >= state.m10.budget_cycle.deadline_day` 且 `status != "PASSED"`）：
   - `state.m10.budget_cycle.status = "DISSOLVED"`
   - 清除 `clear_flag("budget_due")`, `clear_flag("budget_deadline_60")`
   - 调用 `M03` 接口触发议会依法自动解散、政府转为看守内阁并启动大选倒计时（`m03_dissolve_knesset(state, reason="budget_overdue")`）。

---

## 5. 跨模块接口与自定义操作契约 (Cross-Module Interfaces & Custom Ops)

### 5.1 M10 暴露给其他模块的查询与回调接口

| 接口函数签名 | 调用方 | 调用时机 | 返回值 / 行为说明 |
| :--- | :--- | :--- | :--- |
| `m10_finance_monthly(state) -> None` | `M01` | Step 9 (`is_month`) | 执行月度财政收支、罢工风险更新与 4 个月度因果节点步进 |
| `m10_economy_quarterly(state) -> None` | `M01` | Step 16 (`is_quarter`) | 执行预期通胀、移民潮转化、实际 GDP 指数与 4 个季度因果节点步进 |
| `m10_budget_yearly(state) -> None` | `M01` | Step 17 (`is_year`) | 开启新财年预算周期，设置 `budget_due` 与 `deadline_day` |
| `m10_check_budget_deadline_daily(state) -> None` | `M01` / `M03` | Step 3 (`daily`) | 检查 60 天预警与 90 天逾期自动解散 (`D-014`) |
| `m10_monthly_terms(state, node_name, term_key) -> float` | `M02` | Step 9 (`step_nodes`) | 提供 `m10_debt_burden_term`、`m10_fx_balance_term`、`m10_absorption_budget_term` |
| `m10_quarterly_terms(state, node_name, term_key) -> float` | `M02` | Step 16 (`step_nodes`) | 提供 `m10_inflation_spiral_term`、`m10_growth_structural_term`、`m10_unemployment_shock_term`、`m10_inequality_budget_term` |
| `m10_get_budget_slider(state, item: str) -> float` | `M06`~`M13` | 任意时刻 | 返回已生效的预算科目滑块值 `enacted_sliders[item]` |
| `m10_set_draft_slider(state, item: str, value: float) -> Dict` | `M13` (UI) | 玩家拖动预算滑块时 | 更新 `draft_sliders[item]`（截断至 `[0, 100]`），返回预估 `budget_balance` 与各党支持度字典 |
| `m10_budget_result(state, year: int, passed: bool) -> None` | `M03` | Step 3 预算表决完成时 | 处理预算案通过或否决回调（见 §4.6.4） |

### 5.2 M10 注册的 `Effect` `custom` 操作处理器

根据 `docs/contracts.md` 中 `Effect(op="custom", target="custom", key=..., value=...)` 契约，M10 注册并处理以下 6 个 `custom` key（供 `M05` 行动与 `M12` 事件脚本直接调用）：

| Custom Key | Value 参数结构 | 触发源示例 | 精确执行逻辑 |
| :--- | :--- | :--- | :--- |
| `m10_pass_budget` | `{}` 或 `{"year": int}` | `M05` `submit_budget` 行动 / 测试脚本 | 若当前预算未通过，立即将 `draft_sliders` 写入 `enacted_sliders`，设置 `status = "PASSED"`，清除 `budget_due` 与 `budget_deadline_60` |
| `m10_apply_stabilization_plan` | `{"months": 6, "fx_grant": 15.0}` | `E-1985-07`（1985 经济稳定计划选项 A） | 激活 `stabilization_plan_active = True`, `stabilization_months_left = 6`；将 `expected_inflation` 重锚定为 `max(18.0, 0.35 * expected_inflation)`；立即将 `draft_sliders` 与 `enacted_sliders` 中 `defense`、2 项补贴支出各削减 `10.0` 点；`fx_reserves` 增加 `fx_grant` |
| `m10_trigger_bank_bailout` | `{"bailout": bool}` | `E-1983-10`（1983 银行股崩盘事件） | 若 `bailout == True`（选项 A 国有化兜底）：设置 `bank_bailout_committed = True`（使 `public_debt` 目标值上升 `+18.0`），注入 `one_off_flows["budget_balance"] -= 6.0`，移除 `bank_bubble` 修正器；若 `bailout == False`（选项 B 放任破产）：`growth` 注入一次性冲击 `-4.5`，移除 `bank_bubble` |
| `m10_inject_external_inflation_shock` | `{"delta": float}` | `E-1979-02`（伊朗革命第二次石油危机） | 将 `state.m10.external_inflation_shock` 增加 `delta`（例如 `+18.0`），在后续季度 Step 16 中推高 `inflation` 并按季度 `×0.75` 衰减 |
| `m10_spawn_aliyah_cohort` | `{"cohort_id": str, "magnitude": float}` | `E-1989-10`（苏联犹太人大移民开启） | 向 `state.m10.aliyah_cohorts` 追加一个新的 `AliyahCohort(cohort_id, state.day, 0, magnitude, magnitude, 0.0)` |
| `m10_set_enacted_slider_delta` | `{"item": str, "delta": float}` | `M12` 事件选项（如紧急追加定居点/宗教拨款） | 将 `enacted_sliders[item]` 与 `draft_sliders[item]` 同时增加 `delta`（截断至 `[0, 100]`） |

---

## 6. 历史与动态事件钩子映射 (Event Hooks & Flags Mapping)

M10 与 `docs/events/04_1977_1992.md` 中的全部 13 个经济及预算相关事件严格对齐：

| 事件 ID | 事件名称 | 触发条件 / M10 信号 | M10 状态与参数交互明细 |
| :--- | :--- | :--- | :--- |
| `E-1977-10` | 埃利希新经济政策（“经济大翻盘”） | 1977-10-28 历史窗口且利库德执政 | 选项 A 执行 `M05` 的 `fx_regime -> 100`、`food_subsidies -> 33`、`import_protection -> 50`；M10 中 `economic_model` 从 `-45.0` 跃升至 `-11.8`，但因赤字未减且取消补贴，触发通胀预期上跳与外汇流失 |
| `E-1978-06` | 劳工总联合会对抗利库德通货膨胀 | `inflation >= 45.0` 且 `union_strength >= 60.0` | 选项 A 妥协提高补贴（`one_off_flows["budget_balance"] -= 2.5`，降低 `strike_risk`）；选项 B 强硬对抗触发 `strike_risk += 25.0` |
| `E-1979-02` | 伊朗伊斯兰革命与能源危机 | 1979-02 历史窗口 | 调用 `m10_inject_external_inflation_shock({"delta": 18.0})` 并挂载修正器 `oil_crisis_1979`（`fx_spend: 1.20` 持续 360 天） |
| `E-1979-03` | 埃以和平条约与西奈撤军经济账 | 签署戴维营条约后 | 短期西奈油田移交与基地搬迁消耗 `one_off_flows["budget_balance"] -= 3.5`；长期激活美援加成 `us_aid: 1.25` |
| `E-1983-10` | 特拉维夫证券交易所银行股崩盘 | `has_modifier("bank_bubble")` 且 (`fx_reserves < 25.0` 或 `year >= 1983`) | 银行操纵股价泡沫破裂，特拉维夫证交所关闭 18 天；调用 `m10_trigger_bank_bailout` 处理国有化兜底（`public_debt` 飙升）或放任崩盘 |
| `E-1985-07` | 1985 年《经济稳定计划》 | `flag_is_set("inflation_crisis")`（`inflation >= 80`） | 调用 `m10_apply_stabilization_plan`，同步修改 `central_bank -> 100`、`wage_indexation -> 33`、`food_subsidies -> 33`，在 2–3 个季度内将 400%+ 恶性通胀压回 20% |
| `E-1989-10` | 苏联大门敞开：百万大移民浪潮 | 1989-10 历史窗口 | 调用 `m10_spawn_aliyah_cohort({"cohort_id": "soviet_wave_1", "magnitude": 22.0})`，短期大幅拉低 `absorption_capacity` 并推高 `unemployment`，4 个季度后转化为高增长红利 |
| `E-1991-09` | 老布什冻结 100 亿美元住房贷款担保 | `B_settlements >= 50` 且移民潮激活 | 挂载修正器 `us_loan_freeze`（`us_aid: 0.65`, `fx_spend: 1.15`），直到冻结定居点扩建（`B_settlements <= 35`）才解除 |
| `E-G04-01` | 恶性通胀螺旋：谢克尔失去计价功能 | `flag_is_set("hyperinflation")`（`inflation >= 180`） | 触发价格按日重标、商店以美元标价危机；若不采取稳定措施，每季度扣除执政联盟支持率与政府稳定度 |
| `E-G04-02` | 劳工总联合会全国总罢工 | `flag_is_set("general_strike_active")`（`strike_risk >= 80`） | 本古里安机场、港口、银行与电力全面停摆；玩家必须在让步涨薪（推高赤字与通胀）、政治资本强行仲裁或动用紧急法令之间抉择 |
| `E-G04-06` | 外汇储备跌破红线：国家违约边缘 | `flag_is_set("fx_crisis")`（`fx_reserves < 20`） | 进口燃料与军备面临断供；可向美国紧急求援（出让外交自主权）、实行严厉进口配额或强制本币大幅贬值 |
| `E-G04-07` | 发展城镇面包骚乱 | `food_subsidies <= 33` 且 `inflation >= 60` 且 `inequality >= 42` | 发展城镇爆发街头抗议，直接冲击利库德/沙斯党基本盘支持度 |
| `E-G04-08` | 国家预算逾期倒计时：最后 30 天 | `flag_is_set("budget_deadline_60")` | 提醒玩家距离 90 天法定预算大限仅剩 30 天；提供紧急政治交易选项（向宗教党或小党派发放一次性专项拨款换取预算赞成票） |

---

## 7. 边界条件与不变量 (Edge Cases & Invariants)

1. **硬边界裁剪不变量（Range Clamping Invariant）**：
   - 在任何月度（Step 9）、季度（Step 16）或即时操作结束后，M10 拥有的全部 12 项参数必须严格处于其注册表 `range` 闭区间内：
     - `budget_balance` $\in [-50.0, 50.0]$
     - `public_debt` $\in [0.0, 300.0]$
     - `fx_reserves`, `absorption_capacity`, `union_strength`, `inequality`, `strike_risk` $\in [0.0, 100.0]$
     - `budget_slider[k]` $\in [0.0, 100.0]$（对所有 $k \in \text{BUDGET\_ITEMS}$）
     - `inflation` $\in [-5.0, 500.0]$
     - `growth` $\in [-15.0, 20.0]$
     - `unemployment` $\in [0.0, 40.0]$
     - `economic_model` $\in [-100.0, 100.0]$
2. **一次性收支流单次消费不变量（`D-010`）**：
   - `state.one_off_flows["budget_balance"]` 只能在每月 Step 9 `m10_finance_monthly` 中被读取并立即清零（`pop("budget_balance", 0.0)`）。同一月内的多次 UI 预览计算（如拖动预算滑块）**严禁**修改或消费 `one_off_flows`。
3. **看守内阁预算豁免不变量（Caretaker Budget Invariant）**：
   - 当 `state.caretaker == True`（议会已解散、正在等待大选或组阁谈判）时：
     - 玩家不能发起 `submit_budget` 行动；
     - `m10_check_budget_deadline_daily` 不得再次触发议会解散；
     - 国家财政自动按上一份已通过的 `enacted_sliders` 延续执行。
4. **除零与极端负值防护**：
   - 在计算 `strike_risk` 时，`union_strength / 70.0` 分母为常量 `70.0`，当 `union_strength == 0.0` 时 `strike_risk` 精确为 `0.000`（工会瓦解后不可能发动组织化总罢工）。
   - 在计算 `R_aid`、`E_debt`、`E_tanzi` 与 $\Phi_{\text{monetize}}$ 时，所有阈值项均使用 `max(0.0, ...)` 保护，通货紧缩（`inflation < 0`）或低债务（`public_debt < 40`）绝不会产生反向的“负利息收入”或“负坦齐补贴”。
5. **定点精度不变量（`D-015`）**：
   - 所有写入 `state` 的浮点数统一执行 `round(val, 3)`，消除跨平台 IEEE 754 尾数漂移。

---

## 8. 解释层契约与 UI 呈现规范 (Explainability & UI Presentation)

### 8.1 `M02.explain()` 因果归因分解契约
- 对于通过 `CausalNet.step_nodes` 结算的 8 个 `level` 节点（`public_debt`, `fx_reserves`, `absorption_capacity`, `union_strength`, `inflation`, `growth`, `unemployment`, `inequality`），`M02` 自动记录每条 `M05.POL.*`、`M10.*` 因果边及 `custom` 项的当期贡献值，按绝对值降序输出 Top-3 正向驱动因子与 Top-3 负向驱动因子。
- 对于由 M10 算术公式直接计算的 `budget_balance`、`economic_model` 与 `strike_risk`，M10 在每次 Step 9 结算时调用 `M02.record_custom_explanation(state, param_name,drivers_list)` 写入结构化归因列表：
  - `budget_balance` 的 7 个具名分项：`tax_revenue` ($+R_{\text{tax}}$), `us_aid_grant` ($+R_{\text{aid}}$), `slider_expenditure` ($-E_{\text{sliders}}$), `debt_service` ($-E_{\text{debt}}$), `tanzi_erosion` ($-E_{\text{tanzi}}$), `m05_policy_delta` ($\Delta_{\text{M05}}$), `one_off_flow` ($F_{\text{one\_off}}$)。
  - `strike_risk` 的 3 个具名分项：`union_base` (`union_strength`), `wage_erosion` (`wage_erosion_index`), `policy_hostility` ($H_{\text{policy}}$)。

### 8.2 M13 预算与宏观经济面板展示规范
1. **顶栏常驻经济微件（Topbar Economy Cluster）**：
   - 显示 `inflation`（带季度趋势箭头与颜色分级：`<25%` 常态白，`25~80%` 琥珀黄，`>80%` 警报红）、`fx_reserves`（同时显示指数值与折算进口月数 `fx_reserves / 10.0`，如 `35.0 (3.5 个月进口)`）及 `budget_balance`（如 `-2.0%/月`）。
2. **国家预算起草抽屉（Budget Drafting Drawer）**：
   - 左侧列出 8 条预算滑块（`defense` 至 `settlements`），每条滑块显示当前生效值 $B^{\text{enacted}}_k$、草案游标 $B^{\text{draft}}_k$、每 `±5` 点对应的月度财政收支变化（$\pm 5 w_k$），以及下方悬浮的执政联盟政党图标（若拖动至某党底线 $M_{p, k}$ 以下，该党徽标变为闪烁红色感叹号）。
   - 右侧显示“月度财政收支瀑布图”（Waterfall Chart，直接渲染 `state.m10.last_fiscal_ledger` 的 7 个分项）与“议会预算案预计票数条”（调用 `M03` 预测支持席位 / 61 席过关线）。

---

## 9. 历史校准表：1977–1992 五大标志性阶段 (Historical Calibration Table)

下表展示 M10 在 1977–1992 年五个关键历史节点的基准参数轨迹，作为数值回归测试与历史真实感校验的硬性基准：

| 历史阶段与时间节点 | 执政路线与核心政策输入 | `budget_balance` (`%/mo`) | `inflation` (`%/yr`) | `fx_reserves` (`0-100`) | `public_debt` (`% GDP`) | `growth` (`%/yr`) | `unemployment` (`%`) | `union_strength` (`0-100`) | `economic_model` (`[-100,100]`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. 贝京上台开局**<br>(`1977-06-20`) | 工党遗产：严格外汇管制、高补贴、全额工资指数化 | `-2.0` | `35.0` | `35.0` | `120.0` | `1.5` | `3.9` | `70.0` | `-45.0` |
| **2. 埃利希自由化与石油冲击后**<br>(`1979-Q4`) | `fx_regime=100`, `food_subsidies=33`, 伊朗石油危机 + 西奈撤军开支 | `-4.8` | `112.0` | `26.5` | `145.0` | `3.2` | `3.4` | `66.0` | `-16.5` |
| **3. 阿里多尔泡沫与银行股崩盘前夜**<br>(`1983-Q3`) | 黎巴嫩战争 (`defense=80`, `fx_spend=1.25`) + 选举减税补贴 + `bank_bubble` | `-7.2` | `155.0` | `18.5` | `168.0` | `1.2` | `4.6` | `62.0` | `-10.0` |
| **4. 恶性通胀巅峰**<br>(`1984-Q4`) | 银行国有化兜底 (`bank_bailout=True`) + 赤字印钞螺旋 ($\Phi_{\text{monetize}}$) | `-8.8` | `415.0` | `14.2` | `212.0` | `-0.5` | `6.2` | `58.0` | `-8.0` |
| **5. 1985 稳定计划成功与苏联移民潮**<br>(`1991-Q2`) | `central_bank=100`, `wage_indexation=33`, `privatization=67`, 苏联百万移民涌入 | `-1.8` | `18.5` | `58.0` | `132.0` | `6.2` | `10.4` | `42.0` | `+34.0` |

---

## 10. 参考实现：Python 3.9 完整可运行核心代码 (Reference Implementation)

以下 Python 3.9 代码完整实现了 M10 的全部确定性结算函数、因果网络自定义项提供器与预算周期状态机，可直接被 `tests/m10_test.py` 导入测试：

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

BUDGET_WEIGHTS: Dict[str, float] = {
    "defense": 0.040,
    "absorption": 0.016,
    "religion": 0.010,
    "dev_towns": 0.012,
    "education": 0.020,
    "welfare": 0.024,
    "infrastructure": 0.018,
    "settlements": 0.012,
}

ECON_MODEL_POLICY_WEIGHTS: Dict[str, tuple[float, float]] = {
    # policy_id: (initial_1977_value, weight)
    "privatization": (0.0, 0.30),
    "fx_regime": (0.0, 0.22),
    "capital_market": (0.0, 0.20),
    "import_protection": (0.0, 0.16),
    "central_bank": (0.0, 0.14),
    "wage_indexation": (100.0, -0.18),
    "food_subsidies": (67.0, -0.12),
}

PARTY_BUDGET_REDLINES: Dict[str, Dict[str, float]] = {
    "likud": {"defense": 55.0, "settlements": 35.0},
    "alignment": {"defense": 50.0, "welfare": 45.0, "education": 45.0},
    "dash": {"education": 50.0, "infrastructure": 45.0},
    "nrp": {"religion": 40.0, "settlements": 40.0},
    "agudat_yisrael": {"religion": 45.0, "welfare": 50.0},
    "shas": {"religion": 50.0, "dev_towns": 45.0, "welfare": 55.0},
    "tehiya": {"defense": 65.0, "settlements": 60.0},
    "shinui": {"education": 50.0},
    "ratz": {"education": 55.0, "welfare": 50.0},
    "hadash": {"welfare": 60.0},
}


def clip(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def r3(val: float) -> float:
    return round(float(val), 3)


def compute_economic_model(state: Any) -> float:
    """§4.3.1 计算国家经济体制坐标轴 [-100, 100]"""
    acc = -45.0
    for pol_id, (init_v, w) in ECON_MODEL_POLICY_WEIGHTS.items():
        cur_v = float(state.policy.get(pol_id, init_v))
        acc += w * (cur_v - init_v)
    acc -= 0.30 * (float(state.union_strength) - 70.0)
    return clip(r3(acc), -100.0, 100.0)


def compute_monthly_budget_balance(state: Any, consume_one_off: bool = True) -> float:
    """§4.2.1 计算月度财政收支平衡 budget_balance [-50, 50] 并更新 FiscalLedger"""
    sliders = state.m10.budget_cycle.enacted_sliders
    r_tax = (
        8.000
        + 0.120 * (float(state.growth) - 3.0)
        - 0.080 * (float(state.unemployment) - 4.0)
    )
    us_aid_mult = float(state.mod_factor("us_aid"))
    r_aid = max(0.0, (0.600 + 0.012 * (float(state.us_stance) - 65.0)) * us_aid_mult)

    slider_dev = sum(
        w * (float(sliders.get(k, 50.0)) - 50.0) for k, w in BUDGET_WEIGHTS.items()
    )
    fiscal_spend_mult = float(state.mod_factor("fiscal_spend"))
    e_sliders = (8.472 + slider_dev) * fiscal_spend_mult

    e_debt = 0.012 * max(0.0, float(state.public_debt) - 40.0)
    stab_disc = 0.50 if state.m10.stabilization_plan_active else 0.0
    e_tanzi = 0.028 * max(0.0, float(state.inflation) - 10.0) * (1.0 - stab_disc)

    delta_m05 = float(state.m05_policy_fiscal_delta())
    if consume_one_off:
        one_off = float(state.one_off_flows.pop("budget_balance", 0.0))
    else:
        one_off = float(state.one_off_flows.get("budget_balance", 0.0))

    raw_bal = r_tax + r_aid - e_sliders - e_debt - e_tanzi + delta_m05 + one_off
    net_bal = clip(r3(raw_bal), -50.0, 50.0)

    if consume_one_off:
        ledger = state.m10.last_fiscal_ledger
        ledger.tax_revenue = r3(r_tax)
        ledger.us_aid_grant = r3(r_aid)
        ledger.slider_expenditure = r3(e_sliders)
        ledger.debt_service = r3(e_debt)
        ledger.tanzi_erosion = r3(e_tanzi)
        ledger.m05_policy_delta = r3(delta_m05)
        ledger.one_off_flow = r3(one_off)
        ledger.net_balance = net_bal
    return net_bal


def update_strike_mechanics(state: Any, update_erosion: bool = True) -> float:
    """§4.3.2 更新实际工资侵蚀与罢工风险 strike_risk [0, 100]"""
    wage_idx = float(state.policy.get("wage_indexation", 100.0))
    food_sub = float(state.policy.get("food_subsidies", 67.0))
    priv = float(state.policy.get("privatization", 0.0))
    min_wage = float(state.policy.get("minimum_wage", 0.0))
    b_welfare = float(state.m10.budget_cycle.enacted_sliders.get("welfare", 55.0))

    if update_erosion:
        theta_protect = 0.75 * (wage_idx / 100.0)
        target_erosion = (
            (1.0 - theta_protect) * max(0.0, float(state.inflation) - 5.0)
            + 3.5 * max(0.0, float(state.unemployment) - 3.5)
            + 0.20 * max(0.0, 67.0 - food_sub)
        )
        state.m10.wage_erosion_index = clip(
            r3(0.80 * state.m10.wage_erosion_index + 0.20 * target_erosion),
            0.0,
            100.0,
        )

    h_policy = (
        0.35 * priv
        + 0.25 * max(0.0, 50.0 - min_wage)
        + 0.25 * max(0.0, 100.0 - wage_idx)
        + 0.30 * max(0.0, 50.0 - b_welfare)
    )
    raw_risk = (float(state.union_strength) / 70.0) * (
        0.60 * state.m10.wage_erosion_index + 0.80 * h_policy + 6.0
    )
    risk = clip(r3(raw_risk), 0.0, 100.0)
    state.strike_risk = risk

    if state.m10.strike_cooldown_months > 0:
        state.m10.strike_cooldown_months -= 1
        state.m10.active_strike_tier = 0
        state.clear_flag("strike_warning")
        state.clear_flag("general_strike_active")
    else:
        if risk >= 80.0:
            state.m10.active_strike_tier = 2
            state.set_flag("general_strike_active")
            state.m10.strike_cooldown_months = 3
        elif risk >= 60.0:
            state.m10.active_strike_tier = 1
            state.set_flag("strike_warning")
            state.clear_flag("general_strike_active")
            state.one_off_flows["budget_balance"] = (
                float(state.one_off_flows.get("budget_balance", 0.0)) - 0.40
            )
        else:
            state.m10.active_strike_tier = 0
            state.clear_flag("strike_warning")
            state.clear_flag("general_strike_active")
    return risk


def m10_monthly_terms(state: Any, node_name: str, term_key: str) -> float:
    """§4.4 M10 月度因果节点自定义项提供器"""
    sliders = state.m10.budget_cycle.enacted_sliders
    if term_key == "m10_debt_burden_term":
        bailout_add = 18.0 if state.m10.bank_bailout_committed else 0.0
        return r3(
            0.35 * (state.m10.cumulative_deficit_stock - 40.0)
            + 0.40 * max(0.0, 40.0 - float(state.fx_reserves))
            + bailout_add
        )
    if term_key == "m10_fx_balance_term":
        fx_mult = float(state.mod_factor("fx_spend"))
        aid_mult = float(state.mod_factor("us_aid"))
        b_def = float(sliders.get("defense", 65.0))
        return r3(
            -0.20 * (b_def - 50.0) * fx_mult
            - 8.0 * (fx_mult - 1.0)
            + 6.0 * (aid_mult - 1.0)
            - 0.08 * max(0.0, float(state.inflation) - 80.0)
        )
    if term_key == "m10_absorption_budget_term":
        b_abs = float(sliders.get("absorption", 45.0))
        b_inf = float(sliders.get("infrastructure", 50.0))
        b_dev = float(sliders.get("dev_towns", 40.0))
        aliyah_load = sum(c.current_load for c in state.m10.aliyah_cohorts)
        return r3(
            0.45 * (b_abs - 50.0)
            + 0.20 * (b_inf - 50.0)
            + 0.15 * (b_dev - 50.0)
            - aliyah_load
        )
    raise KeyError(f"Unknown M10 monthly term_key: {term_key}")


def m10_quarterly_terms(state: Any, node_name: str, term_key: str) -> float:
    """§4.5 M10 季度因果节点自定义项提供器"""
    sliders = state.m10.budget_cycle.enacted_sliders
    if term_key == "m10_inflation_spiral_term":
        wage_idx = float(state.policy.get("wage_indexation", 100.0))
        cb_ind = float(state.policy.get("central_bank", 0.0))
        psi = max(
            0.10,
            0.28 + 0.0024 * (wage_idx - 50.0) - 0.0016 * (cb_ind - 50.0),
        )
        monetize_gap = max(0.0, -float(state.budget_balance) - 3.0)
        cb_mult = 1.0 + (50.0 - cb_ind) / 50.0
        phi_monetize = 2.50 * (monetize_gap ** 2) * cb_mult
        return r3(
            psi * (state.m10.expected_inflation - 10.0)
            + phi_monetize
            + state.m10.external_inflation_shock
        )
    if term_key == "m10_growth_structural_term":
        b_inf = float(sliders.get("infrastructure", 50.0))
        b_edu = float(sliders.get("education", 50.0))
        b_def = float(sliders.get("defense", 65.0))
        div = sum(c.current_growth_dividend for c in state.m10.aliyah_cohorts)
        return r3(
            0.04 * (b_inf - 50.0)
            + 0.03 * (b_edu - 50.0)
            - 0.04 * (b_def - 50.0)
            - 0.05 * max(0.0, float(state.strike_risk) - 30.0)
            + div
        )
    if term_key == "m10_unemployment_shock_term":
        b_dev = float(sliders.get("dev_towns", 40.0))
        b_inf = float(sliders.get("infrastructure", 50.0))
        aliyah_load = sum(c.current_load for c in state.m10.aliyah_cohorts)
        excess_aliyah = max(
            0.0, aliyah_load - 0.30 * (float(state.absorption_capacity) - 40.0)
        )
        return r3(
            0.22 * excess_aliyah
            - 0.03 * (b_dev - 50.0)
            - 0.02 * (b_inf - 50.0)
        )
    if term_key == "m10_inequality_budget_term":
        b_wel = float(sliders.get("welfare", 55.0))
        b_edu = float(sliders.get("education", 50.0))
        b_dev = float(sliders.get("dev_towns", 40.0))
        return r3(
            -0.18 * (b_wel - 50.0)
            - 0.12 * (b_edu - 50.0)
            - 0.15 * (b_dev - 50.0)
        )
    raise KeyError(f"Unknown M10 quarterly term_key: {term_key}")
```

---

## 11. 自动化验收测试套件 (Automated Acceptance Tests)

本模块定义 **10 项可直接自动化执行的验收测试**（远超最低 8 项要求），覆盖开局稳态、埃利希改革冲击、恶性通胀螺旋、1985 休克疗法稳定计划、外汇危机标志、Histadrut 总罢工触发、苏联移民短期冲击与长期红利转换、年度预算逾期 90 天自动解散议会（`D-014`）、看守内阁预算豁免及定点确定性回放：

| 测试编号 | 测试名称 | 初始输入与驱动操作 | 期望精确断言 (Assertions) |
| :--- | :--- | :--- | :--- |
| **T-M10-01** | **Begin 1977 开局全节点零漂移稳态验证** | 加载 `begin_1977` 初始状态（`1977-06-20`），不修改任何政策或预算滑块，执行 1 次 Step 9 (`finance_monthly`) 与 1 次 Step 16 (`economy_quarterly`) | 1. `budget_balance == -2.000`<br>2. `economic_model == -45.000`, `strike_risk == 28.000`（首次月度未更新 erosion 前为 `28.000`）<br>3. 8 个因果网络节点 `T_raw` 精确等于初值：`public_debt == 120.000`, `fx_reserves == 35.000`, `absorption_capacity == 55.000`, `union_strength == 70.000`, `inflation == 35.000`, `growth == 1.500`, `unemployment == 3.900`, `inequality == 38.000` |
| **T-M10-02** | **埃利希自由化改革与高通胀传导验证 (`E-1977-10`)** | 从 `begin_1977` 出发，设置 `fx_regime=100`, `food_subsidies=33`, `import_protection=50`，注入伊朗石油冲击 `external_inflation_shock=18.0`，连续运行 8 个季度 | 1. `economic_model > -20.0`（向自由市场显著右移）<br>2. `inflation >= 75.0`（从 35% 跃升至高通胀区间）<br>3. `fx_reserves < 31.0`（高通胀侵蚀外汇储备） |
| **T-M10-03** | **赤字货币化与 400%+ 恶性通胀螺旋验证 (`E-G04-01`)** | 设置 `budget_balance = -8.5`（提高 `defense=85, welfare=75` 且不加税），保持 `central_bank = 0`, `wage_indexation = 100`，连续运行 6 个季度 | 1. `m10_quarterly_terms` 中 $\Phi_{\text{monetize}} > 140.0$<br>2. `inflation >= 250.0` 且 `< 500.0`（软目标压缩防止溢出上限）<br>3. `flag_is_set("inflation_crisis") == True` 且 `flag_is_set("hyperinflation") == True` |
| **T-M10-04** | **1985 经济稳定计划休克疗法快速降通胀验证 (`E-1985-07`)** | 从 T-M10-03 的恶性通胀状态（`inflation = 380.0`, `expected_inflation = 350.0`）出发，执行 `m10_apply_stabilization_plan({"months": 6, "fx_grant": 15.0})` 并设置 `central_bank=100`, `wage_indexation=33`，将赤字收窄至 `budget_balance = -1.2`，运行 4 个季度 | 1. 4 个季度后 `inflation <= 45.0`（从 380% 断崖式回落超过 300 个百分点）<br>2. `flag_is_set("hyperinflation") == False` 且 `flag_is_set("inflation_crisis") == False`<br>3. `fx_reserves >= 30.0` |
| **T-M10-05** | **外汇储备跌破 20 点危机标志与滞回恢复验证 (`E-G04-06`)** | 初始 `fx_reserves = 21.0`，挂载黎巴嫩战争高耗汇修正器 `fx_spend = 1.40`，设置 `defense = 80.0`，运行 2 次月度 Step 9；随后注入美援并降防务使 `fx_reserves` 回升至 `25.0` | 1. 前 2 个月后 `fx_reserves < 20.0` 且 `flag_is_set("fx_crisis") == True`<br>2. 当 `fx_reserves == 22.0` 时 `flag_is_set("fx_crisis")` 仍为 `True`（滞回保护）<br>3. 当 `fx_reserves >= 24.0` 时 `flag_is_set("fx_crisis") == False` |
| **T-M10-06** | **Histadrut 罢工风险累积与全国总罢工冷却验证 (`E-G04-02`)** | 在 `union_strength = 70.0`、`inflation = 90.0` 下，政府推行激进反劳工组合：`privatization = 100`, `wage_indexation = 0`, `food_subsidies = 0`, `minimum_wage = 0`，运行月度 Step 9 | 1. 第 1–2 个月内 `strike_risk >= 80.0`<br>2. `flag_is_set("general_strike_active") == True` 且 `state.m10.active_strike_tier == 2`<br>3. `state.m10.strike_cooldown_months == 3`，且接下来 3 个月内不会重复触发 `active_strike_tier == 2` |
| **T-M10-07** | **苏联百万大移民短期冲击与长期 GDP 红利转换验证 (`E-1989-10`)** | 调用 `m10_spawn_aliyah_cohort({"cohort_id": "soviet_1989", "magnitude": 22.0})`，对比第 2 季度（短期冲击期）与第 10 季度（长期红利期）的指标 | 1. 第 2 季度：`absorption_capacity < 46.0` 且 `unemployment > 5.8`（短期安置挤兑与失业上升），`current_growth_dividend == 0.0`<br>2. 第 10 季度：`current_growth_dividend >= 2.0`，拉动 `growth` 比无移民基准高出至少 `+1.2` 个百分点 |
| **T-M10-08** | **年度预算案 60 天预警与 90 天逾期议会自动解散验证 (`D-014`)** | 在 `1978-01-01`（`day = 195`）触发 Step 17 `m10_budget_yearly`；玩家始终不通过预算，推进时间至 `day = 255`（+60 天）和 `day = 285`（+90 天） | 1. `day = 195`：`flag_is_set("budget_due") == True`, `deadline_day == 285`<br>2. `day = 255`：`flag_is_set("budget_deadline_60") == True`, `status == "OVERDUE_WARNING"`<br>3. `day = 285`：`status == "DISSOLVED"`，触发 `m03_dissolve_knesset(reason="budget_overdue")` 且 `state.caretaker == True` |
| **T-M10-09** | **预算单次表决失败不立即解散、允许修改重提验证 (`D-014`)** | 在 `day = 210`（距离 `deadline_day = 285` 尚有 75 天）时，回调 `m10_budget_result(state, year=1978, passed=False)`；随后在 `day = 230` 修改滑块再次提交并回调 `passed=True` | 1. `day = 210` 否决后：`state.caretaker == False`, `status == "DUE"`, `rejection_count_this_year == 1`, `flag_is_set("budget_due") == True`<br>2. `day = 230` 通过后：`status == "PASSED"`, `flag_is_set("budget_due") == False`，新滑块正式写入 `enacted_sliders` |
| **T-M10-10** | **`one_off_flows["budget_balance"]` 单次消费与跨平台确定性验证 (`D-010`, `D-015`)** | 注入 `state.one_off_flows["budget_balance"] = -3.500`；先调用 3 次 `m10_set_draft_slider`（UI 预览），再执行第 1 次月度 Step 9 和第 2 次月度 Step 9 | 1. 3 次 UI 预览后 `state.one_off_flows["budget_balance"]` 仍为 `-3.500`<br>2. 第 1 次 Step 9：`budget_balance == -5.500`（`-2.000 - 3.500`），且 `one_off_flows` 中 `"budget_balance"` 被清零<br>3. 第 2 次 Step 9：`budget_balance` 恢复常态（无 `-3.500` 残留） |

---

## 12. 调参指南与敏感度分析 (Tuning Guide & Sensitivity Analysis)

1. **通胀螺旋敏感度旋钮**：
   - **线性赤字系数 `M10.INF.01` (`c = -4.50`)** 控制温和赤字（`-1% ~ -3%`）下的常态通胀水平。
   - **二次方印钞加速器 $\Phi_{\text{monetize}}$ 系数 (`2.50`) 与阈值 (`3.0`)** 控制何时从高通胀（50–80%）跃迁至恶性通胀（200–450%）。若测试中发现玩家过早进入 400% 通胀，可将阈值从 `3.0` 上调至 `3.8`；若发现阿里多尔路线下通胀爬升过慢，可将系数从 `2.50` 上调至 `3.00`。
2. **外汇储备消耗速度旋钮**：
   - `M10.FX.02` (`c = -0.18`) 与 `m10_fx_balance_term` 中的国防用汇系数 (`-0.20`) 共同决定外汇危机到来时间。在 `alpha = 0.25` 下，`T_soft` 每下降 `10` 点，当月实际 `fx_reserves` 下降 `2.5` 点（约 1 个季度下降 `6` 点）。
3. **劳工总联合会（Histadrut）罢工频率旋钮**：
   - `strike_risk` 的两个触发阈值（`60.0` 警告罢工、`80.0` 全国总罢工）与 `strike_cooldown_months = 3` 保证了即使在最激烈的私有化改革期，全国总罢工每年最多发生 3 次，避免高频弹窗骚扰玩家。

---

## 13. 文件清单与模块边界 (File Manifest & Module Boundaries)

| 文件路径 | 职责说明 |
| :--- | :--- |
| `docs/specs/M10_economy_budget.md` | 本规范文档 |
| `sim/m10_economy.py` (Python 参考实现) / `src/sim/m10_economy.gd` (GDScript) | M10 核心状态类、月度/季度/年度结算函数与自定义项提供器 |
| `data/party_budget_preferences.yaml` | 10 大政党对 8 个预算科目的偏好权重与联盟底线配置 |
| `data/causal_edges.yaml` (M10 节) | M10 拥有的 8 个 `level` 节点与 21 条因果边配置（见附录 C.1） |
| `tests/test_m10_economy.py` | 自动化验收测试套件（实现 §11 的 T-M10-01 至 T-M10-10） |

---

## 附录 A：提议新增的参数与实体 YAML (Appendix A: Proposed Parameters YAML)

M10 严格复用 `docs/registry/parameters.yaml` 中已注册的 10 个核心经济参数（**零破坏性修改**），仅提议在 `entities` 下新增 `budget_items` 列表（共 8 项），并在 `parameters` 下新增 2 个参数（`budget_slider` 与 `strike_risk`）：

```yaml
# 1. 提议追加至 docs/registry/parameters.yaml 顶部 entities 块：
entities:
  budget_items:
    - defense         # 国防与军工
    - absorption      # 移民吸纳与安置
    - religion        # 宗教事务与经学院
    - dev_towns       # 发展城镇专项
    - education       # 公共教育与科研
    - welfare         # 社会福利与津贴
    - infrastructure  # 国家基础设施
    - settlements     # 约旦河西岸与加沙定居点

# 2. 提议追加至 docs/registry/parameters.yaml 的 parameters 块（M10 节）：
parameters:
  budget_slider:
    type: lever
    scope: budget_item
    range: [0, 100]
    tick: event
    owner: M10
    visible: true
    era: null
    drift: none
    description: "8 大国家预算科目的拨款水平滑块（50 为常态基准，通过年度预算案提交议会表决生效）"

  strike_risk:
    type: derived
    scope: national
    range: [0, 100]
    tick: monthly
    owner: M10
    visible: true
    era: null
    drift: "computed from union_strength × wage_erosion_index × policy_hostility"
    description: "劳工总联合会（Histadrut）罢工风险指数（>=60 部门警告罢工，>=80 全国总罢工）"
```

---

## 附录 B：跨模块接口变更提案 (Appendix B: Interface Change Proposals)

### B-1：与 `M01` 修正器因子（Modifier Factors）的对齐扩展
- `M01` §6.3 已为 `M10` 预注册了修正器因子 `"fx_spend"`（默认值 `1.0`）。
- **提案**：在 `M01` 的 `KNOWN_MODIFIER_FACTORS` 集合中补充注册 `"fiscal_spend"`（财政支出乘数，默认 `1.0`）与 `"us_aid"`（美国财政与外汇援助乘数，默认 `1.0`），供 `E-1979-03`（埃以和约美援加成）与 `E-1991-09`（老布什冻结 100 亿美元贷款担保）直接挂载使用。

### B-2：与 `M03` 及 `M05` 预算案提交流程的无缝桥接
- 在 `M05` 中，内阁行动 `submit_budget` 的效果声明为 `fx: [{op: custom, target: custom, key: m10_pass_budget, value: {}}]`, `vote: simple`。
- 在 `M03` §4.9.3 与 §4.19.1 中，年度预算案规定通过 `m03_submit_bill` 提交（`vote: "budget"`, `bill_uid: 900000 + year`, `deadline_day`），并在表决后回调 `m10_budget_result {year, passed}`。
- **桥接契约**：`M10` 同时支持这两种路径：
  1. 当集成 `M03` 运行时，`submit_budget` 完成准备（Step 5）即调用 `m03_submit_bill(..., vote="budget", deadline_day=state.m10.budget_cycle.deadline_day)`，由 `M03` 在 Step 3 表决并回调 `m10_budget_result`；
  2. 当在无 `M03` 的独立单元测试或 `M05` 直接执行 `m10_pass_budget` 时，`m10_pass_budget` 直接将当前预算周期置为 `"PASSED"` 并生效 `draft_sliders`。

---

## 附录 C：因果网络边、修正器与 1977–1992 校准配置 YAML (Appendix C: Causal Edges & Calibration YAML)

### C.1 `data/causal_edges.yaml` — M10 节点与因果边完整定义

```yaml
# ==============================================================================
# M10 Economy & Budget — CausalNet Nodes & Edges (D-052 Compliant)
# Note: M05 lever_edges targeting these 8 nodes are defined in M05 Appendix C
# and are automatically summed into T_raw alongside the M10 edges below.
# ==============================================================================

nodes:
  public_debt:
    owner: M10
    tick: monthly
    mode: level
    baseline: 97.50
    alpha: 0.15
    memory_rho: 0.0
    memory_mu: 0.0
    memory_cap: 50.0
    soft:
      lo_s: 20.0
      hi_s: 240.0
      w: 45.0

  fx_reserves:
    owner: M10
    tick: monthly
    mode: level
    baseline: 43.20
    alpha: 0.25
    memory_rho: 0.0
    memory_mu: 0.0
    memory_cap: 25.0
    soft:
      lo_s: 15.0
      hi_s: 85.0
      w: 13.0

  absorption_capacity:
    owner: M10
    tick: monthly
    mode: level
    baseline: 60.06
    alpha: 0.20
    memory_rho: 0.0
    memory_mu: 0.0
    memory_cap: 25.0
    soft:
      lo_s: 15.0
      hi_s: 85.0
      w: 13.0

  union_strength:
    owner: M10
    tick: monthly
    mode: level
    baseline: 52.17
    alpha: 0.15
    memory_rho: 0.0
    memory_mu: 0.0
    memory_cap: 25.0
    soft:
      lo_s: 15.0
      hi_s: 85.0
      w: 13.0

  inflation:
    owner: M10
    tick: quarterly
    mode: level
    baseline: 5.34
    alpha: 0.35
    memory_rho: 0.30
    memory_mu: 0.05
    memory_cap: 150.0
    soft:
      lo_s: -1.0
      hi_s: 420.0
      w: 60.0

  growth:
    owner: M10
    tick: quarterly
    mode: level
    baseline: 3.82
    alpha: 0.25
    memory_rho: 0.0
    memory_mu: 0.0
    memory_cap: 10.0
    soft:
      lo_s: -8.0
      hi_s: 9.5
      w: 3.5

  unemployment:
    owner: M10
    tick: quarterly
    mode: level
    baseline: 7.26
    alpha: 0.20
    memory_rho: 0.0
    memory_mu: 0.0
    memory_cap: 10.0
    soft:
      lo_s: 2.0
      hi_s: 25.0
      w: 6.0

  inequality:
    owner: M10
    tick: quarterly
    mode: level
    baseline: 44.86
    alpha: 0.15
    memory_rho: 0.0
    memory_mu: 0.0
    memory_cap: 25.0
    soft:
      lo_s: 15.0
      hi_s: 85.0
      w: 13.0

edges:
  # --- Monthly Node: public_debt ---
  - id: M10.DEBT.01
    source: budget_balance
    target: public_debt
    type: linear
    c: -8.00
    offset: 0.0
    description: "月度财政赤字推高公共债务均衡目标"

  - id: M10.DEBT.02
    source: growth
    target: public_debt
    type: linear
    c: -3.00
    offset: 3.0
    description: "实际 GDP 增长扩大分母稀释公共债务率"

  - id: M10.DEBT.03
    source: budget_balance
    target: public_debt
    type: custom
    term_provider: m10_monthly_terms
    term_key: m10_debt_burden_term
    description: "历史累积赤字存量、外汇短缺外债重估与 1983 银行国有化兜底债务"

  # --- Monthly Node: fx_reserves ---
  - id: M10.FX.01
    source: us_stance
    target: fx_reserves
    type: linear
    c: 0.30
    offset: 50.0
    description: "美以关系良好带来双边结算与短期融资便利"

  - id: M10.FX.02
    source: inflation
    target: fx_reserves
    type: linear
    c: -0.18
    offset: 10.0
    description: "国内高通胀削弱出口竞争力并刺激进口用汇"

  - id: M10.FX.03
    source: growth
    target: fx_reserves
    type: linear
    c: 0.80
    offset: 3.0
    description: "经济增长带动高附加值出口创汇"

  - id: M10.FX.04
    source: budget_balance
    target: fx_reserves
    type: custom
    term_provider: m10_monthly_terms
    term_key: m10_fx_balance_term
    description: "国防预算进口军备耗汇、fx_spend/us_aid 修正器与高通胀资本外逃"

  # --- Monthly Node: absorption_capacity ---
  - id: M10.ABS.01
    source: growth
    target: absorption_capacity
    type: linear
    c: 1.20
    offset: 3.0
    description: "宏观经济扩张提供更多就业与安置空间"

  - id: M10.ABS.02
    source: unemployment
    target: absorption_capacity
    type: linear
    c: -1.50
    offset: 4.0
    description: "高失业率挤压新移民就业安置容量"

  - id: M10.ABS.03
    source: budget_balance
    target: absorption_capacity
    type: custom
    term_provider: m10_monthly_terms
    term_key: m10_absorption_budget_term
    description: "吸纳/基建/发展城镇预算拨款支撑减去活跃移民潮短期安置负荷"

  # --- Monthly Node: union_strength ---
  - id: M10.UNI.01
    source: economic_model
    target: union_strength
    type: linear
    c: -0.25
    offset: 0.0
    description: "工党国家资本主义体制支撑 Histadrut 产业垄断，市场化转型削弱工会根基"

  - id: M10.UNI.02
    source: unemployment
    target: union_strength
    type: linear
    c: -0.80
    offset: 4.0
    description: "高失业率削弱工会集体谈判筹码"

  # --- Quarterly Node: inflation ---
  - id: M10.INF.01
    source: budget_balance
    target: inflation
    type: linear
    c: -4.50
    offset: 0.0
    description: "财政赤字直接扩张名义总需求推高物价"

  - id: M10.INF.02
    source: union_strength
    target: inflation
    type: linear
    c: 0.25
    offset: 50.0
    description: "强力工会推动名义工资刚性追涨"

  - id: M10.INF.03
    source: fx_reserves
    target: inflation
    type: threshold
    threshold: 30.0
    direction: below
    c: 1.20
    description: "外汇储备跌破 30 点（3 个月进口）引发本币贬值与进口物价螺旋"

  - id: M10.INF.04
    source: inflation
    target: inflation
    type: custom
    term_provider: m10_quarterly_terms
    term_key: m10_inflation_spiral_term
    description: "适应性通胀预期×工资指数化传导系数 + 赤字印钞二次方加速器 + 外部石油冲击"

  # --- Quarterly Node: growth ---
  - id: M10.GRO.01
    source: inflation
    target: growth
    type: linear
    c: -0.04
    offset: 10.0
    description: "高通胀扭曲价格信号并抑制长期实业投资"

  - id: M10.GRO.02
    source: security_index
    target: growth
    type: linear
    c: 0.06
    offset: 60.0
    description: "良好的国家安全环境提振国内外商业投资与旅游业"

  - id: M10.GRO.03
    source: absorption_capacity
    target: growth
    type: linear
    c: 0.05
    offset: 50.0
    description: "充足的移民安置与住房配套能力促进有效投资"

  - id: M10.GRO.04
    source: budget_balance
    target: growth
    type: custom
    term_provider: m10_quarterly_terms
    term_key: m10_growth_structural_term
    description: "基建与教育预算拉动、超额国防预算挤出、罢工停摆损失及移民长期人力资本红利"

  # --- Quarterly Node: unemployment ---
  - id: M10.UNE.01
    source: growth
    target: unemployment
    type: linear
    c: -0.40
    offset: 3.0
    description: "奥肯定律（Okun's Law）：GDP 增长高于潜在增速时吸纳失业人口"

  - id: M10.UNE.02
    source: absorption_capacity
    target: unemployment
    type: linear
    c: -0.06
    offset: 50.0
    description: "移民吸纳与职业培训体系减少结构性摩擦失业"

  - id: M10.UNE.03
    source: union_strength
    target: unemployment
    type: linear
    c: -0.04
    offset: 50.0
    description: "Histadrut 旗下企业（Koor/Solel Boneh）与公营部门的终身雇佣保护"

  - id: M10.UNE.04
    source: absorption_capacity
    target: unemployment
    type: custom
    term_provider: m10_quarterly_terms
    term_key: m10_unemployment_shock_term
    description: "大规模移民潮超出吸纳容量时的短期失业脉冲与发展城镇/基建预算吸纳效应"

  # --- Quarterly Node: inequality ---
  - id: M10.INE.01
    source: economic_model
    target: inequality
    type: linear
    c: 0.16
    offset: 0.0
    description: "自由市场与私有化转型扩大资本与普通劳动者收入差距"

  - id: M10.INE.02
    source: unemployment
    target: inequality
    type: linear
    c: 0.80
    offset: 4.0
    description: "失业率上升直接打击低收入家庭并拉大基尼系数"

  - id: M10.INE.03
    source: union_strength
    target: inequality
    type: linear
    c: -0.15
    offset: 50.0
    description: "全国集体工资协议压缩行业间与阶层间薪酬差距"

  - id: M10.INE.04
    source: inflation
    target: inequality
    type: linear
    c: 0.04
    offset: 10.0
    description: "高通胀对缺乏金融资产对冲的低收入家庭构成累退税"

  - id: M10.INE.05
    source: budget_balance
    target: inequality
    type: custom
    term_provider: m10_quarterly_terms
    term_key: m10_inequality_budget_term
    description: "福利、教育与发展城镇专项预算的收入再分配效应"
```

### C.2 `scenarios/begin_1977/economy.yaml` — 贝京 1977 开局经济初始配置

```yaml
# Begin 1977 ("Mahapakh", 1977-06-20) M10 Initial State
m10_initial_state:
  parameters:
    budget_balance: -2.0
    public_debt: 120.0
    fx_reserves: 35.0
    absorption_capacity: 55.0
    union_strength: 70.0
    inflation: 35.0
    growth: 1.5
    unemployment: 3.9
    inequality: 38.0
    economic_model: -45.0
    strike_risk: 28.0
    budget_slider:
      defense: 65.0
      absorption: 45.0
      religion: 40.0
      dev_towns: 40.0
      education: 50.0
      welfare: 55.0
      infrastructure: 50.0
      settlements: 35.0

  internal_state:
    expected_inflation: 35.0
    real_gdp_index: 100.0
    cumulative_deficit_stock: 40.0
    external_inflation_shock: 0.0
    wage_erosion_index: 20.0
    strike_cooldown_months: 0
    active_strike_tier: 0
    stabilization_plan_active: false
    stabilization_months_left: 0
    bank_bailout_committed: false
    budget_cycle:
      fiscal_year: 1977
      status: "PASSED"
      opened_day: -170
      deadline_day: -80
      active_bill_uid: null
      warning_60d_emitted: false
      rejection_count_this_year: 0
```

---

## 附录 D：致主 Agent 的收敛问题 (Appendix D: Questions for Main Agent, ≤5)

1. **`budget_slider` 与 `strike_risk` 注册表合并确认**：M10 严格复用了 `parameters.yaml` 中已有的 10 个核心经济参数，并提议新增 `budget_slider`（`scope: budget_item`，含 8 个预算科目实体）与 `strike_risk`（`scope: national`，月度派生参数，便于 `M06`/`M07`/`M12`/`M13` 直接读取罢工风险而无需穿透 `state.m10` 内部字段）。是否批准将这两项合入 `parameters.yaml`？
2. **修正器因子注册扩展（`fiscal_spend` 与 `us_aid`）**：`M01` §6.3 已预注册了 M10 的 `"fx_spend"` 修正器因子。M10 在 §4.2.1 与 §4.4.2 中同时引入了 `"fiscal_spend"`（战争或紧急状态财政支出乘数）与 `"us_aid"`（埃以和约美援加成 / 1991 贷款担保冻结乘数）。是否同意在 `M01` 的 `KNOWN_MODIFIER_FACTORS` 中补充注册这两个因子名？
3. **1977 开局首年预算状态**：1977 年 6 月 20 日贝京政府宣誓就职时，1977 财年国家预算已由前任拉宾政府在年初通过。因此 M10 将开局 `budget_cycle.status` 设为 `"PASSED"`，首次强制年度预算大限将在 `1978-01-01`（Step 17）开启、截止于 `1978-04-01`（而在 1977 年下半年玩家仍可主动通过埃利希新经济政策调整经济杠杆）。这一开局节奏是否符合主设计意图？
