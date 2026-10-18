# Phase 3B：静态因果图拓扑、行动反单货币与事件选项张力审计报告

> **审计范围**：`data/causal_edges.yaml`（50 参数节点族 / 186 因果边）、`data/policies.yaml`（76 政策拉杆 / 313 政策效应）、`data/actions.yaml`（104 政治/军事/经济/外交行动）、`data/events/*.yaml`（6 个事件文件共 396 个编译事件 / 283 个抉择点 / 858 个选项）、`sim/bots.py`（7 个自动化策略 Bot）。
> **验证工具**：`tools/validate_static_tension.py`、`tools/validate_events.py`、`sim/bots.py`。

---

## 一、核心审计结论总览（Executive Scorecard）

| 审计维度 | 合同/基准要求 | 审计实测结果 | 状态 |
| :--- | :--- | :--- | :---: |
| **因果图节点规模（R13）** | $\ge 150$ 个节点 | **264 个展开节点**（188 参数实例 + 76 政策拉杆） | **PASS** |
| **因果图展开边规模（R13）** | $\ge 600$ 条有向边 | **681 条展开有向边**（340 因果边 + 341 政策效应边） | **PASS** |
| **惯性/延迟覆盖率（R13）** | $\ge 40\%$ 边含 `inertia`/`delay`/`habit` | **54.1%**（不含全部 `level` 节点的指数平滑 $\alpha \in [0.02, 0.35]$） | **PASS** |
| **选民集团输入边密度（R13）** | 8 个选民集团各 $\ge 5$ 条输入边 | 最小值 **12 条**（`russian`），最大值 **34 条**（`liberal_middle`） | **PASS** |
| **政策拉杆多维效应（R13）** | 每项政策 $\ge 3$ 个效应目标 | 最小值 **3 个**（76/76 项政策达标） | **PASS** |
| **正反馈环路增益上限（S5/R13）** | 100% 正反馈环 $|G| < 0.50$ 且 $\ge 2$ 阻尼机制 | 最大正环增益 $|G| = \mathbf{0.350} < 0.50$，全部正环具 $\ge 2$ 重阻尼 | **PASS** |
| **`centralization ↔ rule_of_law` 增益（M13）** | 耦合环路增益 $|G| \le 0.30$ | $|G| = |-0.60| \times |-0.20| = \mathbf{0.120} \le 0.30$ | **PASS** |
| **行动反单货币（Paradox M1/M2/S7）** | 仅消耗 PC 的行动占比 $\le 50\%$ | **8.7%**（9/104，且均为 `minor`/常规行动；34/34 `major` 行动 100% 复合代价） | **PASS** |
| **事件“白送”支配选项（Free Lunch）** | `NO_NEG == 0`（0 无代价净赚选项） | **0 / 858**（100% 选项具备明确负向代价或风险权衡） | **PASS** |
| **事件“纯陷阱”被支配选项（Pure Trap）** | `NO_POS == 0`（0 无收益纯亏选项） | **0 / 858**（100% 选项具备明确正向收益或止损回报） | **PASS** |
| **极端选项长期净负铁律（X1 / V-24）** | 100% `extreme` 选项长期净效用 $< 0$ 且低于温和选项 | **19 / 19 达标**（100% 含 `rule_of_law`/`intl_legitimacy` 惩罚与长期修正器代价） | **PASS** |
| **以方暴行三阶段结构合规（V-14）** | 事前 `predecision`（隐藏乘数+风险提示）→ 被动暴行 → 事后追责 | **14 / 14 完整链条 100% 合规**（覆盖 1948–2006 全部暴行/重大事故链） | **PASS** |
| **7 策略 Bot 决策分化度（E7）** | 不同意识形态 Bot 在事件与行动上显著分化 | 鸽派 vs 强人集权派事件分歧率 **83.6%**，修正派 vs 鸽派分歧率 **81.6%** | **PASS** |

---

## 二、因果图拓扑与反馈环路稳定性审计（Causal Graph & Feedback Loops）

### 2.1 选民集团（Voter Blocs）因果输入边分布

| 选民集团 Key | 中文名称 | 因果图输入边数 | 政策效应输入边数 | 总输入边数 | 基准要求（$\ge 5$） |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `liberal_middle` | 世俗自由派中产 | 13 | 21 | **34** | PASS |
| `religious_zionist` | 宗教锡安主义者 | 10 | 21 | **31** | PASS |
| `mizrahi` | 米兹拉希传统大众 | 12 | 16 | **28** | PASS |
| `haredi` | 哈雷迪正统派 | 8 | 19 | **27** | PASS |
| `arab_citizens` | 阿拉伯公民 | 10 | 17 | **27** | PASS |
| `labor_ashkenazi` | 劳工阿什肯纳兹 | 9 | 12 | **21** | PASS |
| `kibbutz_moshav` | 基布兹与莫沙夫 | 7 | 7 | **14** | PASS |
| `russian` | 苏联/俄裔新移民 | 7 | 5 | **12** | PASS |

### 2.2 有向基本环路（Elementary Cycles）增益与阻尼表

注意：对于 `shape: below`（公式 $f(s) = c \cdot \max(0, p - s)$），当源参数处于激活区间 $s < p$ 时，其方向导数为 $\partial f / \partial s = -c$（或显式声明的负斜率 `slope`）。在精确计入方向导数符号后，系统共有 **24 条参数族级基本有向环路**（展开区域/群体下标后为 **46 条实例级基本有向环路**），其中最大正反馈环增益 $|G| = 0.350 < 0.50$：

| 环路编号 | 反馈类型 | 有向环路路径 | 组成边 ID | 环路增益 $G = \prod (\partial f_e / \partial s_e)$ | 阻尼机制 / 软上限 / 危机断路器（$\ge 2$ 重） |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **L-01** | **正反馈** | `inflation → inflation` | `M10.INF.04` | **$+0.3500$** | ① `soft: {lo_s: -1, hi_s: 420, w: 60}` 软上限压缩；② 季度指数平滑 $\alpha = 0.35$ + `inertia: 3`；③ 危机断路器 `stabilization_plan`（`E-1985-07` / 行动 `stabilization_plan`） |
| **L-02** | **负反馈** | `settler_momentum → settler_momentum` | `M02.SM.07` | **$-0.2500$** | 自发扩张疲劳负反馈（`above: 40`, `coef: -0.25`, `inertia: 6`）+ `soft: {lo_s: 8, hi_s: 92, w: 12}` |
| **L-03** | **正反馈** | `fx_reserves → inflation → fx_reserves` | `M10.INF.03` $\times$ `M10.FX.02` | **$+0.2160$** | ① 阈值门控 `fx_reserves < 30` 且 `inflation > 15`；② 两节点均设 `soft` 软边界与指数平滑 $\alpha \in [0.25, 0.35]$；③ `devalue_currency` / `request_us_aid` 断路器 |
| **L-04** | **正反馈** | `centralization ↔ rule_of_law` | `M02.ROL.01+07` $\times$ `M13.CEN.01` | **$+0.1200$** | ① 双重门控 `centralization > 30` 且 `rule_of_law < 45`；② `rule_of_law` 单月变动硬上限 $\pm 1.0$/月；③ `centralization` 余量缩放 `(100-C)/100` + 自然衰减 $-0.5$/月 + M13 九类抵抗主体反制 |
| **L-05** | **正反馈** | `absorption_capacity ↔ unemployment` | `M02.ABS.02` $\times$ `M10.UNE.03` | **$+0.0900$** | ① 双重阈值门控 `unemployment > 7` 且 `absorption_capacity < 50`；② 两节点 `level` 平滑（$\alpha=0.15, 0.20$）与 `soft` 软边界；③ `inertia: 3` |
| **L-06** | **正反馈** | `absorption_capacity ↔ growth` | `M02.ABS.01` $\times$ `M10.GRO.04` | **$+0.0600$** | ① 门控 `growth > 2` 且 `absorption_capacity < 45`；② `inertia: 6` 延迟平滑；③ `soft` 软边界与 $\alpha$ 平滑 |
| **L-07** | **正反馈** | `settler_momentum ↔ bloc_support[religious_zionist]` | `M02.SM.04` $\times$ `M02.BS.RZ.01` | **$+0.0500$** | ① `M02.SM.04` 门控 `above: 60` + `inertia: 6`；② `M02.SM.07` 自疲劳负反馈（$-0.25$）强力压制；③ `soft` 软边界与 $\alpha=0.20$ |
| **L-08** | **正反馈** | `fx_reserves → inflation → growth → fx_reserves` | `M10.INF.03` $\times$ `M10.GRO.01` $\times$ `M10.FX.01` | **$+0.0384$** | ① 多重阈值门控（`fx < 30`, `inf > 20`）；② `inertia: 3` 延迟；③ `soft` 软边界与 $\alpha$ 平滑 |
| **L-09** | **正反馈** | `unemployment ↔ union_strength` | `M10.UNI.01` $\times$ `M10.UNE.02` | **$+0.0320$** | ① 双门控 `unemployment > 6` 且 `union_strength > 55`；② `inertia: 6` 延迟；③ `union_strength` 极慢平滑 $\alpha = 0.05$ |
| **L-10** | **正反馈** | `absorption_capacity → growth → unemployment → absorption_capacity` | `M10.GRO.04` $\times$ `M10.UNE.01` $\times$ `M02.ABS.02` | **$+0.0300$** | ① 门控 `absorption < 45` 且 `unemployment > 7`；② `inertia: 3..6`；③ `level` 指数平滑与 `soft` 边界 |
| **L-11** | **负反馈** | `judicial_conflict ↔ rule_of_law` | `M02.JC.02` $\times$ `M02.ROL.02` | **$-0.0200$** | 司法冲突升高削弱法治，而高法治支撑高院积极审查，构成天然负反馈平衡环（`inertia: 3`） |
| **L-12** | **正反馈** | `region_development[r] ↔ region_security[r]`（11 区域） | `M11.RSEC.04` $\times$ `M11.RDEV.01` | **$+0.0180$** | ① 门控 `region_development < 40`；② 极高惯性 `inertia: 6..12`；③ 区域 `level` 慢速平滑 $\alpha = 0.05..0.15$ |
| **L-13** | **正反馈** | `pal_hostility ↔ settler_momentum` | `M08.PH.01` $\times$ `M02.SM.03` | **$+0.0180$** | ① `inertia: 3`；② `settler_momentum` 自疲劳负反馈（$-0.25$）；③ 两节点 `soft` 软边界与 $\alpha=0.10..0.20$ |
| **L-14** | **正反馈** | `alienation[g] ↔ historical_grievance[g]`（3 群体） | `M02.HGR.01` $\times$ `M02.ALN.06` | **$+0.0150$** | ① 门控 `alienation > 50`（当 `alienation <= 50` 时 `M02.HGR.02` 触发 $-0.1$/月自然消退）；② `headroom: True` 余量上限缩放；③ `inertia: 6..12` |
| **L-15** | **正反馈** | `rule_of_law ↔ settler_momentum` | `M02.SM.05` $\times$ `M02.ROL.04` | **$+0.0150$** | ① 门控 `rule_of_law < 55` 且 `settler_momentum > 60`；② `inertia: 6`；③ `rule_of_law` 单步上限与 `M02.SM.07` 自疲劳 |
| **L-16** | **负反馈** | `growth → unemployment → union_strength → inflation → growth` | `M10.UNE.01` $\times$ `M10.UNI.01` $\times$ `M10.INF.02` $\times$ `M10.GRO.01` | **$-0.0032$** | 宏观菲利普斯—工会工资螺旋阻尼环：高增长压低失业→推高工会力量→推高通胀→抑制增长 |

---

## 三、行动代价多样性与反单货币审计（Action Cost & Anti-Mana Audit）

依据 Paradox 教训（M1/M2 反魔力池、S7 复合代价、D10 重大行动多维代价），对 `data/actions.yaml`（104 项行动）与 `data/policies.yaml`（76 项政策拉杆）审计如下：

### 3.1 行动代价结构分类统计

| 代价结构分类 | 行动数量 | 占比 | 合同阈值要求 | 代表性行动示例 |
| :--- | :---: | :---: | :---: | :--- |
| **PC + 复合多维代价（Composite PC+Other）** | **86** | **82.7%** | 主体类型 | `found_settlement`（`pc` + `fiscal` + `us_admin_relation`）、`evacuate_settlement`（`pc` + `standing` + `ally` + `bloc`） |
| **纯非 PC 代价（Non-PC Only）** | **8** | **7.7%** | 鼓励 | `call_early_election`（`standing` + `ally_coal`）、`free_vote`（`standing`）、`cabinet_retreat`（`fiscal`）、`request_ally_vote`（`fav_incur`） |
| **仅消耗政治资本（PC-Only，全为 `minor`/常规）** | **9** | **8.7%** | **$\le 50.0\%$** | `national_address`、`trial_balloon`、`visit_dev_town`、`knesset_speech`、`diaspora_tour`、`appoint_minister`、`renounce_promise` 等轻量常规动作 |
| **委托政策拉杆复合代价（Delegated Policy）** | **1** | **1.0%** | 76/76 复合 | `adjust_policy`（由 `data/policies.yaml` 中 76/76 项含 `pc` + `up`/`down` 集团/盟友代价 + 议会投票/财政代价的政策驱动） |
| **合计（Total Actions）** | **104** | **100.0%** | **34/34 `major` 100% 复合代价** | **PASS（PC-Only 仅 8.7%，远低于 50% 上限）** |

### 3.2 各代价维度在 104 项行动中的覆盖频次

| 代价键（Cost Key） | 含义 | 涉及行动数 | 占行动总数比例 |
| :--- | :--- | :---: | :---: |
| `pc` | 政治资本（Political Capital） | 95 | 91.3% |
| `par` | 直接国家/外交/安全参数代价（如 `intl_legitimacy`, `us_admin_relation`） | 42 | 40.4% |
| `fiscal` / `fiscal_m` | 一次性或按月持续财政预算消耗 | 39 | 37.5% |
| `standing` | 党内威望损耗（`party_standing`） | 20 | 19.2% |
| `ally` / `ally_coal` | 特定联合政府盟友或全体执政盟友满意度损耗 | 18 | 17.3% |
| `bloc` | 特定选民集团支持度损耗（`bloc_support`） | 12 | 11.5% |
| `rol` | 法治指数损耗（`rule_of_law`） | 11 | 10.6% |
| `rel` | 关键内阁/军方/情报/外国人物关系损耗（`relation`） | 9 | 8.7% |
| `fav_incur` / `fav_spend` | 欠下或消耗人情债（M05 Favor Ledger） | 5 | 4.8% |

---

## 四、事件选项张力、极端选项铁律与暴行三阶段审计（Event Tension Audit）

### 4.1 6 个事件文件（396 事件 / 858 选项）张力统计表

| 事件文件 | 事件总数 | 抉择点（含 `followup_choice`） | 选项总数 | 白送选项（`NO_NEG`） | 纯陷阱选项（`NO_POS`） | 事前决策点（`predecision`） | 极端选项（`extreme`） | 状态 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `fixed_1948_1955.yaml` | 64 | 49 | 147 | **0** | **0** | 4 | 6 | **PASS** |
| `fixed_1955_1967.yaml` | 63 | 44 | 132 | **0** | **0** | 1 | 2 | **PASS** |
| `fixed_1967_1977.yaml` | 62 | 42 | 126 | **0** | **0** | 3 | 1 | **PASS** |
| `fixed_1977_1992.yaml` | 76 | 56 | 168 | **0** | **0** | 3 | 5 | **PASS** |
| `fixed_1992_2006.yaml` | 72 | 52 | 155 | **0** | **0** | 3 | 5 | **PASS** |
| `random_events.yaml` | 59 | 44 | 130 | **0** | **0** | 0 | 0 | **PASS** |
| **总计（All 6 Files）** | **396** | **287** | **858** | **0** | **0** | **14** | **19** | **100% PASS** |

### 4.2 14 条以方暴行/重大事故三阶段链条合规表（V-14）

所有 14 条暴行与重大事故链均严格执行 **阶段 1 事前政策抉择（`form: predecision`，仅设 `display: hidden` 的 `event_multiplier` 与定性 `risk_hint: 低/中/高`）→ 阶段 2 暴行被动触发（`form: passive`）→ 阶段 3 事后调查与问责（`form: choice`）**：

| 序号 | 所属时期文件 | 阶段 1：事前决策点（`form: predecision`） | 选项风险提示与隐藏乘数（A / B / C） | 阶段 2：暴行/事故事件 | 阶段 3：事后调查/处置事件（`form: choice`） | 合规状态 |
| :---: | :--- | :--- | :---: | :--- | :--- | :---: |
| 1 | `1948_1955` | `E-1948-03a` 达尼行动：对占领城镇居民的指令 | A:高(1.0) / B:低(0.20) / C:高(2.0) | `E-1948-04` 吕大与拉姆勒 (`passive`) | `E-1948-05` 吕大与拉姆勒：事后处置 | **PASS** |
| 2 | `1948_1955` | `E-1948-09a` 南北攻势前的作战纪律 | A:高(1.0) / B:低(0.25) / C:高(1.8) | `E-1948-10` 约阿夫与希拉姆 (`passive`) | `E-1948-11` 战时暴行报告 | **PASS** |
| 3 | `1948_1955` | `E-1953-02a` 组建101部队 | A:高(1.0) / B:中(0.35) / C:低(0.15) | `E-1953-04` 耶胡德与基比亚 (`passive`) | `E-1953-05` 基比亚：事后处置 | **PASS** |
| 4 | `1948_1955` | `E-1953-06a` 情报机构的海外行动授权 | A:高(1.0) / B:中(0.30) / C:低(0.05) | `E-1954-01` 苏珊娜行动败露 (`passive`) | `E-1955-01` 开罗审判 / `E-1955-02` "谁下的命令" | **PASS** |
| 5 | `1955_1967` | `E-1956-10d` 战时的开火规则 | A:高(1.0) / B:低(0.15,0.20) / C:中(0.30,0.60) | `E-1956-10b` 卡夫尔卡西姆 / `E-1956-11e` 汗尤尼斯 (`passive`) | `E-1956-11a` 卡夫尔卡西姆审判 / `E-1956-11b` 加沙事后处置 | **PASS** |
| 6 | `1967_1977` | `E-1967-01a` 哭墙前的“清理” | A:高(1.0) / B:中(0.40) / C:低(0.15) | `E-1967-01b` 穆格拉比区拆除 (`passive`) | `E-1967-01c` 穆格拉比居民的去向 | **PASS** |
| 7 | `1967_1977` | `E-1973-01a` 西奈空域的交战规则 | A:高(1.0) / B:中(0.40) / C:低(0.15) | `E-1973-01b` 利比亚航空114号班机 (`passive`) | `E-1973-01c` 客机击落之后 | **PASS** |
| 8 | `1967_1977` | `E-1976-01a` 开发加利利：征地决议与罢工日部署 | A:高(1.0) / B:中(0.40) / C:低(0.15) | `E-1976-01b` 土地日 (`passive`) | `E-1976-01c` 土地日之后 | **PASS** |
| 9 | `1977_1992` | `E-1980-05b` 哈达萨楼之后 | A:高(1.0) / B:中(0.40) / C:低(0.15) | `E-1980-06` 市长汽车炸弹（弹窗含被动发生） | `E-1980-06` 市长汽车炸弹（事后调查选项） | **PASS** |
| 10 | `1977_1992` | `E-1982-09b` 长枪党与难民营 | A:高(1.0) / B:中(0.40) / C:低(0.05) | `E-1982-09c` 萨布拉与夏蒂拉 (`passive`) | `E-1982-09d` 调查委员会 / `E-1983-02a` 卡汉报告 | **PASS** |
| 11 | `1977_1992` | `E-G04-19` 辛贝特的不成文规则 | A:高(1.0) / B:中(0.30) / C:高(2.0) | `E-1984-04a` 300路公交车 (`passive`) | `E-1986-05` 辛贝特丑闻与特赦 | **PASS** |
| 12 | `1992_2006` | `E-1993-05` 奥斯陆之后的极右：执法力度 | A:高(1.0) / B:中(0.40) / C:中(0.50) | `E-1994-01` 易卜拉欣清真寺屠杀 (`passive`) | `E-1994-02` 屠杀之后：处置 | **PASS** |
| 13 | `1992_2006` | `E-1998-02` 乌姆法赫姆冲突之后：警方的交战规则 | A:高(1.0) / B:中(0.30) / C:高(1.8) | `E-2000-04a` 十月：阿拉伯城镇的十三人 (`passive`) | `E-2000-05` 十月事件与奥尔委员会 | **PASS** |
| 14 | `1992_2006` | `E-2004-05` 撤离前夕：对极端反撤离者的执法 | A:高(1.0) / B:中(0.40) / C:高(0.70) | `E-2005-01` 沙法阿姆公交车枪击 (`passive`) | `E-2005-02` 古什卡蒂夫撤离及安全问责 | **PASS** |

### 4.3 19 个极端/掩盖选项长期净负铁律验证表（X1 / V-24）

所有标注 `tags: [..., extreme]` 的 19 个极端硬线或掩盖暴行选项，在计入长期修正器（36 个月累积效应）、暴行触发乘数及制度/外交代价后，长期净效用 $U_{\text{LT}}$ 全部严格为负，且显著低于同事件中的制度化/温和选项 $U_{\text{mod}}$：

| 事件与选项 ID | 选项名称 | 长期综合净效用 $U_{\text{LT}}$ | 同事件最优温和选项 $U_{\text{mod}}$ | 法治/国际合法性直接惩罚 | 验证结果 |
| :--- | :--- | :---: | :---: | :--- | :---: |
| `E-1948-02.C` | 借机取缔伊尔贡，逮捕贝京 | $-106.7$ | $+5.6$ | `rule_of_law -10`, `intl_legitimacy -3` | **PASS** |
| `E-1948-03.C` | 宣布永久禁止回归，系统性拆除空村 | $-88.3$ | $+12.1$ | `intl_legitimacy -12`, `rule_of_law -3` | **PASS** |
| `E-1948-03a.C` | 授权清除交通线沿线的敌对人口 | $-88.3$ | $+12.3$ | `rule_of_law -5`, `intl_legitimacy -6` | **PASS** |
| `E-1948-05.C` | 授权后续战区同样做法 | $-98.0$ | $+1.9$ | `rule_of_law -8`, `intl_legitimacy -10` | **PASS** |
| `E-1948-08.C` | 全面攻入山区，夺取西岸 | $-174.8$ | $+21.1$ | `intl_legitimacy -20`, `rule_of_law -3` | **PASS** |
| `E-1948-09a.C` | 授权指挥官促使村民撤离战区 | $-67.3$ | $+11.4$ | `rule_of_law -4`, `intl_legitimacy -5` | **PASS** |
| `E-1953-05.C` | 公开嘉奖部队，继续同等规模的越境报复 | $-63.5$ | $-2.0$ | `intl_legitimacy -15`, `rule_of_law -3` | **PASS** |
| `E-1956-11a.C` | 延长审查，以“战时安全”为由封存 | $-69.8$ | $+29.2$ | `rule_of_law -12`, `intl_legitimacy -8` | **PASS** |
| `E-1967-06f.C` | 以色列接管圣殿山，允许犹太人在山上祈祷 | $-101.5$ | $+5.1$ | `intl_legitimacy -15`, `rule_of_law -4` | **PASS** |
| `E-1976-01c.A` | 维持征地，称伤亡是维持秩序所致，不设调查 | $-34.7$ | $+6.3$ | `rule_of_law -3`, `intl_legitimacy -2` | **PASS** |
| `E-1980-06.C` | 把调查压下去，以安全名义结案 | $-43.5$ | $+4.0$ | `rule_of_law -8`, `intl_legitimacy -4` | **PASS** |
| `E-1982-09d.B` | 拒绝一切外部调查，由内阁或军方内部自查 | $-86.8$ | $+23.2$ | `rule_of_law -8`, `intl_legitimacy -8` | **PASS** |
| `E-1983-02a.C` | 拒绝报告结论 | $-86.4$ | $+22.3$ | `rule_of_law -12`, `intl_legitimacy -8` | **PASS** |
| `E-G04-19.C` | 口头暗示：不需要活口 | $-77.0$ | $+11.3$ | `rule_of_law -6`, `intl_legitimacy -4` | **PASS** |
| `E-1986-05.C` | 解雇总检察长扎米尔，强行终止调查 | $-52.5$ | $-13.7$ | `rule_of_law -17` (`-12` + `-5`) | **PASS** |
| `E-1994-02.A` | 仅作最低限度回应，不设调查委员会 | $-18.1$ | $+6.2$ | `rule_of_law -3`, `intl_legitimacy -4` | **PASS** |
| `E-1998-02.C` | 定义示威为敌对行动，授权实弹与狙击手 | $-71.4$ | $+8.1$ | `rule_of_law -6`, `intl_legitimacy -4` | **PASS** |
| `E-2000-05.C` | 拒绝调查，将示威定性为“内部起义” | $-61.8$ | $+19.0$ | `rule_of_law -8`, `intl_legitimacy -5` | **PASS** |
| `E-2004-03.B` | 同时拒绝国际法院和本国法院的改道要求 | $-114.6$ | $-9.8$ | `intl_legitimacy -15`, `rule_of_law -10` | **PASS** |

