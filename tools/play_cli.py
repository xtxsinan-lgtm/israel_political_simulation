#!/usr/bin/env python3
"""
Interactive & Automated CLI Playtest Client for Israel Political Simulation (Begin 1977-1992).
Supports:
  - Interactive human play (--interactive)
  - Single bot narrative playtest (--bot <persona> --seed <int> --days <int>)
  - Signature 3-campaign narrative playtest suite (--generate-transcripts)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.bots import (
    AuthoritarianCaesarBot,
    HistoricalBot,
    NeoliberalTechnocratBot,
    PeaceDoveBot,
    PopulistWelfareBot,
    RandomBot,
    RevisionistHawkBot,
    StrategyBot,
)
from sim.engine import SimulationEngine
from sim.modules import compute_final_evaluation


BOT_MAP = {
    "historical": HistoricalBot,
    "revisionist_hawk": RevisionistHawkBot,
    "peace_dove": PeaceDoveBot,
    "populist_welfare": PopulistWelfareBot,
    "neoliberal_technocrat": NeoliberalTechnocratBot,
    "authoritarian_caesar": AuthoritarianCaesarBot,
    "random": RandomBot,
}


class InteractivePlayBot(StrategyBot):
    """Interactive human CLI player with fallback to HistoricalBot if stdin reaches EOF."""
    bot_id = "interactive_player"
    name_zh = "人类玩家交互模式 (Interactive Player)"

    def choose_event_option(
        self,
        state: Any,
        event: Any,
        options: Optional[Sequence[Any]] = None,
    ) -> str:
        opts = list(options if options is not None else (event.get("options") or []))
        if not opts:
            return "A"
        print("\n" + "=" * 78)
        print(f"📜 [EVENT POPUP] {state.date_str} | {event.get('id')} — {event.get('title_zh', event.get('title', ''))}")
        if event.get("summary_zh") or event.get("desc_zh"):
            print(f"   {(event.get('summary_zh') or event.get('desc_zh', ''))[:240]}")
        print("-" * 78)
        for idx, opt in enumerate(opts, 1):
            hist_tag = " [史实]" if opt.get("historical") else ""
            lbl = opt.get("label_zh") or opt.get("text_zh") or opt.get("label") or opt.get("id")
            print(f"  [{idx}] {opt.get('id')}: {lbl}{hist_tag}")
        print("=" * 78)
        try:
            choice = input(f"Select option [1-{len(opts)}] (Enter for 1): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(opts):
                return str(opts[int(choice) - 1].get("id", "A"))
        except EOFError:
            pass
        return str(opts[0].get("id", "A"))


class PragmaticVisionBeginBot(StrategyBot):
    """
    Campaign 1 Persona: Pragmatic Revisionist Begin pursuing 'Peace in Eretz Israel'
    (begin_peace_in_eretz_israel grand vision):
      - Welcomes Sadat & signs Camp David / Egypt Peace Treaty (Southern Peace)
      - Accelerates Judea & Samaria settlement momentum above 65k settlers & 65 momentum
      - Restrains 1982 Lebanon War to 40km limited operation (avoiding Sabra & Shatila stigma & Begin's breakdown)
      - Executes the 1985 Stabilization Plan to tame hyperinflation and preserve democratic legitimacy
    """
    bot_id = "pragmatic_vision_begin"
    name_zh = "务实修正派贝京：在以色列地的和平 (Pragmatic Vision Begin)"

    def __init__(self, seed: int = 19770620) -> None:
        super().__init__(
            seed=seed,
            weights={
                "vision_progress": 3.5,
                "settler_momentum": 2.8,
                "deterrence": 2.2,
                "public_security": 2.2,
                "readiness": 1.8,
                "us_admin_relation": 1.8,
                "intl_legitimacy": 1.5,
                "rule_of_law": 1.8,
                "party_standing": 1.6,
                "political_capital": 0.6,
                "inflation": -2.0,
                "fx_reserves": 2.0,
                "budget_balance": 1.8,
                "growth": 1.8,
                "promise_progress": 1.5,
                "ally_satisfaction": 1.4,
                "bloc_support.mizrahi": 1.8,
                "bloc_support.religious_zionist": 2.0,
                "centralization": -1.5,
                "_stabilization_plan": 40.0,
                "_corridor_away": -2.5,
                "_corridor_toward": 2.2,
                "_atrocity_avoidance": 18.0,
                "_mod_crisis_penalty": -6.0,
                "_axis_territory": 2.0,
                "_axis_security": 1.2,
            },
            tag_bonuses={
                "settlement": 16.0,
                "economic": 10.0,
                "restraint": 8.0,
                "authoritarian": -20.0,
                "extreme": -35.0,
            },
            cat_bonuses={"terr": 9.0, "econ": 8.0, "dip": 6.0, "mil": 4.0, "coal": 4.0},
        )

    def choose_event_option(
        self,
        state: Any,
        event: Any,
        options: Optional[Sequence[Any]] = None,
    ) -> str:
        opts = list(options if options is not None else (event.get("options") or []))
        if not opts:
            return "A"
        eid = str(event.get("id", ""))
        # Southern peace chain: follow historical Camp David & Egypt Peace Treaty
        if eid in ("E-1977-11", "E-1978-03", "E-1978-09", "E-1979-03", "E-1981-06a", "E-1982-04"):
            for o in opts:
                if o.get("historical"):
                    return str(o.get("id", "A"))
        # 1982 Lebanon War: restrain to 40km Operation Peace for Galilee (Option B in E-1982-06a)
        if eid in ("E-1982-06a", "E-1982-06b", "E-1982-08", "E-1982-09a"):
            for o in opts:
                tags = set(o.get("tags") or [])
                if "restraint" in tags or not o.get("historical", False):
                    return str(o.get("id", "B"))
        # 1983 Bank Crisis & 1985 Stabilization Plan: take decisive stabilization
        if eid in ("E-1983-10", "E-1985-07"):
            for o in opts:
                if o.get("historical"):
                    return str(o.get("id", "A"))
        return super().choose_event_option(state, event, opts)


def format_hud_snapshot(st: Any) -> str:
    parl = st.parliament
    coal_parties = parl.get("coalition") or parl.get("coalition_parties", [])
    seats_map = st.params.get("knesset_seats", {}) or parl.get("seats", {})
    ally_sat = st.params.get("ally_satisfaction", {})
    coal_str = ", ".join(
        f"{p}({int(seats_map.get(p, 0))}席" + (f",满{ally_sat.get(p, 70.0):.0f}" if p != st.player.get("party_id") else ",主党") + ")"
        for p in coal_parties
    )
    prom_parts = []
    prom_prog = st.params.get("promise_progress", {})
    for pr in st.promises:
        pid = pr.get("id") or pr.get("key") or pr.get("promise_id") or ""
        status = pr.get("status", "active")
        prog = float(prom_prog.get(pid, pr.get("progress", 0.0)))
        icon = "✅" if status == "fulfilled" or prog >= 80.0 else ("❌" if status == "failed" else f"{prog:.0f}%")
        prom_parts.append(f"{pid}:{icon}")

    leader_id = st.player.get("leader_id", "begin")
    leader_health = st.get_param("health", leader_id)
    leader_stress = st.get_param("character_stress", leader_id)
    in_corr = st.party_state.get("in_corridor", True)
    auth_stage = f"C{int(st.m13.get('stage', 0)) + 1}"
    v_status = st.vision.get("status", "in_progress")
    v_prog = st.get_param("vision_progress")

    return (
        f"📅 {st.date_str} (Day {st.day_index}) | 总理: {leader_id} (健康={leader_health:.1f}, 压力={leader_stress:.1f}) | "
        f"政资(PC): {st.get_param('political_capital'):.1f} | 党内地位: {st.get_param('party_standing'):.1f}\n"
        f"   🏛️ 议会联盟: {int(st.get_param('coalition_seats'))}席 [{coal_str}]\n"
        f"   📊 宏观经济: 通胀={st.get_param('inflation'):.1f}% | 外储={st.get_param('fx_reserves'):.1f} | "
        f"GDP增速={st.get_param('growth'):.2f}% | 失业={st.get_param('unemployment'):.1f}% | 债务/GDP={st.get_param('public_debt'):.1f}%\n"
        f"   ⚖️ 安全与宪政: 威慑={st.get_param('deterrence'):.1f} | 治安={st.get_param('public_security'):.1f} | "
        f"定居点动量={st.get_param('settler_momentum'):.1f} (总人口={st.settler_population_total():,d}) | "
        f"集权度={st.get_param('centralization'):.1f} (阶段={auth_stage}) | 法治={st.get_param('rule_of_law'):.1f}\n"
        f"   🎯 三层目标: 承诺=[{', '.join(prom_parts)}] | 走廊内={'是' if in_corr else '否'} | "
        f"宏大愿景({st.vision.get('id', 'begin_peace_in_eretz_israel')})={v_prog:.1f}% ({v_status})"
    )


def run_narrative_campaign(
    bot: StrategyBot,
    seed: int,
    days: int = 5478,
    allow_succession: bool = True,
    stop_on_end: bool = False,
    campaign_title: str = "",
    campaign_subtitle: str = "",
) -> Dict[str, Any]:
    eng = SimulationEngine(master_seed=seed, bot=bot, allow_succession=allow_succession)
    st = eng.state

    snapshots: List[str] = [
        f"#### 阶段快照 — 开局就任 ({st.date_str})\n```text\n{format_hud_snapshot(st)}\n```"
    ]
    yearly_table: List[Dict[str, Any]] = []
    pm_transitions: List[str] = []
    auth_transitions: List[str] = []
    vision_achieved_date: Optional[str] = None

    last_pm = st.player.get("leader_id", "begin")
    last_auth_stage = f"C{int(st.m13.get('stage', 0)) + 1}"
    milestone_years = {1978, 1981, 1983, 1985, 1988, 1991}
    captured_years = set()

    for _ in range(days):
        if stop_on_end and st.run.get("ended", False):
            break
        eng.step_day()

        cur_pm = st.player.get("leader_id", "begin")
        if cur_pm != last_pm:
            pm_transitions.append(f"`{st.date_str}`: 总理更迭 `{last_pm}` → `{cur_pm}`")
            last_pm = cur_pm

        cur_stage = f"C{int(st.m13.get('stage', 0)) + 1}"
        if cur_stage != last_auth_stage:
            auth_transitions.append(
                f"`{st.date_str}`: 宪政/集权阶梯 `{last_auth_stage}` → `{cur_stage}` (集权度={st.get_param('centralization'):.1f})"
            )
            last_auth_stage = cur_stage

        if st.vision.get("status") == "achieved" and vision_achieved_date is None:
            vision_achieved_date = st.date_str

        if st.month == 12 and st.day == 31:
            yr = st.year
            yearly_table.append({
                "year": yr,
                "pm": cur_pm,
                "seats": int(st.get_param("coalition_seats")),
                "pc": round(st.get_param("political_capital"), 1),
                "standing": round(st.get_param("party_standing"), 1),
                "inflation": round(st.get_param("inflation"), 1),
                "fx": round(st.get_param("fx_reserves"), 1),
                "growth": round(st.get_param("growth"), 2),
                "settler_mom": round(st.get_param("settler_momentum"), 1),
                "settlers": st.settler_population_total(),
                "centralization": round(st.get_param("centralization"), 1),
                "auth_stage": cur_stage,
                "vision_pct": round(st.get_param("vision_progress"), 1),
            })
            if yr in milestone_years and yr not in captured_years:
                captured_years.add(yr)
                snapshots.append(
                    f"#### 阶段快照 — {yr}年终 ({st.date_str})\n```text\n{format_hud_snapshot(st)}\n```"
                )

    snapshots.append(
        f"#### 阶段快照 — 终局结算 ({st.date_str})\n```text\n{format_hud_snapshot(st)}\n```"
    )

    ev_rep = st.m14.get("final_evaluation")
    if not ev_rep:
        ev_rep = compute_final_evaluation(st, st.run.get("end_reason") or "term_complete")

    # Enrich event log with titles and option labels from registry
    event_rows: List[Dict[str, Any]] = []
    for e in st.history.get("event_log", []):
        eid = e.get("event_id", "")
        edef = eng.registry.events_by_id.get(eid, {})
        title = edef.get("title_zh") or edef.get("title") or eid
        opt_id = e.get("option_id", "A")
        opt_lbl = opt_id
        for o in edef.get("options") or []:
            if str(o.get("id")) == str(opt_id):
                opt_lbl = o.get("label_zh") or o.get("text_zh") or o.get("label") or opt_id
                break
        event_rows.append({
            "date": e.get("date", ""),
            "id": eid,
            "title": title,
            "option_id": opt_id,
            "option_label": opt_lbl,
        })

    action_counts: Dict[str, int] = {}
    for a in st.history.get("action_log", []):
        aid = a.get("action_id", "")
        action_counts[aid] = action_counts.get(aid, 0) + 1

    return {
        "title": campaign_title,
        "subtitle": campaign_subtitle,
        "bot_id": bot.bot_id,
        "bot_name_zh": getattr(bot, "name_zh", bot.bot_id),
        "seed": seed,
        "end_date": st.date_str,
        "days_simulated": st.day_index,
        "pm_transitions": pm_transitions,
        "auth_transitions": auth_transitions,
        "vision_achieved": st.vision.get("status") == "achieved",
        "vision_achieved_date": vision_achieved_date,
        "vision_progress": round(st.get_param("vision_progress"), 1),
        "promises": [
            {
                "id": pr.get("id", ""),
                "name_zh": pr.get("name_zh", pr.get("title_zh", pr.get("id", ""))),
                "status": pr.get("status", "active"),
                "progress": round(float(st.params.get("promise_progress", {}).get(pr.get("id", ""), 0.0)), 1),
            }
            for pr in st.promises
        ],
        "tenures": st.tenures,
        "yearly_table": yearly_table,
        "snapshots": snapshots,
        "event_rows": event_rows,
        "action_counts": action_counts,
        "evaluation": ev_rep,
    }


def render_campaign_markdown(res: Dict[str, Any]) -> str:
    lines: List[str] = []
    ev = res["evaluation"]
    lines.append(f"## {res['title']}")
    lines.append(f"> **{res['subtitle']}**  ")
    lines.append(
        f"> **执政人格**: `{res['bot_id']}` ({res['bot_name_zh']}) | **随机种子**: `{res['seed']}` | "
        f"**推演跨度**: `1977-06-20` → `{res['end_date']}` ({res['days_simulated']} 天)  \n"
        f"> **终局结局**: `{ev['ending_id']}` — **{ev['ending_title']}** (`{ev['end_reason']}`) | "
        f"**综合历史评级**: **{ev['final_grade']} ({ev['overall_score']:.2f} 分)**\n"
    )

    lines.append("### 1. 三层目标、任期更迭与宪政状态总结")
    lines.append("| 维度层级 | 指标项 | 终局状态 | 详细记录 |")
    lines.append("|---|---|---|---|")
    for pr in res["promises"]:
        icon = "✅ 已兑现" if pr["status"] == "fulfilled" or pr["progress"] >= 80.0 else ("❌ 未兑现" if pr["status"] == "failed" else f"⏳ {pr['progress']}%")
        lines.append(f"| 第一层：竞选承诺 | `{pr['id']}` ({pr['name_zh']}) | {icon} | 终局兑现度 `{pr['progress']}%` |")
    corr_rate = ev.get("layer_scores", {}).get("corridor_inside_rate", 1.0) * 100.0
    lines.append(f"| 第二层：政党走廊 | 利库德党派走廊合规率 | `{corr_rate:.1f}%` | 走廊评价加成 `{ev.get('layer_scores', {}).get('corridor_bonus', 0.0):+.2f}` 分 |")
    vis_str = f"🌟 已达成 ({res['vision_achieved_date']})" if res["vision_achieved"] else f"⏳ 进度 {res['vision_progress']}%"
    lines.append(f"| 第三层：宏大愿景 | `begin_peace_in_eretz_israel` 在以色列地的和平 | {vis_str} | 愿景评价加成 `{ev.get('layer_scores', {}).get('vision_bonus', 0.0):+.2f}` 分 |")
    if res["tenures"]:
        t_strs = [f"`{t['leader_id']}`({t['start_date']}~{t['end_date']} → `{t['ending_id']}`)" for t in res["tenures"]]
        lines.append(f"| 历任内阁结算 | 共经历 {len(res['tenures'])} 任内阁阶段 | 继任链完整 | {'; '.join(t_strs)} |")
    if res["auth_transitions"]:
        lines.append(f"| 宪政危机阶梯 | C0–C5 集权等级跃迁 | 共 {len(res['auth_transitions'])} 次跃迁 | {'; '.join(res['auth_transitions'][:6])} |")
    lines.append("")

    lines.append("### 2. 1977–1992 历年宏观经济与政治轨迹表")
    lines.append("| 年份 | 在任总理 | 联盟席位 | 政资(PC) | 党内地位 | 通胀率(%) | 外储指数 | GDP增速(%) | 定居点动量(总人口) | 集权度(阶段) | 愿景进度(%) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["yearly_table"]:
        lines.append(
            f"| {r['year']} | `{r['pm']}` | {r['seats']}席 | {r['pc']} | {r['standing']} | "
            f"**{r['inflation']}%** | {r['fx']} | {r['growth']}% | "
            f"{r['settler_mom']} ({r['settlers']:,}) | {r['centralization']} (`{r['auth_stage']}`) | {r['vision_pct']}% |"
        )
    lines.append("")

    lines.append("### 3. 关键历史节点 HUD 仪表盘快照")
    for snap in res["snapshots"]:
        lines.append(snap)
        lines.append("")

    lines.append("### 4. 重大历史锚点与随机事件抉择编年史")
    lines.append("| 日期 | 事件 ID | 事件标题 | 所选选项与决策内容 |")
    lines.append("|---|---|---|---|")
    fixed_evs = [e for e in res["event_rows"] if e["id"].startswith("E-")]
    rand_evs = [e for e in res["event_rows"] if e["id"].startswith("R-")]
    shown_evs = sorted(fixed_evs[:28] + rand_evs[:8], key=lambda x: x["date"])
    for e in shown_evs:
        lines.append(f"| `{e['date']}` | `{e['id']}` | {e['title']} | **{e['option_id']}**: {e['option_label']} |")
    lines.append(
        f"\n*注：本局共触发 `{len(res['event_rows'])}` 次事件弹窗（其中固定历史事件 `{len(fixed_evs)}` 次，动态随机/情境事件 `{len(rand_evs)}` 次）。*\n"
    )

    lines.append("### 5. 主动行政行动与政策杠杆执行统计 (Top 15)")
    lines.append("| 排名 | 行动 / 政策指令 ID | 累计执行次数 |")
    lines.append("|---|---|---|")
    for idx, (aid, cnt) in enumerate(sorted(res["action_counts"].items(), key=lambda x: (-x[1], x[0]))[:15], 1):
        lines.append(f"| {idx} | `{aid}` | {cnt} 次 |")
    lines.append("")

    lines.append("### 6. 终局八维历史评价卡、三派史家评语与十大转折点")
    lines.append(f"- **最终结局代号**: `{ev['ending_id']}` — **{ev['ending_title']}**")
    lines.append(f"- **综合历史得分**: **{ev['overall_score']:.2f} / 100** | **最终评级**: **{ev['final_grade']}**" + (" *(受独裁集权上限规则封顶 B 级)*" if ev.get("grade_capped_by_auth") else ""))
    lines.append("")
    lines.append("| 八维历史评价指标 | 终局得分 (0–100) |")
    lines.append("|---|---|")
    dim_zh = [
        ("security", "国家安全与铁墙威慑 (Security)"),
        ("economy", "宏观经济与反通胀 (Economy)"),
        ("cohesion", "社会凝聚与族群平权 (Cohesion)"),
        ("democracy", "宪政民主与司法独立 (Democracy)"),
        ("diplomacy", "国际地位与美以同盟 (Diplomacy)"),
        ("territory", "领土主权与定居点遗产 (Territory)"),
        ("palestine", "巴勒斯坦治理与和平前景 (Palestine)"),
        ("leadership", "政党领导力与执政韧性 (Leadership)"),
    ]
    for dk, dlbl in dim_zh:
        lines.append(f"| {dlbl} | **{ev['dimensions'].get(dk, 0.0):.2f}** |")
    lines.append("")
    lines.append("#### 三大历史学派终局裁定 (M14 §4.3.3)")
    for sk, sv in ev.get("school_verdicts", {}).items():
        lines.append(f"- **{sv['scholar_zh']}** — 评分 **{sv['score']:.2f} ({sv['grade']})**：{sv['commentary_zh']}")
    lines.append("")
    lines.append("#### 史官编年录：本局关键历史转折点（按时间升序排列，Rubric R22）")
    for idx, tp in enumerate(ev.get("selected_turning_points", []), 1):
        cat = tp.get("category") or tp.get("source") or "event"
        summ = tp.get("summary_zh", "")
        summ_part = f" — {summ}" if summ else ""
        lines.append(f"{idx}. `{tp.get('date', '')}` (Day {tp.get('day_index', 0)}) — **{tp.get('title_zh', '')}**{summ_part} *(类别: `{cat}`)*")
    lines.append("\n---\n")
    return "\n".join(lines)


def generate_three_transcripts(out_path: Path) -> None:
    print("Running Campaign 1: Pragmatic Revisionist Begin (Grand Vision Trajectory)...")
    c1 = run_narrative_campaign(
        bot=PragmaticVisionBeginBot(seed=500000),
        seed=500000,
        days=5478,
        allow_succession=True,
        stop_on_end=False,
        campaign_title="战报一：务实修正主义贝京路线 — 「在以色列地的和平」宏大愿景达成局",
        campaign_subtitle="南线缔结戴维营和约 + 1982黎巴嫩战线严守40公里避免贝京精神崩溃 + 1985新谢克尔稳定计划 + 犹太与撒马利亚定居点既成事实化",
    )

    print("Running Campaign 2: Iron-Wall Settler / Sharon Alliance Trajectory...")
    c2 = run_narrative_campaign(
        bot=RevisionistHawkBot(seed=19810607),
        seed=19810607,
        days=5478,
        allow_succession=True,
        stop_on_end=False,
        campaign_title="战报二：铁壁定居者与沙龙同盟路线 — 大以色列定居狂飙与北线全面战争局",
        campaign_subtitle="全力倾斜定居点补贴与国防预算 + 强推大松树计划直捣贝鲁特 + 贝京1983高压隐退后沙米尔接棒铁腕应对大起义",
    )

    print("Running Campaign 3: Authoritarian Strongman C4/C5 Constitutional Crisis Trajectory...")
    c3 = run_narrative_campaign(
        bot=AuthoritarianCaesarBot(seed=19790326),
        seed=19790326,
        days=5478,
        allow_succession=False,
        stop_on_end=True,
        campaign_title="战报三：凯撒集权强人路线 — 冲击 C4/C5 紧急状态与宪政崩解反噬局",
        campaign_subtitle="强推超越条款、清洗独立司法与安全首脑、实施新闻审查 → 触发最高法院违宪对决、总工会全国总罢工与威权非最优铁律 (R32/X2)",
    )

    header = [
        "# 《应许之地的十字路口：贝京 1977–1992》三局完整实机推演战报集 (Playtest Transcripts)",
        "",
        "> **生成工具**: `python3 tools/play_cli.py --generate-transcripts`  ",
        "> **引擎版本**: Phase 3C Calibrated Reference Simulation (`sim/engine.py` + `sim/modules.py` + `data/events/fixed_1977_1992.yaml`)  ",
        "> **验证目的**: 完整呈现三条代表性战略路线在 1977–1992 旗舰剧本中的因果传导、三层目标张力、通货膨胀与稳定计划曲线、人物命运分叉以及终局八维历史评价。",
        "",
        "---",
        "",
    ]
    full_md = "\n".join(header) + render_campaign_markdown(c1) + render_campaign_markdown(c2) + render_campaign_markdown(c3)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full_md, encoding="utf-8")
    print(f"Successfully wrote 3 full campaign transcripts to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CLI Playtest Client for Israel Political Simulation")
    parser.add_argument("--bot", type=str, default="historical", help="Bot persona name or 'pragmatic_vision'")
    parser.add_argument("--seed", type=int, default=19770620, help="Random seed")
    parser.add_argument("--days", type=int, default=5478, help="Max days to simulate")
    parser.add_argument("--interactive", action="store_true", help="Play interactively via stdin")
    parser.add_argument("--generate-transcripts", action="store_true", help="Generate the 3 signature playtest transcripts")
    parser.add_argument(
        "--out",
        type=str,
        default=str(ROOT / "docs" / "reviews" / "playtest_transcripts.md"),
        help="Output markdown path for --generate-transcripts",
    )
    args = parser.parse_args()

    if args.generate_transcripts:
        generate_three_transcripts(Path(args.out))
        return

    if args.interactive:
        bot: StrategyBot = InteractivePlayBot(seed=args.seed)
    elif args.bot == "pragmatic_vision":
        bot = PragmaticVisionBeginBot(seed=args.seed)
    else:
        bot_cls = BOT_MAP.get(args.bot, HistoricalBot)
        bot = bot_cls(seed=args.seed)

    res = run_narrative_campaign(
        bot=bot,
        seed=args.seed,
        days=args.days,
        campaign_title=f"CLI 实机推演 — {bot.bot_id} (Seed {args.seed})",
        campaign_subtitle="单局完整推演记录",
    )
    print(render_campaign_markdown(res))


if __name__ == "__main__":
    main()
