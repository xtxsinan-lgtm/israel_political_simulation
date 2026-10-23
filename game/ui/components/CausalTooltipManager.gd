class_name CausalTooltipManager
extends Control

## Causal tooltip cards (LockableTooltipPanel at (980,80), 300 wide).
## Opened via DeskEventBus.tooltip_requested(param_id, scope_key) -> DeskMainController ->
## explain_node(state, param_id, scope_key). One transient card at a time; up to 3 locked cards
## (mirrored into UIManager.tooltip_stack so Esc pops the newest lock). The transient card
## closes on a click elsewhere, on ×, or when another one opens. Locked cards re-explain daily.

const MAX_LOCKED: int = 3

var locked: Array[String] = []
## Widgets of the most recently filled card (kept for callers/tests).
var sparkline: SparklineDrawer
var body: Label
var hover_seconds: float = 0.35
var box: VBoxContainer
## tooltip_id -> {"root": PanelContainer, "body": Label, "spark": SparklineDrawer,
##                "lock_line": Label, "lock_button": Button, "param": String, "key": String}
var cards: Dictionary = {}
var bound_state: SimState = null


func _ready() -> void:
	_ensure_widgets()
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null and not bus.tooltip_lock_toggled.is_connected(_on_lock_toggled):
		bus.tooltip_lock_toggled.connect(_on_lock_toggled)


func _ensure_widgets() -> void:
	if box != null:
		return
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	box = VBoxContainer.new()
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.custom_minimum_size = Vector2(300, 0)
	add_child(box)
	visible = false


static func tooltip_id_for(param_id: String, scope_key: String) -> String:
	if scope_key == "":
		return param_id
	return "%s[%s]" % [param_id, scope_key]


func lock_tooltip(tooltip_id: String) -> bool:
	_ensure_widgets()
	if locked.has(tooltip_id):
		return true
	if locked.size() >= MAX_LOCKED:
		return false
	var router: DeskUiRouter = DeskUiRouter.current()
	if router != null:
		# UIManager owns the Esc stack and emits tooltip_lock_toggled(id, true).
		if not router.lock_tooltip(tooltip_id):
			return false
	else:
		_emit_lock(tooltip_id, true)
	var card: Dictionary = _card(tooltip_id, tooltip_id, "")
	locked.append(tooltip_id)
	body = card["body"] as Label
	sparkline = card["spark"] as SparklineDrawer
	if body.text == "":
		body.text = tooltip_id
	_layout()
	return true


func unlock_tooltip(tooltip_id: String) -> void:
	if not locked.has(tooltip_id):
		_close(tooltip_id)
		return
	var router: DeskUiRouter = DeskUiRouter.current()
	if router != null and router.tooltip_stack.has(tooltip_id):
		router.tooltip_stack.erase(tooltip_id)
	_emit_lock(tooltip_id, false)
	# Without an EventBus nobody calls back into _on_lock_toggled.
	if locked.has(tooltip_id):
		_on_lock_toggled(tooltip_id, false)


func handle_escape() -> bool:
	if locked.is_empty():
		_close_transient()
		visible = not cards.is_empty()
		return false
	unlock_tooltip(locked[locked.size() - 1])
	return true


func _on_lock_toggled(tooltip_id: String, is_locked: bool) -> void:
	if is_locked or not locked.has(tooltip_id):
		return
	locked.erase(tooltip_id)
	_close(tooltip_id)


func explain_node(state: SimState, node_id: String, scope_key: String = "") -> Dictionary:
	_ensure_widgets()
	bound_state = state
	var tooltip_id: String = tooltip_id_for(node_id, scope_key)
	var ids: Array = cards.keys()
	for i: int in range(ids.size()):
		var other: String = String(ids[i])
		if other != tooltip_id and not locked.has(other):
			_close(other)
	var card: Dictionary = _card(tooltip_id, node_id, scope_key)
	var explained: Dictionary = _fill(card, state)
	_layout()
	return explained


