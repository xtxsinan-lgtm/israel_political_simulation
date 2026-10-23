class_name OnboardingDirector
extends Control

## Spotlight tutorial on the SpotlightTutorialOverlay node ((1300,900)-(1660,980)).
## maybe_start() shows it on the first start (flag in user://settings.cfg), with the 8 steps,
## 下一步 (advance) and 跳过 (skip_tutorial). Finishing or skipping sets the flag and hides
## the overlay after 2 s. A spotlight outline marks the screen area each step refers to.

const STEP_COUNT: int = 8
const SETTINGS_PATH: String = "user://settings.cfg"
const SETTINGS_SECTION: String = "onboarding"
const SETTINGS_KEY: String = "done"
const STEPS: Array[String] = [
	"看顶栏：61 席与政治资本",
	"在地图上查看西奈、西岸和 F1–F7",
	"锁定一个因果提示，看通胀从哪来",
	"打开 D2，核对利库德联盟",
	"打开 D3，处理部长提案和 30% 折扣",
	"打开 D4，看因果网络",
	"读第一份电报和三层预览",
	"解除暂停，走到第一个周日",
]
## Spotlight rects (left, top, right, bottom) in 1920x1080 stage coordinates per step.
const SPOTS: Array[Rect2] = [
	Rect2(0, 0, 1920, 52),
	Rect2(240, 52, 1440, 942),
	Rect2(855, 0, 210, 52),
	Rect2(240, 52, 920, 900),
	Rect2(240, 52, 920, 900),
	Rect2(240, 52, 920, 900),
	Rect2(500, 200, 920, 400),
	Rect2(0, 0, 210, 52),
]

var step: int = 0
var skipped: bool = false
var body: Label
var next_button: Button
var skip_button: Button
var spot: ReferenceRect
## Only a run started through maybe_start() writes the settings flag (keeps tests side-effect free).
var persist_flag: bool = false


func _ready() -> void:
	if body != null:
		return
	var panel: PanelContainer = PanelContainer.new()
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var column: VBoxContainer = VBoxContainer.new()
	body = Label.new()
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var row: HBoxContainer = HBoxContainer.new()
	next_button = Button.new()
	next_button.text = "下一步"
	next_button.pressed.connect(advance)
	skip_button = Button.new()
	skip_button.text = "跳过"
	skip_button.pressed.connect(skip_tutorial)
	row.add_child(next_button)
	row.add_child(skip_button)
	column.add_child(body)
	column.add_child(row)
	panel.add_child(column)
	add_child(panel)
	spot = ReferenceRect.new()
	spot.editor_only = false
	spot.border_color = Color(0.784, 0.541, 0.118, 1)
	spot.border_width = 3.0
	spot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	spot.top_level = true
	spot.visible = false
	add_child(spot)
	_show()


static func onboarding_done() -> bool:
	var config: ConfigFile = ConfigFile.new()
	if config.load(SETTINGS_PATH) != OK:
		return false
	return bool(config.get_value(SETTINGS_SECTION, SETTINGS_KEY, false))


## Shows the tutorial on the first start only. Returns true when it was shown.
func maybe_start() -> bool:
	if onboarding_done():
		visible = false
		return false
	if body == null:
		_ready()
	step = 0
	skipped = false
	persist_flag = true
	next_button.disabled = false
	skip_button.disabled = false
	visible = true
	_show()
	return true


func advance() -> void:
	if skipped:
		return
	step = mini(step + 1, STEP_COUNT)
	_show()


func skip_tutorial() -> void:
	skipped = true
	step = STEP_COUNT
	if body == null:
		_ready()
	body.text = "教程已跳过，全部面板已解锁"
	_finish()


func finished() -> bool:
	return step >= STEP_COUNT


func _show() -> void:
	if body == null:
		return
	if step >= STEPS.size():
		body.text = "引导完成"
		_finish()
		return
	body.text = "第 %d 步  %s" % [step + 1, STEPS[step]]
	if spot != null:
		var area: Rect2 = SPOTS[step]
		spot.position = area.position
		spot.size = area.size
		spot.visible = visible


func _finish() -> void:
	if spot != null:
		spot.visible = false
	if next_button != null:
		next_button.disabled = true
	if skip_button != null:
		skip_button.disabled = true
	if persist_flag:
		var config: ConfigFile = ConfigFile.new()
		config.load(SETTINGS_PATH)
		config.set_value(SETTINGS_SECTION, SETTINGS_KEY, true)
		var err: Error = config.save(SETTINGS_PATH)
		if err != OK:
			push_warning("onboarding flag save failed: %s" % error_string(err))
	if visible and is_inside_tree():
		get_tree().create_timer(2.0).timeout.connect(_hide_overlay)


func _hide_overlay() -> void:
	visible = false
