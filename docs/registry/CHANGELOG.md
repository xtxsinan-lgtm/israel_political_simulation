# 登记表变更记录

所有对 `parameters.yaml`、`contracts.md` 的修改都在这里记录：日期、提出者、内容、理由。

| 日期 | 提出者 | 变更 | 理由 |
|---|---|---|---|
| 2026-10-15 | 主代理 | 初版：62个参数，实体表，模块编号 M01–M15 | 阶段0 |
| 2026-10-18 | 数据架构师（阶段2A） | 统合 `DECISIONS.md`（D-001 至 D-088）全部获批新增参数（共 110 项参数）：M02 7项（`settlement_policy, region_land_policy, military_government, exemption_coverage, outpost_enforcement, appointment_gap, haredi_cohort`）、M03 10项（`knesset_seats, poll_share, poll_seats, poll_lead, months_to_election, govt_fatigue, bloc_policy_gap, bloc_promise_score, ally_deal_score, seat_expectation_bonus`）、M04 6项（`faction_mood, faction_weight, party_cohesion, challenger_strength, cynicism, promise_credit`，合并 `voter_cynicism -> cynicism`；`stance_deviation` 改为 `derived`）、M05 4项（`policy_level, gov_axis_position, favor_party, favor_character`）、M06 1项（`character_stress`）、M07 2项（`country_war_readiness, peace_treaty_state`；`enemy_nuclear_progress` scope 改为 `country`）、M08 4项（`faction_moderation, faction_cohesion, collaborator_stigma, autonomy_progress`）、M09 1项（`intel_accuracy` 及 `security_index -> public_security` 别名）、M10 2项（`budget_slider, strike_risk`）、M11 8项（`region_absorption_priority, region_investment_priority, region_security_posture, settler_population, trilemma_jewish, trilemma_democratic, trilemma_territory, region_alienation`）、M13 3项（`coup_risk, assassination_risk, social_protest_tier`） | 阶段2A 注册表统合 |
| 2026-10-18 | 数据架构师（阶段2A） | 扩充 `entities`（`parties` 增补18项并合并 `pm_new_party -> new_party_a`、`party_factions` 11项、`budget_items` 8项、`pal_factions` 9枚举、`regions_dynamic` 增补 `south_lebanon`、`countries`、`offices`、`promise_categories`）并新增 `aliases` 映射表；同步更新 `docs/contracts.md`（结算子步骤、custom 处理器总表、表达式函数总表、`KNOWN_MODIFIER_FACTORS` 总表） | 阶段2A 契约统合 |