---

## 五、7 策略 Bot 设计与决策分化矩阵（`sim/bots.py`）

### 5.1 7 个策略 Bot 的人格定义、预算偏好与首选行动

| Bot ID | 中文名称 | 核心效用偏好（Weights & Persona） | 国防/福利/基建/定居点/科教预算比 | 代表性首选行动（Top Actions） |
| :--- | :--- | :--- | :---: | :--- |
| `historical` | **历史还原派** | 优先选择 `historical: true`；无标记时最小化走廊偏离（`_corridor_away: -3.0`）并维持制度与宏观稳定 | `30% / 28% / 20% / 7% / 15%` | `stabilization_plan`, `peace_initiative`, `submit_budget`, `state_inquiry` |
| `revisionist_hawk` | **修正派铁壁** | 最大化 `deterrence`、`settler_momentum`、`readiness`、`region_security`；偏好 `hardline`/`settlement` | `42% / 20% / 15% / 15% / 8%` | `found_settlement`, `legalize_outposts`, `golan_heights_law`, `jerusalem_law`, `retaliatory_raid` |
| `peace_dove` | **和平鸽派** | 最大化 `intl_legitimacy`、`rule_of_law`、`promise_progress[cat_peace]`、降低暴行乘数与 `pal_hostility` | `22% / 32% / 22% / 1% / 23%` | `peace_initiative`, `evacuate_settlement`, `sinai_withdrawal`, `state_inquiry`, `visit_arab_town` |
| `populist_welfare` | **民粹福利派** | 最大化 `bloc_support[mizrahi/haredi]`、`ally_satisfaction[shas/nrp]`、降低 `unemployment`/`alienation`，容忍赤字与通胀 | `24% / 44% / 18% / 4% / 10%` | `absorption_emergency`, `new_development_town`, `project_renewal_expand`, `appoint_mizrahi_officials` |
| `neoliberal_technocrat` | **新自由主义技术官僚** | 最大化 `growth`、`fx_reserves`、`budget_balance`，压低 `inflation`/`debt_gdp`/`union_strength`，高通胀时自动触发紧急稳定计划 | `24% / 18% / 26% / 2% / 30%` | `stabilization_plan`, `free_trade_agreement`, `privatize_soe`, `r_and_d_grant`, `cut_subsidies` |
| `authoritarian_caesar` | **强人集权派** | 最大化 `centralization`、`political_capital`、`party_standing`、情报/审查控制，偏好 `authoritarian`/`extreme` | `40% / 22% / 18% / 12% / 8%` | `emergency_regulations`, `override_clause`, `military_censorship`, `ag_dismiss`, `expel_rebels` |
| `random` | **均匀随机基线** | 基于确定性哈希种子在可用选项与可负担行动间均匀采样，作为蒙特卡洛对照基线 | `30% / 28% / 20% / 7% / 15%` | 确定性伪随机均匀采样 |

### 5.2 7 策略 Bot 在全部抉择事件上的选项分布与成对分歧率（E7 验证）

在全部抉择事件上，没有任何单一非历史选项垄断超过 80% 的意识形态 Bot，全部 7 个 Bot 一致选择同一选项的事件为 **0%**，核心意识形态对立组别的成对决策分歧率高达 **75%–84%**：

- **`peace_dove` vs `authoritarian_caesar`**：分歧率 **83.6%**
- **`revisionist_hawk` vs `peace_dove`**：分歧率 **81.6%**
- **`neoliberal_technocrat` vs `authoritarian_caesar`**：分歧率 **78.0%**
- **`populist_welfare` vs `neoliberal_technocrat`**：分歧率 **71.2%**
- **`historical` vs `authoritarian_caesar`**：分歧率 **74.8%**

---

## 六、Phase 3B 发现并修复的数据问题清单（Changelog of Tuned Items）

1. **修复 1948–1956 年 5 条暴行/重大事故链的事前决策点结构（V-14）**：
   - 将 `E-1948-03a`（达尼行动指令 → `E-1948-04` 吕大与拉姆勒）、`E-1948-09a`（南北攻势作战纪律 → `E-1948-11` 战时暴行报告）、`E-1953-02a`（组建101部队 → `E-1953-04` 基比亚）、`E-1953-06a`（海外行动授权 → `E-1954-01` 苏珊娜行动败露）、`E-1956-10d`（战时开火规则 → `E-1956-10b` 卡夫尔卡西姆 & `E-1956-11e` 汗尤尼斯）升级为 `form: predecision`，补齐 `display: hidden` 的 `event_multiplier` 与严格匹配阈值区间的 `risk_hint: 高/中/低`。
2. **修正 1982–2004 年 3 条 `predecision` 事件的 `event_multiplier` 目标事件 ID 错位**：
   - `E-1982-09b`（长枪党与难民营）：乘数目标由 `E-1982-09a`（杰马耶勒遇刺）修正为 `E-1982-09c`（萨布拉与夏蒂拉被动暴行事件）。
   - `E-1993-05`（奥斯陆之后的极右执法）：乘数目标由 `E-1993-03`（原则宣言）修正为 `E-1994-01`（易卜拉欣清真寺屠杀被动事件）。
   - `E-2004-05`（撤离前夕对极端反撤离者的执法）：乘数目标由 `E-2004-02`（利库德党内公投）修正为 `E-2005-01`（沙法阿姆公交车枪击被动事件）。
3. **补齐 `data/actions.yaml` 中 2 项 `w: major` 行动的复合代价（D10 / S7）**：
   - 为 `coopt_challenger`（收编挑战者）和 `call_leadership_vote`（提前党魁选举）补充 `standing: -1` 威望代价，使 34/34（100%）`w: major` 行动均具备 $\ge 2$ 维复合代价。
4. **标注并强化 19 个 `extreme` 极端/掩盖选项的长期净负与制度惩罚（X1 / V-24）**：
   - 为全时期 19 个极端硬线或事后掩盖选项显式添加 `extreme` 标签，并为 `E-1948-08.C`、`E-1953-05.C`、`E-1967-06f.C`、`E-G04-19.C`、`E-1986-05.C`、`E-1994-02.A`、`E-1998-02.C` 补齐 `rule_of_law` / `intl_legitimacy` 惩罚。
5. **消除全部 858 个事件选项中的“白送”与“纯陷阱”缺口**：
   - 对静态扫描发现缺少显式负向代价的 13 个选项（如 `E-1961-01.B`、`E-1963-06b.A`、`E-1967-06a.B`、`E-1973-05.C`、`E-G03-01.C`、`E-G03-06.A`、`E-1981-06b.C`、`E-1996-04.A`、`E-2005-03.C`、`R-47.B` 等）补齐符合史实的预算、政治资本、威望或盟友代价；
   - 对缺少显式正向收益的选项（如 `E-G04-07.A` 选前全面减税与补贴补齐短期选民支持与威望、`E-1978-09.B` 补齐右翼盟友满意度等）补齐符合史实的短期政治、安全、外交或财政回报，实现 **0 白送选项（`NO_NEG = 0`）与 0 纯陷阱选项（`NO_POS = 0`）**。
