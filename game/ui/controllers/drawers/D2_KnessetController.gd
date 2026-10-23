class_name D2KnessetController
extends Control

const SEAT_RED: Color = Color(0.72, 0.16, 0.18)
const SEAT_BLUE: Color = Color(0.0, 0.22, 0.72)

var party_seats: Dictionary = {}
var coalition_loyalty: Dictionary = {}
var party_polls: Dictionary = {}
var seat_dots: int = 0
## Coalition (government members + support) and opposition party ids, each sorted by seats desc.
var coalition: Array[String] = []
var opposition: Array[String] = []
## One colour per seat dot when the government is known (coalition first, then opposition).
var dot_colors: Array[Color] = []
var legend: Label


func _ready() -> void:
	custom_minimum_size = Vector2(900, 420)
	_ensure_legend()
	queue_redraw()


func _ensure_legend() -> void:
	if legend != null:
		return
	legend = Label.new()
	legend.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(legend)
	legend.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	legend.position = Vector2(0.0, 320.0)


func refresh(state: SimState) -> void:
	_ensure_legend()
	party_seats.clear()
	coalition_loyalty.clear()
	party_polls.clear()
	var m03: Dictionary = _dict(state.modules.get("M03", {}))
	var seats: Dictionary = _dict(m03.get("knesset_seats", state.parliament.get("knesset_seats", {})))
	var ids: Array[String] = SimMath.sorted_keys(seats)
	seat_dots = 0
	for i: int in range(ids.size()):
		var count: int = SimMath.round_half_up_int(float(seats[ids[i]]))
		party_seats[ids[i]] = count
		party_polls[ids[i]] = count
		seat_dots += count
		coalition_loyalty[ids[i]] = state.params.get_val("ally_satisfaction", ids[i], state)
	if seat_dots <= 0:
		seat_dots = 120
	_split_coalition(state, ids)
	queue_redraw()


func seat_total() -> int:
	return seat_dots


func _split_coalition(state: SimState, ids: Array[String]) -> void:
	coalition.clear()
	opposition.clear()
	dot_colors.clear()
	var government: Dictionary = _dict(state.parliament.get("government", {}))
	var in_government: Dictionary = {}
	for list_key: String in ["members", "support"]:
		var raw: Variant = government.get(list_key, [])
		if typeof(raw) == TYPE_ARRAY:
			var members: Array = raw
			for j: int in range(members.size()):
				in_government[String(members[j])] = true
	for i: int in range(ids.size()):
		if int(party_seats.get(ids[i], 0)) <= 0:
			continue
		if in_government.has(ids[i]):
			coalition.append(ids[i])
		else:
			opposition.append(ids[i])
	coalition.sort_custom(_by_seats_desc)
	opposition.sort_custom(_by_seats_desc)
	if in_government.is_empty():
		legend.text = ""
		return
	for i: int in range(coalition.size()):
		for _k: int in range(int(party_seats[coalition[i]])):
			dot_colors.append(SEAT_RED)
	for i: int in range(opposition.size()):
		for _k: int in range(int(party_seats[opposition[i]])):
			dot_colors.append(SEAT_BLUE)
	legend.text = "%s\n%s" % [_legend_row("执政联盟", coalition), _legend_row("反对派", opposition)]


func _legend_row(title: String, parties: Array[String]) -> String:
	var total: int = 0
	var parts: PackedStringArray = PackedStringArray()
	for i: int in range(parties.size()):
		var count: int = int(party_seats.get(parties[i], 0))
		total += count
		parts.append("%s %d" % [parties[i], count])
	return "%s %d 席：%s" % [title, total, " · ".join(parts)]


func _by_seats_desc(a: String, b: String) -> bool:
	var seats_a: int = int(party_seats.get(a, 0))
	var seats_b: int = int(party_seats.get(b, 0))
	if seats_a != seats_b:
		return seats_a > seats_b
	return a < b


func _draw() -> void:
	var total: int = maxi(seat_dots, 1)
	var shown: int = mini(total, 120)
	for i: int in range(shown):
		var t: float = float(i) / float(maxi(shown - 1, 1))
		var angle: float = PI * (1.0 - t)
		var radius: float = 160.0 + float(i % 4) * 18.0
		var at: Vector2 = Vector2(460, 280) + Vector2(cos(angle), -sin(angle)) * radius
		var color: Color = SEAT_RED if i < 61 else SEAT_BLUE
		if not dot_colors.is_empty():
			color = dot_colors[i] if i < dot_colors.size() else SEAT_BLUE
		draw_circle(at, 4.0, color)
	draw_line(Vector2(80, 300), Vector2(840, 300), SEAT_RED, 2.0)


func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
