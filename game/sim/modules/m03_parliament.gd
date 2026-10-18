class_name M03Parliament
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.

const KNESSET_SEATS: int = 120


func _init() -> void:
	module_id = "M03"


func get_electoral_threshold_pct(year: int) -> float:
	if year < 1992:
		return 1.0
	return 1.5


func allocate_knesset_seats(vote_shares: Dictionary, year: int, pairs: Array) -> Dictionary:
	var percent: Dictionary = _as_percent(vote_shares)
	var threshold: float = get_electoral_threshold_pct(year)
	var eligible: Dictionary = {}
	var ids: Array[String] = SimMath.sorted_keys(percent)
	for i: int in range(ids.size()):
		if float(percent[ids[i]]) + 1.0e-9 >= threshold:
			eligible[ids[i]] = float(percent[ids[i]])
	if eligible.is_empty():
		for i: int in range(ids.size()):
			if float(percent[ids[i]]) > 0.0:
				eligible[ids[i]] = float(percent[ids[i]])
	if eligible.is_empty() and not ids.is_empty():
		eligible[ids[0]] = 1.0
	var lists: Array[Dictionary] = _build_lists(eligible, pairs)
	var list_seats: Dictionary = _dhondt(lists, KNESSET_SEATS)
	var out: Dictionary = {}
	for i: int in range(lists.size()):
		var row: Dictionary = lists[i]
		var granted: int = int(list_seats.get(String(row["id"]), 0))
		var members: Array = _as_array(row.get("members", []))
		if members.size() <= 1:
			var only: String = String(row["id"])
			out[only] = int(out.get(only, 0)) + granted
			continue
		var inner: Array[Dictionary] = []
		for m: int in range(members.size()):
			var party_id: String = String(members[m])
			inner.append({"id": party_id, "votes": int(row.get("vote_" + party_id, 0))})
		var split: Dictionary = _dhondt(inner, granted)
		for m: int in range(members.size()):
			var party_id: String = String(members[m])
			out[party_id] = int(out.get(party_id, 0)) + int(split.get(party_id, 0))
	for i: int in range(ids.size()):
		if not out.has(ids[i]):
			out[ids[i]] = 0
	return out


func recompute_coalition_seats(state: SimState) -> int:
	var m03: Dictionary = _m03(state)
	var parties: Array = _as_array(m03.get("coalition_parties", []))
	var total: int = 0
	for i: int in range(parties.size()):
		total += int(round_half_away(state.params.get_val("knesset_seats", String(parties[i]), state)))
	m03["coalition_seats"] = total
	state.modules["M03"] = m03
	state.params.set_val("coalition_seats", "", float(total), state)
	return total


func compute_party_vote_shares(state: SimState) -> Dictionary:
	var m03: Dictionary = _m03(state)
	var blocs: Array = _as_array(m03.get("blocs", ["mizrahi", "haredi", "secular", "arab", "national", "religious_zionist", "russian", "ashkenazi"]))
	var parties: Array = _as_array(m03.get("parties", []))
	if parties.is_empty():
		parties = _seat_parties(state)
	var weights: Dictionary = {}
	var total: float = 0.0
	for i: int in range(parties.size()):
		var party_id: String = String(parties[i])
		var weight: float = 0.01
		for b: int in range(blocs.size()):
			var bloc: String = String(blocs[b])
			var support: float = state.params.get_val("bloc_support", bloc, state)
			var gap: float = state.params.get_val("bloc_policy_gap", bloc, state)
			var promise: float = state.params.get_val("bloc_promise_score", bloc, state)
			var attraction: float = 1.0
			if state.modifiers != null:
				attraction = state.modifiers.get_factor("vote_attraction", party_id)
			weight += maxf(0.0, support) * attraction * (1.0 - clampf(gap, 0.0, 100.0) / 200.0) * (0.5 + clampf(promise, 0.0, 100.0) / 200.0)
		var cynicism: float = state.params.get_val("cynicism", "", state)
		weight *= clampf(1.0 - cynicism / 400.0, 0.25, 1.0)
		weights[party_id] = weight
		total += weight
	var shares: Dictionary = {}
	if total <= 1.0e-9:
		var even: float = 100.0 / float(maxi(1, parties.size()))
		for i: int in range(parties.size()):
			shares[String(parties[i])] = even
		return shares
	for i: int in range(parties.size()):
		var party_id: String = String(parties[i])
		shares[party_id] = 100.0 * float(weights[party_id]) / total
	return shares


func weekly_step(step_no: int, state: SimState, ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 7:
		return []
	var effects: Array[Dictionary] = open_campaign_if_due(state)
	if SimCalendar.is_first_sunday_of_month(state.clock.weekday, state.clock.d):
		effects.append_array(_step_7a(state))
	effects.append_array(_step_7b(state))
	effects.append_array(_resolve_due_bills(state, ctx))
	return effects


func daily_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 19:
		return []
	return _resolve_vote_requests(state)


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	match op_name:
		"m03_apply_seat_change":
			return _seat_change(state, args)
		"m03_request_vote":
			return _request_vote(state, args)
		"m03_submit_bill":
			return _submit_bill(state, args)
		"m03_offer":
			return _offer(state, args)
		"m03_form_unity_rotation":
			return _unity(state, args)
		"m03_add_to_coalition":
			return _coalition_edit(state, String(args.get("party", "")), true)
		"m03_remove_from_coalition":
			return _coalition_edit(state, String(args.get("party", "")), false)
		"m03_split_party", "m03_mk_defect":
			return _move_seats(state, String(args.get("from", args.get("party", ""))), String(args.get("to", "new_party_a")), int(args.get("seats", 1)))
		"m03_found_party":
			return _move_seats(state, String(args.get("from", state.player.get("party_id", "likud"))), "new_party_a", int(args.get("seats", 1)))
		"m03_merge_parties":
			return _move_seats(state, String(args.get("from", "")), String(args.get("into", "")), 999)
		"m03_dissolve_party":
			return _dissolve(state, String(args.get("party", "")))
		"m03_set_role", "m03_assign_portfolio":
			return _assign_role(state, args)
		"m03_delay_demand":
			_m03(state)["demand_delay_" + String(args.get("party", ""))] = state.clock.day_index + int(args.get("days", 30))
			return []
		"m03_force_support":
			var whip: Dictionary = _as_dict(_m03(state).get("whip", {}))
			whip[String(args.get("bill_uid", args.get("party", "")))] = true
			var m03: Dictionary = _m03(state)
			m03["whip"] = whip
			state.modules["M03"] = m03
			return []
		"m03_postpone_election":
			return _postpone(state, args)
		"m03_dissolve_knesset":
			return _request_vote(state, {"kind": "early_election", "due_day": state.clock.day_index})
		_:
			return []
	return []


func _step_7a(state: SimState) -> Array[Dictionary]:
	var m03: Dictionary = _m03(state)
	var parties: Array = _as_array(m03.get("coalition_parties", []))
	var fatigue: float = state.params.get_val("govt_fatigue", "", state) + 0.4
	state.params.set_val("govt_fatigue", "", fatigue, state)
	var effects: Array[Dictionary] = []
	for i: int in range(parties.size()):
		var party_id: String = String(parties[i])
		var score: float = _deal_score(state, party_id)
		var deals: Dictionary = _as_dict(m03.get("ally_deal_score", {}))
		deals[party_id] = score
		m03["ally_deal_score"] = deals
		var sat: float = clampf(state.params.get_val("ally_satisfaction", party_id, state) * 0.9 + score * 0.1, 0.0, 100.0)
		state.params.set_val("ally_satisfaction", party_id, sat, state)
		var low: Dictionary = _as_dict(m03.get("low_sat_months", {}))
		if sat < 20.0:
			low[party_id] = int(low.get(party_id, 0)) + 1
		else:
			low[party_id] = 0
		m03["low_sat_months"] = low
		if int(low[party_id]) >= 2 and party_id != String(state.player.get("party_id", "")):
			effects.append_array(_coalition_edit(state, party_id, false))
			effects.append({"op": "set_flag", "flag": "ally_exit_warning." + party_id, "value": 1.0, "ai_reason_breakdown": {"ally_satisfaction": sat}})
	state.modules["M03"] = m03
	recompute_coalition_seats(state)
	return effects


func _step_7b(state: SimState) -> Array[Dictionary]:
	var shares: Dictionary = compute_party_vote_shares(state)
	var rng: SimRNG.Stream = state.rng.get_stream("politics")
	var noisy: Dictionary = {}
	var ids: Array[String] = SimMath.sorted_keys(shares)
	var total: float = 0.0
	for i: int in range(ids.size()):
		var jitter: float = rng.uniform(-1.5, 1.5)
		var value: float = maxf(0.0, float(shares[ids[i]]) + jitter)
		noisy[ids[i]] = value
		total += value
	if total > 1.0e-9:
		for i: int in range(ids.size()):
			noisy[ids[i]] = 100.0 * float(noisy[ids[i]]) / total
	for i: int in range(ids.size()):
		state.params.set_val("poll_share", ids[i], float(noisy[ids[i]]), state)
	var seats: Dictionary = allocate_knesset_seats(noisy, state.clock.y, _pairs(state))
	var seat_ids: Array[String] = SimMath.sorted_keys(seats)
	for i: int in range(seat_ids.size()):
		state.params.set_val("poll_seats", seat_ids[i], float(seats[seat_ids[i]]), state)
	var player: String = String(state.player.get("party_id", "likud"))
	var player_seats: int = int(seats.get(player, 0))
	var opponent: int = 0
	for i: int in range(seat_ids.size()):
		if seat_ids[i] == player:
			continue
		opponent = maxi(opponent, int(seats[seat_ids[i]]))
	var lead: int = player_seats - opponent
	state.params.set_val("poll_lead", "", float(lead), state)
	var m03: Dictionary = _m03(state)
	m03["poll_lead"] = lead
	state.modules["M03"] = m03
	return []


func _resolve_due_bills(state: SimState, ctx: Dictionary) -> Array[Dictionary]:
	var m03: Dictionary = _m03(state)
	var bills: Array = _as_array(m03.get("scheduled_bills", []))
	var keep: Array = []
	var effects: Array[Dictionary] = []
	var rng: SimRNG.Stream = state.rng.get_stream("politics")
	for i: int in range(bills.size()):
		var bill: Dictionary = _as_dict(bills[i])
		if int(bill.get("due_day", 0)) > state.clock.day_index:
			keep.append(bill)
			continue
		effects.append_array(_resolve_scheduled_bill(bill, state, rng))
	m03["scheduled_bills"] = keep
	state.modules["M03"] = m03
	return effects


func _resolve_scheduled_bill(bill: Dictionary, state: SimState, _rng: SimRNG.Stream) -> Array[Dictionary]:
	var vote: String = String(bill.get("vote", "simple"))
	if bill.has("votes_for_override"):
		var forced: int = int(bill["votes_for_override"])
		var forced_pass: bool = _vote_passes(vote, forced, KNESSET_SEATS - forced)
		if forced_pass and (vote == "absolute80" or vote == "entrenched80"):
			var m03_force: Dictionary = _m03(state)
			m03_force["months_to_election"] = int(m03_force.get("months_to_election", 0)) + int(bill.get("extend_months", 6))
			state.modules["M03"] = m03_force
		return [{"op": "custom", "key": "m05_bill_result", "value": {"bill_uid": String(bill.get("uid", "")), "passed": forced_pass, "votes_for": forced}}]
	var votes_for: int = 0
	var votes_against: int = 0
	var coalition: Array = _as_array(_m03(state).get("coalition_parties", []))
	var whip: Dictionary = _as_dict(_m03(state).get("whip", {}))
	var whipped: bool = bool(whip.get(String(bill.get("uid", "")), false))
	for i: int in range(coalition.size()):
		var party_id: String = String(coalition[i])
		var seats: int = int(round_half_away(state.params.get_val("knesset_seats", party_id, state)))
		var sat: float = state.params.get_val("ally_satisfaction", party_id, state)
		var yes: int = seats
		if not whipped and sat < 40.0:
			yes = SimMath.idiv_floor(seats * int(sat), 100)
		votes_for += yes
		votes_against += seats - yes
	var player_seats: int = int(round_half_away(state.params.get_val("knesset_seats", String(state.player.get("party_id", "")), state)))
	votes_for += player_seats
	votes_against += maxi(0, KNESSET_SEATS - votes_for - votes_against)
	var passed: bool = false
	match vote:
		"absolute61", "confidence":
			passed = votes_for >= 61
		"absolute80", "entrenched80":
			passed = votes_for >= 80
		"budget":
			passed = votes_for >= 61
		_:
			passed = votes_for > votes_against
	var origin: String = String(bill.get("origin", "M05"))
	var payload: Dictionary = {"bill_uid": String(bill.get("uid", "")), "passed": passed, "votes_for": votes_for, "votes_against": votes_against}
	if origin == "M07":
		return [{"op": "custom", "key": "m07_ratification_result", "value": payload}]
	if origin == "M10" or vote == "budget":
		return [{"op": "custom", "key": "m10_budget_result", "value": {"passed": passed}}]
	return [{"op": "custom", "key": "m05_bill_result", "value": payload}]


func _resolve_vote_requests(state: SimState) -> Array[Dictionary]:
	var pending: Dictionary = state.pending
	var requests: Array = _as_array(pending.get("vote_requests", []))
	var keep: Array = []
	var effects: Array[Dictionary] = []
	var survival: bool = bool(_as_dict(state.modules.get("M13", {})).get("survival_mode", false))
	for i: int in range(requests.size()):
		var req: Dictionary = _as_dict(requests[i])
		if int(req.get("due_day", 0)) > state.clock.day_index:
			keep.append(req)
			continue
		var kind: String = String(req.get("kind", "election"))
		if survival and (kind == "election" or kind == "no_confidence"):
			keep.append(req)
			continue
		if kind == "no_confidence":
			var yes: int = recompute_coalition_seats(state)
			if KNESSET_SEATS - yes >= 61:
				effects.append({"op": "custom", "key": "end_tenure", "value": {"reason": "no_confidence"}})
		else:
			var shares: Dictionary = compute_party_vote_shares(state)
			var seats: Dictionary = allocate_knesset_seats(shares, state.clock.y, _pairs(state))
			var seat_ids: Array[String] = SimMath.sorted_keys(seats)
			for s: int in range(seat_ids.size()):
				state.params.set_val("knesset_seats", seat_ids[s], float(seats[seat_ids[s]]), state)
			var player: String = String(state.player.get("party_id", ""))
			var best: int = 0
			var best_id: String = player
			for s: int in range(seat_ids.size()):
				if int(seats[seat_ids[s]]) > best:
					best = int(seats[seat_ids[s]])
					best_id = seat_ids[s]
			if best_id == player:
				var m03: Dictionary = _m03(state)
				m03["phase"] = "formation"
				m03["formation_deadline"] = state.clock.day_index + 42
				state.modules["M03"] = m03
			else:
				effects.append({"op": "custom", "key": "end_tenure", "value": {"reason": "election_loss"}})
	pending["vote_requests"] = keep
	state.pending = pending
	return effects


func _seat_change(state: SimState, args: Dictionary) -> Array[Dictionary]:
	var party_id: String = String(args.get("party", ""))
	var delta: int = int(args.get("delta", 0))
	var cur: int = int(round_half_away(state.params.get_val("knesset_seats", party_id, state)))
	state.params.set_val("knesset_seats", party_id, float(clampi(cur + delta, 0, KNESSET_SEATS)), state)
	recompute_coalition_seats(state)
	return []


func _request_vote(state: SimState, args: Dictionary) -> Array[Dictionary]:
	var pending: Dictionary = state.pending
	var requests: Array = _as_array(pending.get("vote_requests", []))
	requests.append({
		"kind": String(args.get("kind", "election")),
		"due_day": int(args.get("due_day", state.clock.day_index + 90)),
	})
	pending["vote_requests"] = requests
	state.pending = pending
	return []


func _submit_bill(state: SimState, args: Dictionary) -> Array[Dictionary]:
	var m03: Dictionary = _m03(state)
	var bills: Array = _as_array(m03.get("scheduled_bills", []))
	bills.append({
		"uid": String(args.get("bill_uid", "bill-%d" % bills.size())),
		"vote": String(args.get("vote", "simple")),
		"origin": String(args.get("origin", "M05")),
		"due_day": int(args.get("due_day", state.clock.day_index + 7)),
	})
	m03["scheduled_bills"] = bills
	state.modules["M03"] = m03
	return []


func _offer(state: SimState, args: Dictionary) -> Array[Dictionary]:
	var m03: Dictionary = _m03(state)
	var offers: Dictionary = _as_dict(m03.get("offers", {}))
	offers[String(args.get("party", ""))] = args.duplicate(true)
	m03["offers"] = offers
	state.modules["M03"] = m03
	return []


func _unity(state: SimState, _args: Dictionary) -> Array[Dictionary]:
	var m03: Dictionary = _m03(state)
	m03["unity_rotation_active"] = true
	m03["unity_months_left"] = 24
	state.modules["M03"] = m03
	return [{"op": "add_modifier", "modifier": "unity_rotation_pc", "value": {"factors": [{"key": "pc_cost", "mode": "mult", "value": 1.5}], "duration_days": 720}}]


func _coalition_edit(state: SimState, party_id: String, add: bool) -> Array[Dictionary]:
	if party_id == "":
		return []
	var m03: Dictionary = _m03(state)
	var parties: Array = _as_array(m03.get("coalition_parties", []))
	var next: Array = []
	var found: bool = false
	for i: int in range(parties.size()):
		if String(parties[i]) == party_id:
			found = true
			if add:
				next.append(party_id)
		else:
			next.append(parties[i])
	if add and not found:
		next.append(party_id)
	m03["coalition_parties"] = next
	state.modules["M03"] = m03
	recompute_coalition_seats(state)
	return []


func _move_seats(state: SimState, from_party: String, to_party: String, seats: int) -> Array[Dictionary]:
	if from_party == "" or to_party == "":
		return []
	var have: int = int(round_half_away(state.params.get_val("knesset_seats", from_party, state)))
	var moved: int = mini(have, maxi(0, seats))
	state.params.set_val("knesset_seats", from_party, float(have - moved), state)
	var dest: int = int(round_half_away(state.params.get_val("knesset_seats", to_party, state)))
	state.params.set_val("knesset_seats", to_party, float(dest + moved), state)
	recompute_coalition_seats(state)
	return []


func _dissolve(state: SimState, party_id: String) -> Array[Dictionary]:
	var m03: Dictionary = _m03(state)
	var archived: Array = _as_array(m03.get("archived_parties", []))
	archived.append(party_id)
	m03["archived_parties"] = archived
	state.modules["M03"] = m03
	var moved: Array[Dictionary] = _move_seats(state, party_id, String(state.player.get("party_id", "likud")), 999)
	state.params.deactivate_key("knesset_seats", party_id)
	state.params.deactivate_key("ally_satisfaction", party_id)
	return moved


func open_campaign_if_due(state: SimState) -> Array[Dictionary]:
	var days: int = int(_m03(state).get("days_to_election", 9999))
	if days != 90:
		return []
	state.flags["campaign_period_active"] = {"value": 1.0, "set_day": state.clock.day_index}
	return [{"op": "custom", "key": "m04_open_campaign_pool", "value": {}}]


func note_reelection(state: SimState) -> void:
	var m03: Dictionary = _m03(state)
	var bonus: float = float(m03.get("seat_expectation_bonus", 0.0)) + 4.0
	m03["seat_expectation_bonus"] = bonus
	state.modules["M03"] = m03


func score_offer(state: SimState, args: Dictionary) -> float:
	var offer_type: String = String(args.get("offer_type", "portfolio"))
	var score: float = 0.0
	if offer_type == "portfolio":
		score += clampf(float(args.get("weight", 12.0)), 8.0, 22.0)
	elif offer_type == "policy_clause":
		score += 10.0
	elif offer_type == "budget_guarantee":
		score += 8.0
	var ideological_dist: float = 0.0
	var axes: Array[String] = SimTypes.STANCE_AXES
	for i: int in range(axes.size()):
		var d: float = float(state.gov_axis_position.get(axes[i], 0.0)) - float(args.get(axes[i], 0.0))
		ideological_dist += d * d
	ideological_dist = sqrt(ideological_dist)
	score -= ideological_dist * 0.05
	if bool(args.get("red_line", false)):
		return -999.0
	return score


func enter_caretaker(state: SimState) -> void:
	var m03: Dictionary = _m03(state)
	m03["caretaker"] = true
	m03["caretaker_govt"] = true
	state.modules["M03"] = m03
	state.modifiers.add_modifier("caretaker_government", {"factors": [{"key": "pc_cost", "mode": "mult", "value": 1.30}], "duration_days": 120}, "M03", state)


func _vote_passes(vote: String, votes_for: int, votes_against: int) -> bool:
	match vote:
		"absolute61", "confidence", "budget":
			return votes_for >= 61
		"absolute80", "entrenched80":
			return votes_for >= 80
		_:
			return votes_for > votes_against


func _assign_role(state: SimState, args: Dictionary) -> Array[Dictionary]:
	var office: String = String(args.get("office", args.get("role", "")))
	var who: String = String(args.get("character", ""))
	if office == "":
		return []
	var m06: Dictionary = _as_dict(state.modules.get("M06", {}))
	var offices: Dictionary = _as_dict(m06.get("offices", {}))
	offices[office] = who
	m06["offices"] = offices
	state.modules["M06"] = m06
	state.offices[office] = who
	return []


func _postpone(state: SimState, args: Dictionary) -> Array[Dictionary]:
	var m03: Dictionary = _m03(state)
	var days: int = int(args.get("days", 180))
	m03["days_to_election"] = int(m03.get("days_to_election", 0)) + days
	m03["election_postponed"] = true
	state.modules["M03"] = m03
	return []


func _deal_score(state: SimState, party_id: String) -> float:
	var base: float = 60.0
	base -= absf(state.params.get_val("bloc_policy_gap", party_id, state)) * 0.2
	return clampf(base, 0.0, 100.0)


func _pairs(state: SimState) -> Array:
	return _as_array(_m03(state).get("surplus_pairs", []))


func _seat_parties(state: SimState) -> Array:
	return state.params.get_active_keys("knesset_seats")


func _build_lists(eligible: Dictionary, pairs: Array) -> Array[Dictionary]:
	var used: Dictionary = {}
	var lists: Array[Dictionary] = []
	for i: int in range(pairs.size()):
		var pair: Variant = pairs[i]
		var a: String = ""
		var b: String = ""
		if typeof(pair) == TYPE_ARRAY and (pair as Array).size() >= 2:
			a = String((pair as Array)[0])
			b = String((pair as Array)[1])
		elif typeof(pair) == TYPE_DICTIONARY:
			a = String((pair as Dictionary).get("a", ""))
			b = String((pair as Dictionary).get("b", ""))
		if a == "" or b == "" or a == b or not eligible.has(a) or not eligible.has(b) or used.has(a) or used.has(b):
			continue
		used[a] = true
		used[b] = true
		var votes_a: int = _votes(float(eligible[a]))
		var votes_b: int = _votes(float(eligible[b]))
		lists.append({"id": a + "+" + b, "members": [a, b], "votes": votes_a + votes_b, "vote_" + a: votes_a, "vote_" + b: votes_b})
	var ids: Array[String] = SimMath.sorted_keys(eligible)
	for i: int in range(ids.size()):
		if used.has(ids[i]):
			continue
		lists.append({"id": ids[i], "members": [ids[i]], "votes": _votes(float(eligible[ids[i]]))})
	return lists


func _dhondt(lists: Array[Dictionary], seats: int) -> Dictionary:
	var granted: Dictionary = {}
	for i: int in range(lists.size()):
		granted[String(lists[i]["id"])] = 0
	if lists.is_empty() or seats <= 0:
		return granted
	for seat_i: int in range(seats):
		var _unused: int = seat_i
		var best: int = 0
		for i: int in range(1, lists.size()):
			if _quot_before(lists[i], int(granted[String(lists[i]["id"])]), lists[best], int(granted[String(lists[best]["id"])])):
				best = i
		var winner: String = String(lists[best]["id"])
		granted[winner] = int(granted[winner]) + 1
	return granted


func _quot_before(a: Dictionary, a_seats: int, b: Dictionary, b_seats: int) -> bool:
	var qa: float = float(int(a.get("votes", 0))) / float(a_seats + 1)
	var qb: float = float(int(b.get("votes", 0))) / float(b_seats + 1)
	if not is_equal_approx(qa, qb):
		return qa > qb
	if a_seats != b_seats:
		return a_seats < b_seats
	return String(a.get("id", "")) < String(b.get("id", ""))


func _votes(percent: float) -> int:
	return maxi(0, SimMath.round_half_up_int(percent * 10000.0))


func _as_percent(vote_shares: Dictionary) -> Dictionary:
	var ids: Array[String] = SimMath.sorted_keys(vote_shares)
	var total: float = 0.0
	for i: int in range(ids.size()):
		total += float(vote_shares[ids[i]])
	var scale: float = 1.0
	if total > 0.0 and total <= 1.5:
		scale = 100.0
	var out: Dictionary = {}
	for i: int in range(ids.size()):
		out[ids[i]] = float(vote_shares[ids[i]]) * scale
	return out


func round_half_away(value: float) -> int:
	return SimMath.round_half_up_int(value)


func _m03(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M03", {}))
	state.modules["M03"] = current
	return current


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}


func _as_array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []
