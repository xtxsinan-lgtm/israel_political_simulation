class_name D2KnessetController
extends Control

var party_seats: Dictionary = {}
var coalition_loyalty: Dictionary = {}
var party_polls: Dictionary = {}
var seat_dots: int = 0


func _ready() -> void:
	custom_minimum_size = Vector2(920, 420)
	queue_redraw()


func refresh(state: SimState) -> void:
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
	queue_redraw()


func seat_total() -> int:
	return seat_dots


func _draw() -> void:
	var total: int = maxi(seat_dots, 1)
	var shown: int = mini(total, 120)
	for i: int in range(shown):
		var t: float = float(i) / float(maxi(shown - 1, 1))
		var angle: float = PI * (1.0 - t)
		var radius: float = 160.0 + float(i % 4) * 18.0
		var at: Vector2 = Vector2(460, 280) + Vector2(cos(angle), -sin(angle)) * radius
		var color: Color = Color(0.72, 0.16, 0.18) if i < 61 else Color(0.0, 0.22, 0.72)
		draw_circle(at, 4.0, color)
	draw_line(Vector2(80, 300), Vector2(840, 300), Color(0.72, 0.16, 0.18), 2.0)


func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