## Re-explains the locked cards (called once per sim day).
func refresh_locked(state: SimState) -> void:
	if state == null:
		return
	bound_state = state
	for i: int in range(locked.size()):
		if cards.has(locked[i]):
			_fill(cards[locked[i]], state)


func _fill(card: Dictionary, state: SimState) -> Dictionary:
	var node_id: String = String(card["param"])
	var scope_key: String = String(card["key"])
	var card_body: Label = card["body"] as Label
	var card_spark: SparklineDrawer = card["spark"] as SparklineDrawer
	body = card_body
	sparkline = card_spark
	var expr: ExprEngine = ExprEngine.new()
	expr.bind(state)
	var net: CausalNet = CausalNet.new()
	var explained: Dictionary = net.explain(state, node_id, scope_key, expr, {}, 5)
	var fuzzy: bool = FuzzyBand.is_fuzzy(node_id)
	card_spark.set_series(_node_history(state, node_id, scope_key, fuzzy), 35.0 if node_id == "public_security" else -1.0)
	var current: float = state.params.get_val(node_id, scope_key, state)
	var label_id: String = tooltip_id_for(node_id, scope_key)
	var lines: PackedStringArray = PackedStringArray()
	if fuzzy:
		lines.append("%s  %s" % [label_id, FuzzyBand.describe(current, node_id)])
	else:
		lines.append("%s = %.2f" % [label_id, current])
	var top: Array = _array(explained.get("top_contributions", []))
	for i: int in range(mini(5, top.size())):
		var row: Dictionary = top[i] if typeof(top[i]) == TYPE_DICTIONARY else {}
		var source_label: String = String(row.get("source_label_zh", row.get("source_id", "")))
		var delta: float = float(row.get("delta_per_tick", 0.0))
		if fuzzy:
			var arrow: String = "—"
			if delta > 0.0:
				arrow = "↑"
			elif delta < 0.0:
				arrow = "↓"
			lines.append("%s %s" % [source_label, arrow])
		else:
			lines.append("%s %+0.2f" % [source_label, delta])
	card_body.text = "\n".join(lines)
	return explained


## Last 30 daily values of the selected node (falls back to monthly snapshots).
## Fuzzy nodes are plotted as band centres so the curve cannot reveal exact values.
## Scoped (per-region) parameters have no global history column and get an empty series.
func _node_history(state: SimState, node_id: String, scope_key: String, fuzzy: bool) -> PackedFloat64Array:
	var history: PackedFloat64Array = PackedFloat64Array()
	if scope_key != "":
		return history
	var rows: Array = _array(state.history.get("daily_ring", []))
	if rows.is_empty() or typeof(rows[rows.size() - 1]) != TYPE_DICTIONARY or not (rows[rows.size() - 1] as Dictionary).has(node_id):
		rows = state.monthly_snapshots
	var start: int = maxi(0, rows.size() - 30)
	for i: int in range(start, rows.size()):
		if typeof(rows[i]) != TYPE_DICTIONARY:
			continue
		var row: Dictionary = rows[i]
		if not row.has(node_id):
			continue
		var value: float = float(row[node_id])
		if fuzzy:
			value = float(FuzzyBand.band_centre(FuzzyBand.band_index(value)))
		history.append(value)
	return history


func preview_action(state: SimState, effects: Array) -> Dictionary:
	_ensure_widgets()
	var expr: ExprEngine = ExprEngine.new()
	expr.bind(state)
	var preview: Dictionary = PreviewEngine.preview_effects_on_three_layers(state, effects, expr)
	var card: Dictionary = _card("preview", "preview", "")
	body = card["body"] as Label
	sparkline = card["spark"] as SparklineDrawer
	body.text = "L1 直接代价\nL2 下游区间\nL3 阈值预警\n%s" % preview.keys()
	_layout()
	return preview


func _card(tooltip_id: String, param_id: String, scope_key: String) -> Dictionary:
	if cards.has(tooltip_id):
		return cards[tooltip_id]
	var root: PanelContainer = PanelContainer.new()
	root.mouse_filter = Control.MOUSE_FILTER_STOP
	var column: VBoxContainer = VBoxContainer.new()
	var head: HBoxContainer = HBoxContainer.new()
	var lock_line: Label = Label.new()
	lock_line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var lock_button: Button = Button.new()
	lock_button.text = "锁定"
	lock_button.pressed.connect(_on_lock_pressed.bind(tooltip_id))
	var close_button: Button = Button.new()
	close_button.text = "×"
	close_button.tooltip_text = "关闭"
	close_button.pressed.connect(_on_close_pressed.bind(tooltip_id))
	head.add_child(lock_line)
	head.add_child(lock_button)
	head.add_child(close_button)
	var card_body: Label = Label.new()
	card_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	card_body.custom_minimum_size = Vector2(280, 0)
	var card_spark: SparklineDrawer = SparklineDrawer.new()
	card_spark.custom_minimum_size = Vector2(220, 48)
	column.add_child(head)
	column.add_child(card_body)
	column.add_child(card_spark)
	root.add_child(column)
	box.add_child(root)
	var card: Dictionary = {
		"root": root, "body": card_body, "spark": card_spark, "lock_line": lock_line,
		"lock_button": lock_button, "param": param_id, "key": scope_key,
	}
	cards[tooltip_id] = card
	return card


func _on_lock_pressed(tooltip_id: String) -> void:
	if locked.has(tooltip_id):
		unlock_tooltip(tooltip_id)
		return
	if not lock_tooltip(tooltip_id) and cards.has(tooltip_id):
		var lock_button: Button = (cards[tooltip_id] as Dictionary)["lock_button"] as Button
		lock_button.text = "已满 3/3"


func _on_close_pressed(tooltip_id: String) -> void:
	if locked.has(tooltip_id):
		unlock_tooltip(tooltip_id)
	else:
		_close(tooltip_id)


func _close(tooltip_id: String) -> void:
	if not cards.has(tooltip_id):
		return
	var card: Dictionary = cards[tooltip_id]
	cards.erase(tooltip_id)
	var root: PanelContainer = card["root"] as PanelContainer
	if root != null:
		box.remove_child(root)
		root.queue_free()
	_layout()


func _close_transient() -> void:
	var ids: Array = cards.keys()
	for i: int in range(ids.size()):
		if not locked.has(String(ids[i])):
			_close(String(ids[i]))


## Locked cards first (in lock order), then the transient one.
func _layout() -> void:
	var order: int = 0
	for i: int in range(locked.size()):
		if not cards.has(locked[i]):
			continue
		var card: Dictionary = cards[locked[i]]
		(card["lock_line"] as Label).text = "锁定 %d/3  %s" % [i + 1, locked[i]]
		(card["lock_button"] as Button).text = "解锁"
		box.move_child(card["root"] as Node, order)
		order += 1
	var ids: Array = cards.keys()
	for j: int in range(ids.size()):
		var other: String = String(ids[j])
		if locked.has(other):
			continue
		var rest: Dictionary = cards[other]
		(rest["lock_line"] as Label).text = ""
		(rest["lock_button"] as Button).text = "锁定"
	visible = not cards.is_empty()


## A click outside every card closes the transient (unlocked) card.
func _input(event: InputEvent) -> void:
	if not visible or not (event is InputEventMouseButton):
		return
	var button: InputEventMouseButton = event as InputEventMouseButton
	if not button.pressed or button.button_index != MOUSE_BUTTON_LEFT:
		return
	var ids: Array = cards.keys()
	for i: int in range(ids.size()):
		var card: Dictionary = cards[ids[i]]
		var root: PanelContainer = card["root"] as PanelContainer
		if root != null and root.get_global_rect().has_point(button.position):
			return
	_close_transient()


func _emit_lock(tooltip_id: String, is_locked: bool) -> void:
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.tooltip_lock_toggled.emit(tooltip_id, is_locked)


func _array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []
